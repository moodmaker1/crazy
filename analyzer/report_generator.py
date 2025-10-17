import traceback

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
        raw_result = None

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
            raw_result = predict_delivery(mct_id)
            if raw_result is None:
                return {"error": "해당 가맹점을 찾을 수 없거나 이미 배달을 운영 중입니다."}
            # 배달 예측 리포트 포맷 정리
            base_result = {
                "store_code": raw_result.get("store_code"),
                "store_name": raw_result.get("store_name"),
                "store_type": raw_result.get("store_type"),
                "district": raw_result.get("district"),
                "area": raw_result.get("area"),
                "emoji": raw_result.get("emoji", "📦"),
                "success_prob": raw_result.get("success_prob", 0.0),
                "fail_prob": 100 - raw_result.get("success_prob", 0.0),
                "status": raw_result.get("level", "-"),
                "message": raw_result.get("summary", ""),
                "recommendation": raw_result.get("recommendation", ""),
                "reasons": raw_result.get("reasons", []),
                "interpret_text": raw_result.get("interpret_text", ""),
                "feature_report": raw_result.get("feature_report", {}),
            }
        else:
            return {"error": f"지원되지 않는 모드입니다: {mode}"}

        # --------------------------------------
        # ② RAG 비활성 모드 → 내부 분석 결과만 반환
        # --------------------------------------
        if not rag:
            return base_result

        # --------------------------------------
        # ③ 업종 식별 (RAG/키워드 공통 입력)
        # --------------------------------------
        industry = (base_result.get("업종분류")or base_result.get("store_type")or get_industry_from_store(mct_id)or "기타")





        # --------------------------------------
        # ④ 키워드 트렌드 분석 → RAG 생성
        #    (업종 키워드 기반으로 프롬프트에 최신 메뉴/콘셉트 반영)
        # --------------------------------------
        keyword_report = {}
        keyword_top10 = []
        try:
            keyword_report = generate_keyword_trend_report(industry)
            keyword_top10 = keyword_report.get("TOP10", []) or []
        except Exception as e:
            print(f"⚠️ 키워드 트렌드 생성 실패: {e}")
            keyword_report = {"error": str(e), "TOP10": []}

        rag_kwargs = {
            "mct_id": mct_id,
            "mode": mode,
            "top_k": 5,
            "keyword_top10": keyword_top10,
        }
        if mode in ("v2", "v3"):
            rag_kwargs["store_type"] = industry

        rag_output = generate_rag_summary(**rag_kwargs)
        rag_text = rag_output.get("rag_summary", "")

        # --------------------------------------
        # ⑤ 결과 병합
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
