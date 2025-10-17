"""
rag_engine.py
-------------
Gemini-2.5-Flash + FAISS 기반 RAG 엔진
- 주 고객층 강화 전략 + 유사매장 타겟 확장 전략 병합형 분석
- 현재 매장 페르소나(summary/persona 등)를 프롬프트 컨텍스트 최상단에 앵커로 삽입
"""
import warnings
warnings.filterwarnings("ignore", message="resource_tracker")
import os
import json
import traceback
import threading
import time
import numpy as np
import faiss
from typing import Dict, Any, List, Tuple
import google.generativeai as genai
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import multiprocessing

# ------------------------------------------------
# ✅ 병렬/성능 설정
# ------------------------------------------------
num_cores = min(4, multiprocessing.cpu_count())
os.environ["OMP_NUM_THREADS"] = str(num_cores)
os.environ["MKL_NUM_THREADS"] = str(num_cores)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
print(f"⚙️ 병렬 설정: OMP={num_cores}, MKL={num_cores}")

# ------------------------------------------------
# ✅ 환경 변수 및 모델 초기화
# ------------------------------------------------
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
print("🔍 GEMINI_API_KEY =", "✅ 로드 완료" if os.getenv("GEMINI_API_KEY") else "❌ 없음")

embedder = None
_embedder_lock = threading.Lock()

def _load_embedder_background():
    global embedder
    try:
        with _embedder_lock:
            if embedder is None:
                print("🚀 [Init] 임베딩 모델 백그라운드 로드 시작...")
                t0 = time.time()
                embedder = SentenceTransformer("BAAI/bge-m3")
                print(f"✅ [Init] 임베딩 모델 로드 완료 (전역 1회, {time.time() - t0:.2f}s)")
    except Exception as e:
        print("❌ 임베딩 모델 로드 실패:", e)

threading.Thread(target=_load_embedder_background, daemon=True).start()


