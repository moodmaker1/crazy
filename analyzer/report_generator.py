"""
analyzer/report_generator.py
AI 마케팅 분석 모델 통합 게이트웨이 (RAG 통합 버전)
---------------------------------
"""
import traceback
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

try:
    from experiments._0_final.store_status import get_store_status_with_insights
    from experiments._1_final.report_generator import generate_marketing_report1
    from experiments._2_final.report_generator2 import generate_marketing_report2
    from experiments._3_final.report_generator3 import generate_marketing_report3
    from .rag_engine import generate_rag_summary  # ✅ RAG 모듈
except ModuleNotFoundError as e:
    print(f"[Import Warning] 일부 모델 모듈을 불러오지 못했습니다: {e}")

import pandas as pd
from .utils import summarize_report, df_row_as_dict


def generate_marketing_report(mct_id: str, mode: str = "v2"):
    """
    mode별로:
    1️⃣ 내부 모델 실행 (기초 통계 or 분석 결과)
    2️⃣ RAG 기반 요약 통합
    """
    try:
        # -----------------------------
        # ① 내부 모델 실행
        # -----------------------------
        base_result = None
        if mode == "v0":
            base_result = get_store_status_with_insights(mct_id)
            return base_result
        elif mode == "v1":
            base_result = generate_marketing_report1(mct_id)
        elif mode == "v2":
            base_result = generate_marketing_report2(mct_id)
        elif mode == "v3":
            base_result = generate_marketing_report3(mct_id)

        # -----------------------------
        # ② RAG 기반 리포트 생성
        # -----------------------------
        rag_output = generate_rag_summary(mct_id, mode)
        rag_text = rag_output.get("rag_summary", None)

        # -----------------------------
        # ③ 결과 합치기
        # -----------------------------
        result = {
            "store_code": mct_id,
            "mode": mode,
            "rag_summary": rag_text,
            "references": rag_output.get("references", {}),
        }

        # base_result에 매장 정보가 있을 경우 함께 포함
        if isinstance(base_result, dict):
            result.update({
                "store_name": base_result.get("store_name", ""),
                "status": base_result.get("status", ""),
                "status_detail": base_result.get("status_detail", ""),
                "analysis": base_result.get("analysis", ""),
                "recommendations": base_result.get("recommendations", ""),
                "metadata": base_result.get("metadata", {}),
            })

        return result

    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc(limit=2)}
