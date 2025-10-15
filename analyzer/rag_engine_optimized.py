"""
rag_engine.py
-------------
Gemini-2.5-Flash + FAISS 기반 RAG 엔진 (max_output_tokens 테스트 버전)
- 프롬프트 구조 유지
- MPS + FP16
- Timeout 없음
- Context 압축 + 캐시 유지
- 출력 길이 제한 (max_output_tokens=500)
"""

import os
import json
import time
import traceback
import hashlib
import numpy as np
import faiss
from typing import Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# ------------------------------------------------
# ✅ 기본 설정
# ------------------------------------------------
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
print("🔍 GEMINI_API_KEY =", "✅ 로드 완료" if os.getenv("GEMINI_API_KEY") else "❌ 없음")

# ------------------------------------------------
# ✅ 임베딩 모델 (전역 1회 로드)
# ------------------------------------------------
print("🚀 [Init] 임베딩 모델 로드 시작...")
t0 = time.time()
try:
    embedder = SentenceTransformer("BAAI/bge-m3", device="mps")
    if hasattr(embedder, "half"):
        embedder = embedder.half()
    print(f"✅ [Init] 임베딩 모델 로드 완료 ({time.time() - t0:.2f}s, device=MPS)")
except Exception as e:
    embedder = None
    print("❌ 임베딩 모델 로드 실패:", e)

# ------------------------------------------------
# ✅ 캐시 초기화
# ------------------------------------------------
_cache = {}

def get_cache_key(mct_id: str, mode: str, combined_context: str) -> str:
    return f"{mct_id}-{mode}-{hashlib.md5(combined_context.encode()).hexdigest()}"


