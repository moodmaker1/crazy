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
import numpy as np
import faiss
from typing import Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv

# ------------------------------------------------
# 환경 설정
# ------------------------------------------------
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
print("🔍 GEMINI_API_KEY =", "✅ 로드 완료" if os.getenv("GEMINI_API_KEY") else "❌ 없음")

# ------------------------------------------------
# 벡터DB 로드 유틸
# ------------------------------------------------
def load_vector_db(folder_path: str, base_name: str):
    """FAISS 인덱스와 메타데이터 로드"""
    index_path = os.path.join(folder_path, f"{base_name}.faiss")
    meta_path = os.path.join(folder_path, f"{base_name}_metadata.jsonl")
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        raise FileNotFoundError(f"[{base_name}] 파일을 찾을 수 없습니다: {folder_path}")

    index = faiss.read_index(index_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = [json.loads(line.strip()) for line in f]

    return index, metadata

# ------------------------------------------------
# 유사 문서 검색
# ------------------------------------------------
def retrieve_similar_docs(index, metadata, query_vector: np.ndarray, top_k: int = 5):
    """쿼리 벡터로 유사 문서 검색"""
    _, I = index.search(query_vector, top_k)
    return [metadata[i] for i in I[0] if 0 <= i < len(metadata)]

# ------------------------------------------------
# 모드별 프롬프트
# ------------------------------------------------
def get_prompt_for_mode(mode: str, mct_id: str, combined_context: str) -> str:
    """모드(v1/v2/v3)에 따라 다른 프롬프트 반환"""
    prompts = {
        "v1": f"""
        다음은 '{mct_id}' 매장과 유사한 사례들의 **고객 분석 및 마케팅 데이터**입니다.
        이를 기반으로 **AI 마케팅 리포트**를 작성하세요.

        {combined_context}

        작성 지침:
        1️⃣ 매장 핵심 요약 — 고객 구성, 구매 패턴, 주요 상권 특징
        2️⃣ 타겟층별 적합 채널 추천 및 홍보 문구 제안
        """,

        "v2": f"""
        다음은 '{mct_id}' 매장과 유사한 사례들의 **재방문율 분석 데이터**입니다.
        이를 기반으로 **재방문율 향상 전략 리포트**를 작성하세요.

        {combined_context}

        작성 지침:
        1️⃣ 단기/중기/장기 리텐션 전략 구체화
        2️⃣ 매장에서 현재 재방문률을 높일 수 있는 마케팅 아이디어와 근거를 제시
        """,

        "v3": f"""
        다음은 '{mct_id}' 매장과 유사한 **요식업종 가맹점 데이터**입니다.
        이를 기반으로 **문제 진단 및 개선 아이디어**를 제시하세요.

        {combined_context}

        작성 지침:
        1️⃣ 문제별 원인 분석 및 트렌드 연관
        2️⃣ 개선 아이디어 3개 제시 (온/오프라인)
        """,
    }
    return prompts.get(mode, prompts["v1"])

# ------------------------------------------------
# RAG 리포트 생성
# ------------------------------------------------
def generate_rag_summary(mct_id: str, mode: str = "v1", top_k: int = 5) -> Dict[str, Any]:
    """Gemini 기반 RAG 요약 리포트 생성"""
    print(f"🚀 [RAG Triggered] mct_id={mct_id}, mode={mode}")

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        report_folder = os.path.join(base_dir, "vector_dbs", mode)
        shared_folder = os.path.join(base_dir, "vector_dbs", "shared")

        # ✅ 벡터DB 로드
        reports_index, reports_meta = load_vector_db(report_folder, "marketing_reports")
        segments_index, segments_meta = load_vector_db(shared_folder, "marketing_segments")

        # ✅ 임베딩 생성
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer("BAAI/bge-m3")
        query_emb = embedder.encode([mct_id], normalize_embeddings=True)
        query_vector = np.array(query_emb, dtype=np.float32)

        # ✅ 유사 문서 검색
        report_results = retrieve_similar_docs(reports_index, reports_meta, query_vector, top_k)
        segment_results = retrieve_similar_docs(segments_index, segments_meta, query_vector, top_k)

        if not report_results and not segment_results:
            return {"error": f"'{mct_id}' 관련 데이터를 찾을 수 없습니다."}

        # ✅ 컨텍스트 구성
        report_context = "\n\n".join([r.get("text", "") for r in report_results])
        segment_context = "\n\n".join([r.get("text", "") for r in segment_results])
        combined_context = f"[매장 분석 데이터]\n{report_context}\n\n[마케팅 전략 데이터]\n{segment_context}"

        # ✅ 프롬프트 생성
        prompt = get_prompt_for_mode(mode, mct_id, combined_context)

        # ✅ Gemini 호출
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)

        return {
            "store_code": mct_id,
            "rag_summary": response.text,
            "references": {
                "reports": report_results,
                "segments": segment_results,
            },
        }

    except Exception as e:
        print("❌ RAG ERROR:", e)
        return {"error": str(e), "traceback": traceback.format_exc(limit=2)}