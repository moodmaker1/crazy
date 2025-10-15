import traceback
from analyzer.rag_engine_optimized import generate_rag_summary
from experiments._1_final.report_generator import generate_marketing_report1
from experiments._2_final.report_generator2 import generate_marketing_report2
from experiments._3_final.report_generator3 import generate_marketing_report3
from experiments._0_final.store_status import get_store_status_with_insights


def generate_marketing_report(mct_id: str, mode: str = "v1", rag: bool = True):
    """
    AI 마케팅 리포트 생성 게이트웨이 (자동 라우팅)

    Parameters
    ----------
    mct_id : str
        가맹점 코드
    mode : str
        분석 모드 (v0, v1, v2, v3)
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
