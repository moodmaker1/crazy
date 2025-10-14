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
load_dotenv()  # .env 파일 로드

# ✅ Gemini API 설정
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ✅ 환경 변수 확인
print("🔍 GEMINI_API_KEY =", os.getenv("GEMINI_API_KEY"))

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
# 벡터 검색
# ------------------------------------------------
def retrieve_similar_docs(index, metadata, query_vector: np.ndarray, top_k: int = 5):
    """쿼리 벡터로 유사 문서 검색"""
    D, I = index.search(query_vector, top_k)
    results = []
    for idx in I[0]:
        if 0 <= idx < len(metadata):
            results.append(metadata[idx])
    return results


# ------------------------------------------------
# RAG 리포트 생성
# ------------------------------------------------
def generate_rag_summary(mct_id: str, mode: str = "v1", top_k: int = 5) -> Dict[str, Any]:
    """
    각 모델(v1/v2/v3)의 reports 벡터DB + 공통 segments 벡터DB를 함께 검색하여
    Gemini-2.5-Flash가 통합 리포트를 생성합니다.
    """
    print(f"🚀 [RAG Triggered] mct_id={mct_id}, mode={mode}")
    try:
        # ✅ analyzer/ 기준으로 vector_dbs 경로 지정
        base_dir = os.path.dirname(os.path.abspath(__file__))  
        report_folder = os.path.join(base_dir, "vector_dbs", mode)
        shared_folder = os.path.join(base_dir, "vector_dbs", "shared")


        print(f"📂 보고서 벡터 경로: {report_folder}")
        print(f"📂 세그먼트 벡터 경로: {shared_folder}")


        # ✅ 각 폴더에서 벡터DB 로드
        reports_index, reports_meta = load_vector_db(report_folder, "marketing_reports")
        segments_index, segments_meta = load_vector_db(shared_folder, "marketing_segments")

        print(f"✅ reports_meta 개수: {len(reports_meta)}")
        print(f"✅ segments_meta 개수: {len(segments_meta)}")

        os.environ["TOKENIZERS_PARALLELISM"] = "false"  # M1 병렬 경고 방지

        # ✅ 임베딩 모델 (BGE-M3)
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer("BAAI/bge-m3")

        # ✅ 쿼리 벡터 변환 부분도 같이 수정해야 함
        query_emb = embedder.encode([mct_id], normalize_embeddings=True)
        query_vector = np.array(query_emb, dtype=np.float32)

        # ✅ 각 벡터DB에서 유사 문서 검색
        report_results = retrieve_similar_docs(reports_index, reports_meta, query_vector, top_k)
        segment_results = retrieve_similar_docs(segments_index, segments_meta, query_vector, top_k)

        if not report_results and not segment_results:
            return {"error": f"'{mct_id}' 관련 데이터를 찾을 수 없습니다."}

        # ------------------------------------------------
        # context 조합
        # ------------------------------------------------
        report_context = "\n\n".join([r["text"] for r in report_results])
        segment_context = "\n\n".join([r["text"] for r in segment_results])

        combined_context = f"""
        [매장 분석 데이터]
        {report_context}

        [마케팅 전략 데이터]
        {segment_context}
        """

        # ------------------------------------------------
        # Gemini 프롬프트
        # ------------------------------------------------
        prompt = f"""
        다음은 '{mct_id}' 매장과 유사한 사례들의 데이터입니다.
        이를 기반으로 AI 마케팅 리포트를 작성하세요.

        {combined_context}

        작성 지침:
        1️⃣ 매장 핵심 요약 (현재 상태를 한 문단으로)
        2️⃣ 데이터 기반 인사이트 (3개 이상)
        3️⃣ 주요 문제점 및 원인
        4️⃣ 개선 전략 (단기/중기/장기별 구체적 실행안 포함)
        5️⃣ 결론 및 우선순위 요약

        ⚙️ 단순 요약이 아니라, 데이터에 기반한 분석적 리포트를 작성하세요.
        """

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)

        print(prompt)

        return {
            "store_code": mct_id,
            "rag_summary": response.text,
            "references": {
                "reports": [r.get("store_name", "N/A") for r in report_results],
                "segments": [r.get("title", r.get("category", "공통 전략")) for r in segment_results],
            },
        }

    except Exception as e:
        print(str(e))
        return {"error": str(e), "traceback": traceback.format_exc(limit=2)}
