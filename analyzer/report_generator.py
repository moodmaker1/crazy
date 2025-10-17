import traceback
import concurrent.futures

# -----------------------------
# 내부 모듈 import
# -----------------------------
from analyzer.rag_engine import generate_rag_summary
from experiments._0_final.store_status import get_store_status_with_insights
from experiments._1_final.report_generator import generate_marketing_report1
from experiments._2_final.report_generator2 import generate_marketing_report2
from experiments._3_final.report_generator3 import generate_marketing_report3
from experiments._4_final.delivery_prediction import predict_delivery
from experiments.keywords.keyword_generator import generate_keyword_trend_report


# -----------------------------
# 업종 추출 헬퍼
# -----------------------------
def get_industry_from_store(mct_id: str) -> str:
    """
    매장 코드로 업종명을 추출하는 헬퍼 함수
    """
    try:
        info = get_store_status_with_insights(mct_id)
        if not info:
            return "기타"
        return info.get("업종분류") or info.get("industry") or "기타"
    except Exception as e:
        print(f"⚠️ 업종 조회 실패: {e}")
        return "기타"


# -----------------------------
# 마케팅 리포트 메인
# -----------------------------
def generate_marketing_report(mct_id: str, mode: str = "v1", rag: bool = True):
    """
    AI 마케팅 리포트 생성 게이트웨이 (자동 라우팅 + 병렬 RAG/키워드)
    """
    try:
        base_result = None

        # --------------------------------------
        # ① 내부 분석 라우팅
        # --------------------------------------
        if mode == "v0":
            base_result = get_store_status_with_insights(mct_id)
        elif mode == "v1":
            base_result = generate_marketing_report1(mct_id)
        elif mode == "v2":
            base_result = generate_marketing_report2(mct_id)
        elif mode == "v3":
            base_result = generate_marketing_report3(mct_id)
        elif mode == "v4":
            base_result = predict_delivery(mct_id)
            if base_result is None:
                return {"error": "해당 가맹점을 찾을 수 없거나 이미 배달을 운영 중입니다."}
            # 배달 예측 리포트 포맷 정리
            base_result = {
                "store_code": base_result.get("store_code"),
                "store_name": base_result.get("store_name"),
                "store_type": base_result.get("store_type"),
                "district": base_result.get("district"),
                "area": base_result.get("area"),
                "emoji": base_result.get("emoji", "📦"),
                "success_prob": base_result.get("success_prob", 0.0),
                "fail_prob": 100 - base_result.get("success_prob", 0.0),
                "status": base_result.get("level", "-"),
                "message": base_result.get("summary", ""),
                "recommendation": base_result.get("recommendation", ""),
                "reasons": base_result.get("reasons", []),
                "interpret_text": base_result.get("interpret_text", "")
            }
        else:
            return {"error": f"지원되지 않는 모드입니다: {mode}"}

        # --------------------------------------
        # ② RAG 비활성 모드 → 내부 분석 결과만 반환
        # --------------------------------------
        if not rag:
            return base_result

        # --------------------------------------
        # ③ RAG + Keyword Trend 병렬 실행 (모든 모드 적용)
        # --------------------------------------
        industry = (base_result.get("업종분류")or base_result.get("store_type")or get_industry_from_store(mct_id)or "기타")





        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # ✅ v3일 때만 업종(store_type) 전달
            if mode == "v3":
                futures = {
                    "rag": executor.submit(generate_rag_summary, mct_id, mode, 5, industry),
                    "trend": executor.submit(generate_keyword_trend_report, industry)
                }
            else:
                futures = {
                    "rag": executor.submit(generate_rag_summary, mct_id, mode),
                    "trend": executor.submit(generate_keyword_trend_report, industry)
                }

            rag_output = futures["rag"].result()
            trend_output = futures["trend"].result()

        rag_text = rag_output.get("rag_summary", "")
        keyword_top10 = trend_output.get("TOP10", [])

        # --------------------------------------
        # ④ 결과 병합
        # --------------------------------------
        result = {
            "store_code": mct_id,
            "mode": mode,
            "store_name": base_result.get("store_name", ""),
            "status": base_result.get("status", ""),
            "message": base_result.get("message")
                or base_result.get("status_detail", "")
                or "",
            "analysis": base_result.get("analysis", ""),
            "recommendations": base_result.get("recommendations", ""),
            "metadata": base_result.get("metadata", {}),
            "revisit_rate": base_result.get("revisit_rate", None),
            "rag_summary": rag_text,
            "references": rag_output.get("references", {}),
            "keyword_trend": keyword_top10,
            "industry": industry
        }

        return result

    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc(limit=2)}
