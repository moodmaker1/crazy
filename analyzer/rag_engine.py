"""
rag_engine.py
-------------
Gemini-2.5-Flash + FAISS 기반 RAG 엔진
모델별 marketing_reports 벡터DB + 공통 marketing_segments 벡터DB를 병합하여
AI 기반 마케팅 리포트를 생성합니다.
"""

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

num_cores = min(4, multiprocessing.cpu_count())  # 최대 4스레드까지만 허용
os.environ["OMP_NUM_THREADS"] = str(num_cores)
os.environ["MKL_NUM_THREADS"] = str(num_cores)
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # SentenceTransformer 병렬 토크나이저 중복 방지

print(f"⚙️ 병렬 설정: OMP={num_cores}, MKL={num_cores}")

# ✅ 환경 변수 로드
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
print("🔍 GEMINI_API_KEY =", "✅ 로드 완료" if os.getenv("GEMINI_API_KEY") else "❌ 없음")


# ------------------------------------------------
# ✅ 임베딩 모델을 전역으로 1회 로드 (백그라운드)
# ------------------------------------------------
embedder = None
_embedder_lock = threading.Lock()

def _load_embedder_background():
    global embedder
    try:
        with _embedder_lock:
            if embedder is None:
                print("🚀 [Init] 임베딩 모델 백그라운드 로드 시작...")
                t0 = time.time()
                model = SentenceTransformer("BAAI/bge-m3")
                embedder = model
                print(f"✅ [Init] 임베딩 모델 로드 완료 (전역 1회, {time.time() - t0:.2f}s)")
    except Exception as e:
        print("❌ 임베딩 모델 로드 실패:", e)

# 백그라운드에서 자동 로드
threading.Thread(target=_load_embedder_background, daemon=True).start()


# ------------------------------------------------
# 벡터DB 로드 유틸
# ------------------------------------------------
def load_vector_db(folder_path: str, base_name: str):
    """FAISS 인덱스와 메타데이터 로드"""
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
# 벡터 검색
# ------------------------------------------------
def retrieve_similar_docs(index, metadata, query_vector: np.ndarray, top_k: int = 5):
    """쿼리 벡터로 유사 문서 검색"""
    t0 = time.time()
    D, I = index.search(query_vector, top_k)
    results = [metadata[idx] for idx in I[0] if 0 <= idx < len(metadata)]
    print(f"⏱️ [retrieve_similar_docs] 검색 완료 ({time.time() - t0:.2f}s)")
    return results


# ------------------------------------------------
# (개선1) 쿼리문 구성: mct_id만 쓰지 말고 의미 있는 문장으로 확장
# ------------------------------------------------
def build_query_text(mct_id: str, mode: str) -> str:
    """매장코드 단독 대신 의미적 쿼리문으로 확장하여 임베딩 품질 개선"""
    # 모드별 검색 의도 문구 가미
    intent = {
        "v1": "고객 분석, 구매 패턴, 상권 특징, 채널 성과",
        "v2": "재방문율, 리텐션, 영향 요인, 쿠폰/멤버십/푸시",
        "v3": "핵심 문제점, 원인 분석, 마케팅 아이디어, 기대효과",
    }.get(mode, "매장 분석, 마케팅 전략, 데이터 기반 인사이트")
    return f"매장코드 {mct_id} 관련 {intent} 데이터와 유사 사례 요약"


# ------------------------------------------------
# (개선2) 보고서-세그먼트 정렬: 컨텍스트를 짝지어 배치
# ------------------------------------------------
def align_reports_with_segments(
    report_docs: List[dict], segment_docs: List[dict], max_pairs: int = 5
) -> List[Tuple[dict, dict, float]]:
    """
    상위 report/segment 결과를 임베딩 재계산으로 유사도 스코어링 후 매칭.
    greedy로 높은 유사도부터 짝을 만들어 최대 max_pairs 페어 반환.
    """
    if not report_docs or not segment_docs or embedder is None:
        return []

    # 텍스트 추출
    r_texts = [r.get("text", "")[:2000] for r in report_docs]  # 과도한 길이 방지
    s_texts = [s.get("text", "")[:2000] for s in segment_docs]

    # 임베딩
    r_emb = embedder.encode(r_texts, normalize_embeddings=True)
    s_emb = embedder.encode(s_texts, normalize_embeddings=True)

    # 유사도 행렬 (cosine)
    sim = np.matmul(r_emb, s_emb.T)  # (R x S)

    pairs = []
    used_r = set()
    used_s = set()

    # greedy 매칭
    while len(pairs) < max_pairs:
        # 아직 안 쓴 index들만 고려
        mask = np.full_like(sim, -1e9)
        for i in range(sim.shape[0]):
            if i in used_r: continue
            for j in range(sim.shape[1]):
                if j in used_s: continue
                mask[i, j] = sim[i, j]
        i_max, j_max = np.unravel_index(np.argmax(mask), mask.shape)
        if mask[i_max, j_max] < -1e8:
            break  # 더 이상 매칭할 게 없음
        score = float(sim[i_max, j_max])
        pairs.append((report_docs[i_max], segment_docs[j_max], score))
        used_r.add(i_max)
        used_s.add(j_max)

    return pairs