# ------------------------------------------------
# 벡터DB 로드 유틸
# ------------------------------------------------
def load_vector_db(folder_path: str, base_name: str):
    t0 = time.time()
    index_path = os.path.join(folder_path, f"{base_name}.faiss")
    meta_path = os.path.join(folder_path, f"{base_name}_metadata.jsonl")
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        raise FileNotFoundError(f"[{base_name}] 파일을 찾을 수 없습니다: {folder_path}")
    index = faiss.read_index(index_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = [json.loads(line.strip()) for line in f]
    print(f"⏱️ [load_vector_db] {base_name} 로드 완료 ({time.time() - t0:.2f}s)")
    return index, metadata


# ------------------------------------------------
# 유사 문서 검색
# ------------------------------------------------
def retrieve_similar_docs(index, metadata, query_vector: np.ndarray, top_k: int = 5):
    t0 = time.time()
    D, I = index.search(query_vector, top_k)
    results = [metadata[idx] for idx in I[0] if 0 <= idx < len(metadata)]
    print(f"⏱️ [retrieve_similar_docs] 검색 완료 ({time.time() - t0:.2f}s)")
    return results


# ------------------------------------------------
# (개선A) 듀얼 쿼리 — 우리 매장 강화 + 유사매장 확장
# ------------------------------------------------
def build_dual_queries(mct_id: str, mode: str) -> List[str]:
    """매장 중심 쿼리 + 유사매장 타겟 전략 쿼리 동시 수행"""
    base_intent = {
        "v1": "고객 분석, 주요 고객층, 상권 특징, 채널 성과",
        "v2": "재방문율, 리텐션, 멤버십, 푸시 전략",
        "v3": "문제 진단, 원인 분석, 개선 아이디어",
    }.get(mode, "매장 분석, 마케팅 전략, 데이터 기반 인사이트")

    query_1 = f"{mct_id} 매장의 {base_intent} 및 주 고객층 강화 전략"  # 우리 매장 중심
    query_2 = (
        "유사 매장에서 성공한 타겟 확장 전략, 연령/성별별 타겟팅, "
        "채널별 성과, 트렌드 기반 마케팅 사례"  # 확장 타겟 참고
    )
    return [query_1, query_2]


# ------------------------------------------------
# (개선B) 현재 매장 페르소나/요약 앵커 생성
# ------------------------------------------------
def build_store_profile_anchor(report_results: List[dict]) -> str:
    """
    report_results 상단에서 summary/persona/visit_mix/loyalty 등을 추출해
    프롬프트 컨텍스트 최상단에 고정(앵커) 삽입.
    """
    if not report_results:
        return ""
    cand = report_results[0]  # 관례상 0번째가 해당 매장/핵심 문맥일 확률이 가장 높음
    fields = []
    if cand.get("summary"):
        fields.append(f"summary: {cand['summary']}")
    if cand.get("persona"):
        fields.append(f"persona: {cand['persona']}")
    if cand.get("visit_mix"):
        fields.append(f"visit_mix: {cand['visit_mix']}")
    if cand.get("loyalty"):
        fields.append(f"loyalty: {cand['loyalty']}")
    if not fields:
        return ""
    return "📊 [현재 매장 데이터 분석]\n" + "\n".join(fields) + "\n"


# ------------------------------------------------
# (보조) 라인 중복 제거
# ------------------------------------------------
def dedupe_lines(text: str) -> str:
    lines, seen, out = text.splitlines(), set(), []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            out.append(ln)
    return "\n".join(out)


# ------------------------------------------------
# 프롬프트 (v1/v2/v3 실행형으로 통일)
# ------------------------------------------------
def get_prompt_for_mode(mode: str, mct_id: str, combined_context: str) -> str:
    """
    v1: 우리 매장 고객층 강화 + 유사매장 기반 확장 타겟을 함께 제시 (채널/문구 포함)
    v2: 재방문 30% 이하 점주 즉시 실행 아이디어
    v3: 요식업 문제 진단 + 개선 아이디어 (문제-해결-문구-근거)
    """
    prompts = {
        # ✅ v1 — 페르소나 앵커 우선, 두 축 병행 (강화 + 확장)
        "v1": f"""
# {mct_id} 고객 특성 기반 채널 추천 & 홍보 실행 가이드 (강화 + 확장)

아래 컨텍스트를 참고하되, **반드시 현재 매장 데이터(📊)를 최우선**으로 판단하세요.
유사 매장 데이터는 참고용이며, 결과에는 **[A] 현재 고객층 강화 전략**과 **[B] 유사매장 기반 확장 타겟 전략**을 함께 제시합니다.

{combined_context}

⚠️ **필수 준수 사항 - 반드시 아래 형식을 정확히 따르세요:**

[A] 현재 고객층 강화 전략

1. [전략 제목]
추천 채널: [채널명, 1줄]
홍보 문구 예시: [타겟 공감 문장, 1줄]
실행 방법: [구체적 행동, 1-2줄]
근거: [유사 사례/데이터, 1줄]

2. [전략 제목]
추천 채널: [채널명, 1줄]
홍보 문구 예시: [타겟 공감 문장, 1줄]
실행 방법: [구체적 행동, 1-2줄]
근거: [유사 사례/데이터, 1줄]

[B] 유사매장 기반 확장 타겟 전략

1. [전략 제목]
추천 채널: [채널명, 1줄]
홍보 문구 예시: [타겟 공감 문장, 1줄]
실행 방법: [구체적 행동, 1-2줄]
근거: [유사 사례/데이터, 1줄]

2. [전략 제목]
추천 채널: [채널명, 1줄]
홍보 문구 예시: [타겟 공감 문장, 1줄]
실행 방법: [구체적 행동, 1-2줄]
근거: [유사 사례/데이터, 1줄]

중요:
- "[A]"와 "[B]" 헤더를 반드시 포함하세요
- "추천 채널:", "홍보 문구 예시:", "실행 방법:", "근거:" 레이블을 정확히 사용하세요
- 각 항목은 반드시 "1.", "2."로 시작하세요
""",

        # ✅ v2 — 점주 즉시 실행 (재방문 30% 이하) - 단기/중기/장기 전략
        "v2": f"""
# 🔁 {mct_id} 재방문율 향상 전략 요약 & 실천 가이드

아래 컨텍스트를 참고하여, **재방문율이 30% 이하인 매장**의 점주가 실행할 수 있는 전략을 단기/중기/장기로 나누어 제시하세요.

{combined_context}

⚠️ **필수 준수 사항 - 반드시 아래 형식을 정확히 따르세요:**

[단기 전략] (1-2주 내 즉시 실행 가능)

1. [전략 제목]
실행 방법: [구체적 행동과 예상 효과, 2-3줄]
근거: [유사 사례/데이터 1줄]

2. [전략 제목]
실행 방법: [구체적 행동과 예상 효과, 2-3줄]
근거: [유사 사례/데이터 1줄]

[중기 전략] (1-2개월 내 실행)

1. [전략 제목]
실행 방법: [구체적 행동과 예상 효과, 2-3줄]
근거: [유사 사례/데이터 1줄]

2. [전략 제목]
실행 방법: [구체적 행동과 예상 효과, 2-3줄]
근거: [유사 사례/데이터 1줄]

[장기 전략] (3개월 이상 지속 실행)

1. [전략 제목]
실행 방법: [구체적 행동과 예상 효과, 2-3줄]
근거: [유사 사례/데이터 1줄]

2. [전략 제목]
실행 방법: [구체적 행동과 예상 효과, 2-3줄]
근거: [유사 사례/데이터 1줄]

중요:
- "[단기 전략]", "[중기 전략]", "[장기 전략]" 헤더를 반드시 포함하세요
- "실행 방법:" 과 "근거:" 레이블을 정확히 사용하세요
- 각 섹션 내 항목은 반드시 "1.", "2."로 시작하세요
- 분석이나 서론 없이 바로 [단기 전략]부터 시작하세요
- 단기는 적은 비용으로 빠르게 실행 가능한 것, 중기는 일정 투자 필요, 장기는 지속적 노력 필요한 전략으로 구분하세요
""",

        # ✅ v3 — 문제 진단 + 개선 (문구 포함)
        "v3": f"""
# 🍽️ {mct_id} 요식업 매장 문제 진단 및 개선 아이디어 가이드

아래 컨텍스트를 참고하되, **현재 매장 상황/고객 특성/현재 매장 업종**을 기준으로 문제를 진단하고, **즉시 실행 가능한 개선 아이디어**를 제시하세요.

{combined_context}

⚠️ **필수 준수 사항 - 반드시 아래 형식을 정확히 따르세요:**

1. [개선 전략 제목]
실행 방법: [문제 진단,개선 행동,예상 효과을 포함하여 2~3줄로 작성하세요.]
근거: [유사 사례/데이터 1줄]

2. [개선 전략 제목]
실행 방법: [문제 진단,개선 행동,예상 효과을 포함하여 2~3줄로 작성하세요.]
근거: [유사 사례/데이터 1줄]

3. [개선 전략 제목]
실행 방법: [문제 진단,개선 행동,예상 효과을 포함하여 2~3줄로 작성하세요.]
근거: [유사 사례/데이터 1줄]



중요:
- "실행 방법:" 과 "근거:" 레이블을 정확히 사용하세요
- 각 항목은 반드시 "1.", "2.", "3."로 시작하세요
- 분석이나 서론 없이 바로 1번부터 시작하세요
- 각 문장은 반드시 줄바꿈(Enter)으로 구분하세요.
""",
    }
    return prompts.get(mode, prompts["v1"])


# ------------------------------------------------
# RAG 리포트 생성
# ------------------------------------------------
def generate_rag_summary(mct_id: str, mode: str = "v1", top_k: int = 5) -> Dict[str, Any]:
    t_start = time.time()
    print(f"🚀 [RAG Triggered] mct_id={mct_id}, mode={mode}")

    try:
        # 1) 벡터DB 로드
        base_dir = os.path.dirname(os.path.abspath(__file__))
        report_folder = os.path.join(base_dir, "vector_dbs", mode)
        shared_folder = os.path.join(base_dir, "vector_dbs", "shared")
        reports_index, reports_meta = load_vector_db(report_folder, "marketing_reports")
        segments_index, segments_meta = load_vector_db(shared_folder, "marketing_segments")

        # 2) 임베딩 준비
        global embedder
        if embedder is None:
            _load_embedder_background()
            while embedder is None:
                time.sleep(0.5)

        # 3) 듀얼 쿼리 검색 (우리 매장 강화 + 유사매장 확장)
        queries = build_dual_queries(mct_id, mode)
        all_reports, all_segments = [], []
        for q in queries:
            q_emb = embedder.encode([q], normalize_embeddings=True)
            q_vec = np.array(q_emb, dtype=np.float32)
            all_reports.extend(retrieve_similar_docs(reports_index, reports_meta, q_vec, top_k))
            all_segments.extend(retrieve_similar_docs(segments_index, segments_meta, q_vec, top_k))

        # 4) (간단) 중복 제거
        def _uniq(items: List[dict], key_priority: List[str]) -> List[dict]:
            seen, out = set(), []
            for i, it in enumerate(items):
                key = None
                for k in key_priority:
                    if it.get(k) is not None:
                        key = f"{k}:{it.get(k)}"
                        break
                if key is None:
                    key = f"idx:{i}"
                if key not in seen:
                    seen.add(key)
                    out.append(it)
            return out

        report_results = _uniq(all_reports, ["id", "chunk_id", "store_code"])
        segment_results = _uniq(all_segments, ["id", "chunk_id", "store_code"])

        if not report_results and not segment_results:
            return {"error": f"'{mct_id}' 관련 데이터를 찾을 수 없습니다."}

        # 5) 페르소나 앵커 구성
        persona_anchor = build_store_profile_anchor(report_results)

        # 6) 컨텍스트 병합 (앵커 → 우리 매장 데이터 → 유사 매장 사례)
        report_context = "\n\n".join([r.get("text", "") for r in report_results])
        segment_context = "\n\n".join([s.get("text", "") for s in segment_results])

        combined_context = ""
        if persona_anchor:
            combined_context += persona_anchor + "\n"
        combined_context += (
            "[매장 주요 분석 및 고객층 강화 데이터]\n"
            + (report_context or "(데이터 없음)") + "\n\n"
            + "[유사 매장 타겟 확장 전략 사례]\n"
            + (segment_context or "(데이터 없음)")
        )
        combined_context = dedupe_lines(combined_context)

        # 7) 프롬프트 생성
        prompt = get_prompt_for_mode(mode, mct_id, combined_context)
        print(f"🧾 [Prompt Info] 글자 수: {len(prompt):,} / 예상 토큰 수: ~{len(prompt)//4}")

        # 8) Gemini 호출
        t4 = time.time()
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        print(f"⏱️ [Gemini 호출 시간] {time.time() - t4:.2f}s")
        print(f"✅ [총 소요시간] {time.time() - t_start:.2f}s")

        return {
            "store_code": mct_id,
            "rag_summary": response.text,
            "references": {"reports": report_results, "segments": segment_results},
        }

    except Exception as e:
        print(f"❌ RAG ERROR: {e}")
        return {"error": str(e), "traceback": traceback.format_exc(limit=2)}
