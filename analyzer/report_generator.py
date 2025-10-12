"""
analyzer/report_generator.py
AI 마케팅 분석 모델 통합 게이트웨이
---------------------------------
여러 모델 모듈을 import하고, mode 값에 따라 해당 함수를 실행하는 라우터 역할을 합니다.
"""

import traceback
import os
import sys

# -----------------------------------------
# 경로 설정 (상위 경로 import 가능하게)
# -----------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# -----------------------------------------
# 모델 모듈 Import
# -----------------------------------------
try:
    # 1. 최신 버전 (report_generator2)
    from experiments._2_final.report_generator2 import generate_marketing_report2

    # 2. 기존 baseline 모델 (generate_personal_reports.py)
    from experiments.clusters_k4_baseline.scripts.generate_personal_reports import (
        load_cluster_data,
        load_feature_data,
        generate_reports,
    )

    from experiments._3_final.report_generator3 import generate_marketing_report3

except ModuleNotFoundError as e:
    print(f"[Import Warning] 일부 모델 모듈을 불러오지 못했습니다: {e}")

# -----------------------------------------
# Analyzer 내부 유틸 (공통)
# -----------------------------------------
from .data_loader import load_cluster_df, load_feature_df
from .utils import summarize_report, df_row_as_dict
import pandas as pd


# -----------------------------------------
# Report Router (Gateway)
# -----------------------------------------
def generate_marketing_report(mct_id: str, mode: str = "v2"):
    """
    mode에 따라 다른 모델 모듈을 호출하는 통합 리포트 생성 함수.
    - "v2": experiments/_2_final/report_generator2.py
    - "baseline": experiments/clusters_k4_baseline/sripts/generate_personal_reports.py
    - "timeseries": (추가 예정)
    """

    try:
        if mode == "v2":
            # 최신 모델 (report_generator2)
            return generate_marketing_report2(mct_id)
        
        elif mode == "v3":
            # 최신 모델 (report_generator2)
            return generate_marketing_report3(mct_id)

        elif mode == "baseline":
            # 구버전 모델 (기존 클러스터 기반)
            cluster_df = load_cluster_data("experiments/clusters_k4_baseline/outputs/latest_cluster/cluster_result.csv")
            feature_df = load_feature_data("experiments/clusters_k4_baseline/data/processed/cafe_features_processed.csv")

            merged = pd.merge(feature_df, cluster_df, on="ENCODED_MCT", how="left").set_index("ENCODED_MCT")

            if mct_id not in merged.index:
                return {"error": f"가맹점 ID '{mct_id}'를 찾을 수 없습니다."}

            record = df_row_as_dict(merged, mct_id)
            summary = summarize_report(record)
            return {"mct_id": mct_id, "report": record, "summary": summary}

        elif mode == "timeseries":
            # 추가 예정: 시계열 기반 예측 모델
            return {"message": "시계열 기반 리포트는 현재 준비 중입니다."}

        else:
            return {"error": f"지원되지 않는 모드: {mode}"}

    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc(limit=2)}