# ------------------------------------------------
# (개선3) 프롬프트 압축: 라인 단위 중복 제거
# ------------------------------------------------
def dedupe_lines(text: str) -> str:
    lines = text.splitlines()
    seen = set()
    out = []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            out.append(ln)
    return "\n".join(out)


# ------------------------------------------------
# 프롬프트 생성기 (모드별 로직 분리)
# ------------------------------------------------
def get_prompt_for_mode(mode: str, mct_id: str, combined_context: str) -> str:
    """모드(v1/v2/v3)에 따라 다른 프롬프트 반환"""
    prompts = {
        "v1": f"""
        다음은 '{mct_id}' 매장과 유사한 사례들의 **고객 분석 및 마케팅 데이터**입니다.
        이를 기반으로 **AI 마케팅 리포트**를 작성하세요.

        {combined_context}

        작성 지침:
        1️⃣ 매장 핵심 요약 — 고객 구성, 구매 패턴, 주요 상권 특징을 요약  
        2️⃣ 데이터 기반 인사이트 — 최소 3개, 각 인사이트마다 **데이터 근거**를 괄호로 명시  
            예: "10~20대 여성 고객 비중이 높음 (출처: 챔스*** 리포트, +3.7pp)"
        3️⃣ 타겟층별로 적합한 마케팅 채널 추천 (예: 인스타그램, 네이버 블로그, 배달앱 등)
        4️⃣ 추천 채널별 맞춤 홍보 문구 제안  
        5️⃣ 결론 — 어떤 채널이 ROI 대비 가장 효과적인지 제시

        ⚙️ 작성 규칙:
        - 모든 근거는 [매장 분석 데이터] 또는 [마케팅 전략 데이터]에서 인용해야 함
        - 인용 시 “(출처: 매장코드 또는 세그먼트명)” 형태로 표시
        - 결과는 한국어로 작성
        """,

        "v2": f"""
        다음은 '{mct_id}' 매장과 유사한 사례들의 **재방문율 분석 데이터**입니다.
        이 데이터를 기반으로 **재방문율 향상 전략 보고서**를 작성하세요.

        {combined_context}

        작성 지침:
        1️⃣ 현재 재방문율 상태 요약 — 수치와 비교 기준 포함  
        2️⃣ 재방문율에 영향을 미친 요인 3가지 이상 제시 (각 요인별 데이터 근거 명시)
        3️⃣ 단기 / 중기 / 장기별 리텐션 전략을 구체적으로 제시  
            - 단기: 쿠폰, 이벤트, 앱 푸시  
            - 중기: 멤버십, 고객 주기 최적화  
            - 장기: 충성고객 관리, 커뮤니티 강화
        4️⃣ 각 전략의 예상 효과를 수치나 사례로 제시  
        5️⃣ 결론 — 어떤 전략이 ROI 기준으로 가장 효율적인지 제시

        ⚙️ 작성 규칙:
        - 모든 근거는 [매장 분석 데이터] 또는 [마케팅 전략 데이터]에서 인용해야 함
        - 인용 시 “(출처: 매장코드 또는 세그먼트명)” 형태로 표시
        - 결과는 한국어로 작성
        """,

        "v3": f"""
        다음은 '{mct_id}' 매장과 유사한 **요식업종 가맹점 데이터**입니다.
        이 데이터를 기반으로 **현재 가장 큰 문제점과 이를 보완할 마케팅 아이디어**를 제시하세요.

        {combined_context}

        작성 지침:
        1️⃣ 요식업종 매장의 핵심 문제점 3개를 도출하고 각 문제의 **데이터 근거**를 명시  
            예: "점심 매출 집중률 높음 (출처: 91BA22FC44, +42%)"
        2️⃣ 문제별 원인을 분석하고, 고객군/상권/트렌드와 연관지어 설명  
        3️⃣ 각 문제를 해결하기 위한 **마케팅 아이디어**를 제시 (온라인/오프라인 포함)  
            - 예: 메뉴 리뉴얼, 타겟형 광고, 지역 제휴, 배달 최적화 등  
        4️⃣ 각 아이디어의 기대 효과를 데이터 기반으로 추정  
        5️⃣ 결론 — 어떤 아이디어가 단기성과 vs 장기브랜딩 측면에서 우선순위가 높은지 정리

        ⚙️ 작성 규칙:
        - 반드시 데이터 기반으로 논리적으로 작성  
        - 인용 시 “(출처: 매장코드 또는 세그먼트명)” 형태로 표시  
        - 결과는 한국어로 작성
        """,

        "default": f"""
        다음은 '{mct_id}' 매장과 유사한 사례들의 데이터입니다.
        이를 기반으로 AI 마케팅 리포트를 작성하세요.

        {combined_context}

        작성 지침:
        1️⃣ 매장 핵심 요약  
        2️⃣ 데이터 기반 인사이트  
        3️⃣ 주요 문제점 및 원인  
        4️⃣ 개선 전략  
        5️⃣ 결론 및 요약
        """
    }
    return prompts.get(mode, prompts["default"])