# ------------------------------------------------
# 벡터DB 로드
# ------------------------------------------------
def load_vector_db(folder_path: str, base_name: str):
    t = time.time()
    index_path = os.path.join(folder_path, f"{base_name}.faiss")
    meta_path = os.path.join(folder_path, f"{base_name}_metadata.jsonl")

    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        raise FileNotFoundError(f"[{base_name}] 파일을 찾을 수 없습니다: {folder_path}")

    index = faiss.read_index(index_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = [json.loads(line.strip()) for line in f]

    print(f"⏱️ [load_vector_db] {base_name} 로드 완료 ({time.time() - t:.2f}s)")
    return index, metadata


# ------------------------------------------------
# 벡터 검색
# ------------------------------------------------
def retrieve_similar_docs(index, metadata, query_vector: np.ndarray, top_k: int = 5):
    t = time.time()
    D, I = index.search(query_vector, top_k)
    results = [metadata[idx] for idx in I[0] if 0 <= idx < len(metadata)]
    print(f"⏱️ [retrieve_similar_docs] 검색 완료 ({time.time() - t:.2f}s)")
    return results


# ------------------------------------------------
# ✅ 텍스트 압축
# ------------------------------------------------
def compact_text(text: str) -> str:
    return " ".join(text.split())


# ------------------------------------------------
# ✅ 프롬프트 생성
# ------------------------------------------------
def get_prompt_for_mode(mode: str, mct_id: str, combined_context: str) -> str:
    prompts = {
        "v1": f"""
        다음은 '{mct_id}' 매장과 유사한 사례들의 **고객 분석 및 마케팅 데이터**입니다.
        이를 기반으로 **AI 마케팅 리포트**를 작성하세요.

        {combined_context}

        작성 지침:
        1️⃣ 매장 핵심 요약 — 고객 구성, 구매 패턴, 주요 상권 특징을 요약  
        2️⃣ 데이터 기반 인사이트 — 최소 3개, 각 인사이트마다 **데이터 근거**를 괄호로 명시  
        3️⃣ 타겟층별로 적합한 마케팅 채널 추천  
        4️⃣ 추천 채널별 맞춤 홍보 문구 제안  
        5️⃣ 결론 — 어떤 채널이 ROI 대비 가장 효과적인지 제시
        """,

        "v2": f"""
        다음은 '{mct_id}' 매장과 유사한 사례들의 **재방문율 분석 데이터**입니다.
        이 데이터를 기반으로 **재방문율 향상 전략 보고서**를 작성하세요.

        {combined_context}
        """,

        "v3": f"""
        다음은 '{mct_id}' 매장과 유사한 **요식업종 가맹점 데이터**입니다.
        이 데이터를 기반으로 **현재 가장 큰 문제점과 이를 보완할 마케팅 아이디어**를 제시하세요.

        {combined_context}
        """,

        "default": f"""
        다음은 '{mct_id}' 매장과 유사한 사례들의 데이터입니다.
        이를 기반으로 AI 마케팅 리포트를 작성하세요.

        {combined_context}
        """
    }
    return prompts.get(mode, prompts["default"])


# ------------------------------------------------
# ✅ Gemini 호출 (출력 500토큰 제한)
# ------------------------------------------------
model = genai.GenerativeModel("gemini-2.5-flash")

def generate_with_retry(prompt: str):
    """Gemini 호출 — 제한 없이 끝까지 기다리되, 출력만 500토큰 제한"""
    for attempt in range(2):
        try:
            return model.generate_content(
                prompt,
                generation_config={"max_output_tokens": 500}
            )
        except Exception as e:
            print(f"⚠️ Gemini 호출 재시도 중... ({attempt+1}/2) 이유: {e}")
            time.sleep(2)
    raise RuntimeError("Gemini 호출 실패")


# ------------------------------------------------
# ✅ RAG 리포트 생성
# ------------------------------------------------
def generate_rag_summary(mct_id: str, mode: str = "v1", top_k: int = 5) -> Dict[str, Any]:
    print(f"\n🚀 [RAG Triggered] mct_id={mct_id}, mode={mode}")
    t_start = time.time()

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))  
        report_folder = os.path.join(base_dir, "vector_dbs", mode)
        shared_folder = os.path.join(base_dir, "vector_dbs", "shared")

        # 1️⃣ 벡터DB 로드
        t1 = time.time()
        reports_index, reports_meta = load_vector_db(report_folder, "marketing_reports")
        segments_index, segments_meta = load_vector_db(shared_folder, "marketing_segments")
        print(f"⏱️ [1] 벡터DB 로드 시간: {time.time() - t1:.2f}s")

        # 2️⃣ 임베딩 생성
        t2 = time.time()
        query_emb = embedder.encode([mct_id], normalize_embeddings=True, convert_to_numpy=True)
        query_vector = np.array(query_emb, dtype=np.float32)
        print(f"⏱️ [2] 임베딩 생성 시간: {time.time() - t2:.2f}s")

        # 3️⃣ 유사 문서 검색
        t3 = time.time()
        report_results = retrieve_similar_docs(reports_index, reports_meta, query_vector, top_k)
        segment_results = retrieve_similar_docs(segments_index, segments_meta, query_vector, top_k)
        print(f"⏱️ [3] 검색 전체 시간: {time.time() - t3:.2f}s")

        # 4️⃣ 컨텍스트 구성
        t4 = time.time()
        report_context = compact_text("\n\n".join([r.get("text", "") for r in report_results]))
        segment_context = compact_text("\n\n".join([r.get("text", "") for r in segment_results]))
        combined_context = f"[매장 분석 데이터]\n{report_context}\n\n[마케팅 전략 데이터]\n{segment_context}"
        print(f"⏱️ [4] 컨텍스트 구성 시간: {time.time() - t4:.2f}s")

        # 5️⃣ 프롬프트 생성
        prompt = get_prompt_for_mode(mode, mct_id, combined_context)
        prompt_len = len(prompt)
        est_tokens = int(prompt_len / 4)
        print(f"🧾 [Prompt Info] 글자 수: {prompt_len:,} / 예상 토큰 수: 약 {est_tokens:,}")

        # 6️⃣ 캐시 조회
        cache_key = get_cache_key(mct_id, mode, combined_context)
        if cache_key in _cache:
            print(f"⚡ [CACHE HIT] '{mct_id}' ({mode}) 결과 재사용")
            return _cache[cache_key]

        # 7️⃣ Gemini 호출 (출력 제한 500토큰)
        t5 = time.time()
        response = generate_with_retry(prompt)
        print(f"⏱️ [5] Gemini 호출 시간: {time.time() - t5:.2f}s")

        total_time = time.time() - t_start
        print(f"✅ [총 소요시간] {total_time:.2f}s")

        result = {
            "store_code": mct_id,
            "rag_summary": response.text,
            "references": {"reports": report_results, "segments": segment_results},
            "timing": {
                "vector_load": round(time.time() - t1, 2),
                "embedding": round(time.time() - t2, 2),
                "search": round(time.time() - t3, 2),
                "context": round(time.time() - t4, 2),
                "gemini": round(time.time() - t5, 2),
                "total": round(total_time, 2)
            },
            "prompt_info": {
                "length": prompt_len,
                "estimated_tokens": est_tokens,
                "max_output_tokens": 500
            }
        }

        # 8️⃣ 캐시 저장
        _cache[cache_key] = result
        print(f"💾 [CACHE STORE] '{mct_id}' ({mode}) 결과 캐싱 완료")

        return result

    except Exception as e:
        print("❌ RAG ERROR:", e)
        return {"error": str(e), "traceback": traceback.format_exc(limit=2)}
