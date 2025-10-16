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

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import faiss
from typing import Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv

# ✅ 환경 변수 로드
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
    print(f"🚀 [RAG Triggered] mct_id={mct_id}, mode={mode}")

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))  
        report_folder = os.path.join(base_dir, "vector_dbs", mode)
        shared_folder = os.path.join(base_dir, "vector_dbs", "shared")

        # ✅ 벡터DB 로드
        reports_index, reports_meta = load_vector_db(report_folder, "marketing_reports")
        segments_index, segments_meta = load_vector_db(shared_folder, "marketing_segments")

        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        # ✅ 임베딩 모델 (BGE-M3)
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer("BAAI/bge-m3")

        query_emb = embedder.encode([mct_id], normalize_embeddings=True)
        query_vector = np.array(query_emb, dtype=np.float32)

        # ✅ 유사 문서 검색
        report_results = retrieve_similar_docs(reports_index, reports_meta, query_vector, top_k)
        segment_results = retrieve_similar_docs(segments_index, segments_meta, query_vector, top_k)

        if not report_results and not segment_results:
            return {"error": f"'{mct_id}' 관련 데이터를 찾을 수 없습니다."}

        # ✅ context 구성
        report_context = "\n\n".join([r.get("text", "") for r in report_results])
        segment_context = "\n\n".join([r.get("text", "") for r in segment_results])
        combined_context = f"[매장 분석 데이터]\n{report_context}\n\n[마케팅 전략 데이터]\n{segment_context}"

        # ✅ 프롬프트 생성 함수 호출
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
