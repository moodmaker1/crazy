"""
rag_engine.py
-------------
Gemini-2.5-Flash + FAISS 기반 RAG 엔진
- 주 고객층 강화 전략 + 유사매장 타겟 확장 전략 병합형 분석
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

# ------------------------------------------------
# ✅ 병렬 설정
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
# 벡터DB 로드
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
# (개선A) 듀얼 쿼리 — 주 고객층 + 유사매장 타겟 강화
# ------------------------------------------------
def build_dual_queries(mct_id: str, mode: str) -> List[str]:
    """매장 중심 쿼리 + 유사매장 타겟 전략 쿼리 동시 수행"""
    base_intent = {
        "v1": "고객 분석, 주요 고객층, 상권 특징, 채널 성과",
        "v2": "재방문율, 리텐션, 멤버십, 푸시 전략",
        "v3": "문제 진단, 원인 분석, 개선 아이디어",
    }.get(mode, "매장 분석, 마케팅 전략, 데이터 기반 인사이트")

    query_1 = f"{mct_id} 매장의 {base_intent} 및 주 고객층 강화 전략"
    query_2 = (
        "유사 매장에서 성공한 고객층 재정의 및 신규 타겟 확장 전략, "
        "연령대/성별별 타겟팅, 채널별 성과, 트렌드 기반 마케팅 사례"
    )
    return [query_1, query_2]


# ------------------------------------------------
# 프롬프트 생성기
# ------------------------------------------------
def get_prompt_for_mode(mode: str, mct_id: str, combined_context: str) -> str:
    """유사매장 타겟 확장 지시 추가"""
    prompts = {
        "v1": f"""
        다음은 '{mct_id}' 매장과 유사한 사례들의 고객 분석 및 마케팅 데이터입니다.
        이를 기반으로 **AI 마케팅 리포트**를 작성하세요.

        {combined_context}

        작성 지침:
        1️⃣ 매장 핵심 요약 — 고객 구성, 구매 패턴, 주요 상권 특징
        2️⃣ 주 고객층 강화 전략 제시
        3️⃣ **유사 매장의 고객층 분석 결과를 참고하여 새로운 타겟 고객층을 제시**
        4️⃣ 각 타겟별로 적합한 마케팅 채널 및 홍보 문구를 구체화
        """,

        "v2": f"""
        '{mct_id}' 매장의 재방문율 분석 결과와 유사매장 사례를 참고해
        재방문율 향상 전략을 제시하세요.

        {combined_context}

        작성 지침:
        - 단기/중기/장기 리텐션 전략 제시
        - 유사 매장의 성공 패턴을 인용해 실천 가능한 아이디어 제시
        """,

        "v3": f"""
        '{mct_id}' 매장과 유사한 요식업종 가맹점 데이터를 기반으로
        문제점과 개선 아이디어를 제시하세요.

        {combined_context}

        작성 지침:
        - 문제 원인 분석 + 트렌드 연계
        - 유사매장의 개선 성공 사례를 참고하여 해결 전략 작성
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
        base_dir = os.path.dirname(os.path.abspath(__file__))
        report_folder = os.path.join(base_dir, "vector_dbs", mode)
        shared_folder = os.path.join(base_dir, "vector_dbs", "shared")
        reports_index, reports_meta = load_vector_db(report_folder, "marketing_reports")
        segments_index, segments_meta = load_vector_db(shared_folder, "marketing_segments")

        global embedder
        if embedder is None:
            _load_embedder_background()
            while embedder is None:
                time.sleep(0.5)

        # ✅ 듀얼 쿼리 수행 (주 고객층 + 유사매장)
        queries = build_dual_queries(mct_id, mode)
        all_reports, all_segments = [], []
        for q in queries:
            q_emb = embedder.encode([q], normalize_embeddings=True)
            q_vec = np.array(q_emb, dtype=np.float32)
            all_reports.extend(retrieve_similar_docs(reports_index, reports_meta, q_vec, top_k))
            all_segments.extend(retrieve_similar_docs(segments_index, segments_meta, q_vec, top_k))

        # ✅ 중복 제거
        report_results = list({
            r.get("id") or r.get("chunk_id") or r.get("store_code") or f"r{i}": r
            for i, r in enumerate(all_reports)
        }.values())
        segment_results = list({
            s.get("id") or s.get("chunk_id") or s.get("store_code") or f"s{i}": s
            for i, s in enumerate(all_segments)
        }.values())

        if not report_results and not segment_results:
            return {"error": f"'{mct_id}' 관련 데이터를 찾을 수 없습니다."}

        # ✅ 컨텍스트 섹션 구분 (A: 매장, B: 유사매장)
        report_context = "\n\n".join([r.get("text", "") for r in report_results])
        segment_context = "\n\n".join([s.get("text", "") for s in segment_results])

        combined_context = f"""
        [매장 주요 분석 및 고객층 강화 데이터]
        {report_context}

        [유사 매장 타겟 확장 전략 사례]
        {segment_context}
        """

        # ✅ 프롬프트 생성
        prompt = get_prompt_for_mode(mode, mct_id, combined_context)
        print(f"🧾 [Prompt Info] 글자 수: {len(prompt):,} / 예상 토큰 수: {len(prompt)//4}")

        # ✅ Gemini 호출
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