# ------------------------------------------------
# RAG 리포트 생성
# ------------------------------------------------
def generate_rag_summary(mct_id: str, mode: str = "v1", top_k: int = 5) -> Dict[str, Any]:
    t_start = time.time()
    print(f"🚀 [RAG Triggered] mct_id={mct_id}, mode={mode}")

    try:
        # 1️⃣ 벡터DB 로드
        t0 = time.time()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        report_folder = os.path.join(base_dir, "vector_dbs", mode)
        shared_folder = os.path.join(base_dir, "vector_dbs", "shared")
        reports_index, reports_meta = load_vector_db(report_folder, "marketing_reports")
        segments_index, segments_meta = load_vector_db(shared_folder, "marketing_segments")
        print(f"⏱️ [1] 벡터DB 로드 시간: {time.time() - t0:.2f}s")

        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        # 2️⃣ 임베딩 모델 확인
        t1 = time.time()
        global embedder
        if embedder is None:
            print("⚙️ 임베딩 모델 초기화 중... (백그라운드 로드 지연)")
            _load_embedder_background()
            while embedder is None:
                time.sleep(0.5)
        print(f"⏱️ [2] 임베딩 준비 시간: {time.time() - t1:.2f}s")

        # 3️⃣ 쿼리 임베딩 생성 (개선: 의미 기반 쿼리문 사용)
        t2 = time.time()
        query_text = build_query_text(mct_id, mode)
        query_emb = embedder.encode([query_text], normalize_embeddings=True)
        query_vector = np.array(query_emb, dtype=np.float32)
        print(f"⏱️ [3] 임베딩 생성 시간: {time.time() - t2:.2f}s")
        print(f"🔎 [Query] {query_text}")

        # 4️⃣ 유사 문서 검색
        t3 = time.time()
        report_results = retrieve_similar_docs(reports_index, reports_meta, query_vector, top_k)
        segment_results = retrieve_similar_docs(segments_index, segments_meta, query_vector, top_k)
        print(f"⏱️ [4] 검색 전체 시간: {time.time() - t3:.2f}s")

        if not report_results and not segment_results:
            return {"error": f"'{mct_id}' 관련 데이터를 찾을 수 없습니다."}

        # 5️⃣ 컨텍스트 구성 (개선: 보고서-세그먼트 정렬 + 중복 제거)
        pairs = align_reports_with_segments(report_results, segment_results, max_pairs=top_k)
        if pairs:
            # 페어 단위로 교차 배치 → 모델이 연관성을 더 잘 학습
            blocks = []
            for i, (r, s, sc) in enumerate(pairs, 1):
                r_src = r.get("source", r.get("id", "reports"))
                s_src = s.get("source", s.get("id", "segments"))
                blocks.append(
                    f"[매장 분석 데이터 #{i} | 출처: {r_src}]\n{r.get('text','')}\n\n"
                    f"[연관 마케팅 전략 데이터 #{i} | 출처: {s_src} | 유사도: {sc:.3f}]\n{s.get('text','')}\n"
                )
            combined_context = "\n\n".join(blocks)
        else:
            # 페어링 실패 시 기존 방식으로 폴백
            report_context = "\n\n".join([r.get("text", "") for r in report_results])
            segment_context = "\n\n".join([r.get("text", "") for r in segment_results])
            combined_context = f"[매장 분석 데이터]\n{report_context}\n\n[마케팅 전략 데이터]\n{segment_context}"

        # 라인 중복 제거로 프롬프트 압축
        before_len = len(combined_context)
        combined_context = dedupe_lines(combined_context)
        after_len = len(combined_context)
        if after_len < before_len:
            print(f"🧹 [Context Dedupe] {before_len} → {after_len} chars (-{before_len - after_len})")

        prompt = get_prompt_for_mode(mode, mct_id, combined_context)
        print(f"🧾 [Prompt Info] 글자 수: {len(prompt):,} / 예상 토큰 수: 약 {len(prompt)//4}")

        # 6️⃣ Gemini 호출 (원본 유지)
        t4 = time.time()
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        print(f"⏱️ [5] Gemini 호출 시간: {time.time() - t4:.2f}s")

        print(f"✅ [총 소요시간] {time.time() - t_start:.2f}s")
        return {
            "store_code": mct_id,
            "rag_summary": response.text,
            "references": {"reports": report_results, "segments": segment_results},
        }

    except Exception as e:
        print(f"❌ RAG ERROR: {e}")
        print(f"⏱️ [총 실패까지 소요시간] {time.time() - t_start:.2f}s")
        return {"error": str(e), "traceback": traceback.format_exc(limit=2)}
