# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
THIS_DIR = Path(__file__).resolve().parents[1]
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from src.preprocessing import (
    CAFE_CATEGORIES_DECODED,
    convert_grade_columns,
    drop_low_sales_grade,
    ensure_datetime,
    filter_by_history,
    filter_cafe_records,
    load_total_dataset,
    remove_sales_outliers,
    rename_total_columns,
)

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = THIS_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RAW_TOTAL_PATH = DATA_DIR / "total" / "total_data_final.csv"
MIN_HISTORY_MONTHS = 12

KEEP_COLUMNS = [
    "ENCODED_MCT",
    "TA_YM",
    "RC_M1_SAA",
    "RC_M1_TO_UE_CT",
    "RC_M1_AV_NP_AT",
    "MCT_UE_CLN_REU_RAT",
    "MCT_UE_CLN_NEW_RAT",
    "RC_M1_SHC_RSD_UE_CLN_RAT",
    "RC_M1_SHC_WP_UE_CLN_RAT",
    "RC_M1_SHC_FLP_UE_CLN_RAT",
    "DLV_SAA_RAT",
    "M12_SME_RY_SAA_PCE_RT",
    "M12_SME_BZN_SAA_PCE_RT",
]


def prepare_timeseries_dataset(raw_total: Path, output_path: Path) -> None:
    total = load_total_dataset(raw_total)
    total = rename_total_columns(total)
    total = filter_cafe_records(total, categories=CAFE_CATEGORIES_DECODED)
    total = convert_grade_columns(total)

    keep_cols = [col for col in KEEP_COLUMNS if col in total.columns]
    df = total[keep_cols].copy()

    df = ensure_datetime(df, "TA_YM")
    df = df.rename(columns={
        "TA_YM": "snapshot_date",
        "RC_M1_SAA": "sales_grade",
        "RC_M1_TO_UE_CT": "visits_grade",
        "RC_M1_AV_NP_AT": "unit_price_grade",
        "MCT_UE_CLN_REU_RAT": "revisit_ratio",
        "MCT_UE_CLN_NEW_RAT": "new_customer_ratio",
        "RC_M1_SHC_RSD_UE_CLN_RAT": "resident_ratio",
        "RC_M1_SHC_WP_UE_CLN_RAT": "worker_ratio",
        "RC_M1_SHC_FLP_UE_CLN_RAT": "floating_ratio",
        "DLV_SAA_RAT": "delivery_ratio",
        "M12_SME_RY_SAA_PCE_RT": "industry_sales_change",
        "M12_SME_BZN_SAA_PCE_RT": "trade_sales_change",
    })

    df = drop_low_sales_grade(df)
    df = remove_sales_outliers(df)
    df = filter_by_history(df, min_months=MIN_HISTORY_MONTHS)
    df = df.sort_values(["ENCODED_MCT", "snapshot_date"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[SAVE] Time-series panel -> {output_path}")


if __name__ == "__main__":
    output_csv = OUTPUT_DIR / "cafe_timeseries_panel.csv"
    prepare_timeseries_dataset(RAW_TOTAL_PATH, output_csv)
