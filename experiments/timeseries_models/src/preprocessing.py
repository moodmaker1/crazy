# -*- coding: utf-8 -*-
"""카페 업종 시계열 전처리 모듈."""
from __future__ import annotations

from typing import Iterable, List

import pandas as pd

from .preprocessing_constants import TOTAL_COLUMN_RENAME_MAP, GRADE_MIDPOINTS, CAFE_CATEGORIES

RENAME_MAP = dict(TOTAL_COLUMN_RENAME_MAP)
CAFE_CATEGORIES_DECODED = tuple(CAFE_CATEGORIES)


def load_total_dataset(path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp949")


def rename_total_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {k: v for k, v in RENAME_MAP.items() if k in df.columns}
    return df.rename(columns=rename_map)


def filter_cafe_records(df: pd.DataFrame, categories: Iterable[str] | None = None) -> pd.DataFrame:
    cats = tuple(categories) if categories is not None else CAFE_CATEGORIES_DECODED
    if "HPSN_MCT_ZCD_NM" not in df.columns:
        raise KeyError("HPSN_MCT_ZCD_NM not found; rename_total_columns must run first.")
    return df[df["HPSN_MCT_ZCD_NM"].isin(cats)].copy()


def convert_grade_columns(df: pd.DataFrame) -> pd.DataFrame:
    grade_cols = [
        "MCT_OPE_MS_GRADE",
        "RC_M1_SAA",
        "RC_M1_TO_UE_CT",
        "RC_M1_AV_NP_AT",
        "RC_M1_UE_CUS_GRADE",
    ]
    for col in grade_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round().map(GRADE_MIDPOINTS)
    return df


def ensure_datetime(df: pd.DataFrame, column: str) -> pd.DataFrame:
    df[column] = pd.to_datetime(df[column], errors="coerce")
    return df.dropna(subset=[column])


def drop_low_sales_grade(
    df: pd.DataFrame,
    column: str = "sales_grade",
    minimum: float = 0.05,
) -> pd.DataFrame:
    if column not in df.columns:
        return df
    mask = df[column].isna() | (df[column] >= minimum)
    return df[mask].copy()


def remove_sales_outliers(
    df: pd.DataFrame,
    column: str = "sales_grade",
    group_col: str = "ENCODED_MCT",
    iqr_multiplier: float = 3.0,
    min_points: int = 6,
) -> pd.DataFrame:
    if column not in df.columns:
        return df

    filtered_groups: List[pd.DataFrame] = []
    for _, group in df.groupby(group_col):
        series = group[column].dropna()
        if len(series) < min_points:
            filtered_groups.append(group)
            continue
        q1, q3 = series.quantile([0.25, 0.75])
        iqr = q3 - q1
        if iqr == 0:
            filtered_groups.append(group)
            continue
        lower = max(series.min(), q1 - iqr_multiplier * iqr)
        upper = min(series.max(), q3 + iqr_multiplier * iqr)
        filtered_groups.append(group[(group[column] >= lower) & (group[column] <= upper)])

    if not filtered_groups:
        return df.copy()
    return pd.concat(filtered_groups, ignore_index=True)


def filter_by_history(
    df: pd.DataFrame,
    min_months: int,
    group_col: str = "ENCODED_MCT",
    date_col: str = "snapshot_date",
) -> pd.DataFrame:
    counts = df.groupby(group_col)[date_col].count()
    keep = counts[counts >= min_months].index
    return df[df[group_col].isin(keep)].copy()


__all__ = [
    "load_total_dataset",
    "rename_total_columns",
    "filter_cafe_records",
    "convert_grade_columns",
    "ensure_datetime",
    "drop_low_sales_grade",
    "remove_sales_outliers",
    "filter_by_history",
    "CAFE_CATEGORIES_DECODED",
]
