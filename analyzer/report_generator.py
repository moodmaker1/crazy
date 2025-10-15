import traceback
from analyzer.rag_engine import generate_rag_summary
from experiments._1_final.report_generator import generate_marketing_report1
from experiments._2_final.report_generator2 import generate_marketing_report2
from experiments._3_final.report_generator3 import generate_marketing_report3
from experiments._0_final.store_status import get_store_status_with_insights
from experiments._4_final.delivery_prediction import predict_delivery


def generate_marketing_report(mct_id: str, mode: str = "v1", rag: bool = True):
    """
    AI 마케팅 리포트 생성 게이트웨이 (자동 라우팅)

    Parameters
    ----------
    mct_id : str
        가맹점 코드
    mode : str
        분석 모드 (v0, v1, v2, v3, v4)
        - v0: 기본 매장 상태 분석
        - v1: 고객 분석 및 마케팅 채널 추천
        - v2: 재방문율 분석 및 향상 전략
        - v3: 약점 진단 및 개선 전략
        - v4: 배달 도입 성공 예측
    rag : bool
        RAG 실행 여부 (False면 내부 분석만 수행)

    Returns
    -------
    dict : 리포트 결과
    """
    try:
        # --------------------------------------
        # ① 내부 분석 모델 자동 라우팅
        # --------------------------------------
        base_result = None
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
        # ② RAG 비활성 모드면 바로 반환
        # --------------------------------------
        if not rag:
            return base_result

        # --------------------------------------
        # ③ RAG 리포트 생성
        # --------------------------------------
        rag_output = generate_rag_summary(mct_id, mode)
        rag_text = rag_output.get("rag_summary", None)

        result = {
            "store_code": mct_id,
            "mode": mode,
            "rag_summary": rag_text,
            "references": rag_output.get("references", {}),
        }

        # --------------------------------------
        # ④ 내부 분석 결과와 병합
        # --------------------------------------
        if isinstance(base_result, dict):
            result.update({
                "store_name": base_result.get("store_name", ""),
                "status": base_result.get("status", ""),
                # ✅ message가 없을 경우 status_detail 또는 빈 문자열
                "message": base_result.get("message") or base_result.get("status_detail", "") or "",
                "analysis": base_result.get("analysis", ""),
                "recommendations": base_result.get("recommendations", ""),
                "metadata": base_result.get("metadata", {}),
                "revisit_rate": base_result.get("revisit_rate", None)
            })


        return result

    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc(limit=2)}
