from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

CAFE_CATEGORIES: tuple[str, ...] = (
    "카페",
    "커피전문점",
    "테이크아웃커피",
    "테마카페",
)

CATEGORY_NORMALIZATION_MAP: dict[str, str] = {
    "카페": "카페",
    "커피전문점": "커피전문점",
    "테이크아웃커피": "테이크아웃커피",
    "테마카페": "테마카페",
    "ī��": "카페",
    "Ŀ��������": "커피전문점",
    "����ũ�ƿ�Ŀ��": "테이크아웃커피",
    "�׸�ī��": "테마카페",
}

TOTAL_COLUMN_RENAME_MAP: dict[str, str] = {
    "가맹점코드": "ENCODED_MCT",
    "분석기준일자": "TA_YM",
    "가맹점명": "MCT_NM",
    "가맹점시군구명": "MCT_SIGUNGU_NM",
    "업종분류": "HPSN_MCT_ZCD_NM",
    "상권": "TRADE_AREA",
    "운영개월구간(1~6)": "MCT_OPE_MS_GRADE",
    "운영개월수": "MCT_OPE_MONTHS",
    "운영개월수_(분위)": "MCT_OPE_MONTHS_QUANTILE",
    "운영개월수_(0~1)": "MCT_OPE_MONTHS_NORMALIZED",
    "배달여부": "delivery_flag",
    "객단가비율": "RC_UNIT_PRICE_RATIO",
    "배달매출비율": "DLV_SAA_RAT",
    "배달매출비율_LOG": "DLV_SAA_RAT_LOG",
    "최근12개월_업종매출증감률": "M12_SME_RY_SAA_PCE_RT",
    "최근12개월_상권_매출증감률": "M12_SME_BZN_SAA_PCE_RT",
    "최근12개월_업종_월평균가맹점비율": "M12_SME_RY_ME_MCT_RAT",
    "최근12개월_상권_월평균가맹점비율": "M12_SME_BZN_ME_MCT_RAT",
    "최근12개월_남성_10-20대비율": "M12_MAL_1020_RAT",
    "최근12개월_남성_30대비율": "M12_MAL_30_RAT",
    "최근12개월_남성_40대비율": "M12_MAL_40_RAT",
    "최근12개월_남성_50대비율": "M12_MAL_50_RAT",
    "최근12개월_남성_60대비율": "M12_MAL_60_RAT",
    "최근12개월_여성_10-20대비율": "M12_FME_1020_RAT",
    "최근12개월_여성_30대비율": "M12_FME_30_RAT",
    "최근12개월_여성_40대비율": "M12_FME_40_RAT",
    "최근12개월_여성_50대비율": "M12_FME_50_RAT",
    "최근12개월_여성_60대비율": "M12_FME_60_RAT",
    "재방문고객비율": "MCT_UE_CLN_REU_RAT",
    "신규고객비율": "MCT_UE_CLN_NEW_RAT",
    "최근1개월_거주고객비율": "RC_M1_SHC_RSD_UE_CLN_RAT",
    "최근1개월_직장고객비율": "RC_M1_SHC_WP_UE_CLN_RAT",
    "최근1개월_유동고객비율": "RC_M1_SHC_FLP_UE_CLN_RAT",
    "최근1개월_매출액_등급(1~6)": "RC_M1_SAA",
    "최근1개월_총이용건수_등급(1~6)": "RC_M1_TO_UE_CT",
    "최근1개월_이용고객수_등급(1~6)": "RC_M1_UE_CUS_GRADE",
    "최근1개월_객단가_등급(1~6)": "RC_M1_AV_NP_AT",
    "충성도점수": "LOYALTY_SCORE",
    "충성도점수(재방문_비율에서_신규_비율을뺀_것)": "LOYALTY_SCORE_DELTA",
    "업종매출대비비율_정규화": "INDUSTRY_SALES_RATIO_NORM",
    "업종건수대비비율_정규화": "INDUSTRY_STORES_RATIO_NORM",
    "30대성별비율차이": "AGE30_GENDER_DIFF",
}

GRADE_MIDPOINTS = {
    1: 0.083,
    2: 0.250,
    3: 0.417,
    4: 0.583,
    5: 0.750,
    6: 0.917,
}

GRADE_COLUMNS = (
    "MCT_OPE_MS_GRADE",
    "RC_M1_SAA",
    "RC_M1_TO_UE_CT",
    "RC_M1_AV_NP_AT",
    "RC_M1_UE_CUS_GRADE",
)

FEATURE_KEEP_COLUMNS: tuple[str, ...] = (
    "ENCODED_MCT",
    "TA_YM",
    "snapshot_date",
    "MCT_NM",
    "MCT_SIGUNGU_NM",
    "HPSN_MCT_ZCD_NM",
    "TRADE_AREA",
    "MCT_BRD_NUM",
    "is_chain",
    "has_delivery",
    "MCT_OPE_MONTHS",
    "MCT_OPE_MONTHS_QUANTILE",
    "MCT_OPE_MONTHS_NORMALIZED",
    "MCT_OPE_MS_GRADE",
    "RC_UNIT_PRICE_RATIO",
    "RC_M1_SAA",
    "RC_M1_TO_UE_CT",
    "RC_M1_AV_NP_AT",
    "M12_SME_RY_SAA_PCE_RT",
    "M12_SME_BZN_SAA_PCE_RT",
    "M12_SME_RY_ME_MCT_RAT",
    "M12_SME_BZN_ME_MCT_RAT",
    "DLV_SAA_RAT",
    "DLV_SAA_RAT_LOG",
    "M12_MAL_1020_RAT",
    "M12_MAL_30_RAT",
    "M12_MAL_40_RAT",
    "M12_MAL_50_RAT",
    "M12_MAL_60_RAT",
    "M12_FME_1020_RAT",
    "M12_FME_30_RAT",
    "M12_FME_40_RAT",
    "M12_FME_50_RAT",
    "M12_FME_60_RAT",
    "MCT_UE_CLN_REU_RAT",
    "MCT_UE_CLN_NEW_RAT",
    "RC_M1_SHC_RSD_UE_CLN_RAT",
    "RC_M1_SHC_WP_UE_CLN_RAT",
    "RC_M1_SHC_FLP_UE_CLN_RAT",
    "INDUSTRY_SALES_RATIO_NORM",
    "INDUSTRY_STORES_RATIO_NORM",
    "LOYALTY_SCORE",
    "LOYALTY_SCORE_DELTA",
    "AGE30_GENDER_DIFF",
)

STORE_COLUMN_RENAME_MAP: dict[str, str] = {
    "ENCODED_MCT": "ENCODED_MCT",
    "MCT_BRD_NUM": "MCT_BRD_NUM",
}


def load_total_dataset(path: str | Path, encoding: str = "utf-8") -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding=encoding)


def load_store_metadata(path: str | Path, encoding: str = "cp949") -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, encoding=encoding)
    df = df.rename(columns=STORE_COLUMN_RENAME_MAP)
    keep = [col for col in ("ENCODED_MCT", "MCT_BRD_NUM") if col in df.columns]
    return df[keep] if keep else df


def normalize_category_values(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        return series.map(CATEGORY_NORMALIZATION_MAP).fillna(series)
    return series


def filter_cafe_categories(
    df: pd.DataFrame,
    category_column: str = "HPSN_MCT_ZCD_NM",
    categories: Iterable[str] | None = None,
) -> pd.DataFrame:
    if category_column not in df.columns:
        raise KeyError(f"Column '{category_column}' not found in dataframe")
    cats = tuple(categories) if categories is not None else CAFE_CATEGORIES
    normalized = normalize_category_values(df[category_column])
    mask = normalized.isin(cats)
    result = df.loc[mask].copy()
    result[category_column] = normalized.loc[result.index]
    return result


def rename_total_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {col: new for col, new in TOTAL_COLUMN_RENAME_MAP.items() if col in df.columns}
    renamed = df.rename(columns=rename_map)
    if "HPSN_MCT_ZCD_NM" in renamed.columns:
        renamed["HPSN_MCT_ZCD_NM"] = normalize_category_values(renamed["HPSN_MCT_ZCD_NM"])
    return renamed


def convert_grade_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in GRADE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round().map(GRADE_MIDPOINTS)
    return df


def prepare_latest_snapshot(
    total_df: pd.DataFrame,
    store_df: pd.DataFrame,
    categories: Iterable[str] | None = None,
) -> pd.DataFrame:
    categories = tuple(categories) if categories is not None else CAFE_CATEGORIES

    renamed = rename_total_columns(total_df)
    filtered = filter_cafe_categories(renamed, category_column="HPSN_MCT_ZCD_NM", categories=categories)

    if "TA_YM" not in filtered.columns:
        raise KeyError("Column 'TA_YM' is required in the total dataset")

    filtered["TA_YM"] = pd.to_datetime(filtered["TA_YM"], errors="coerce")
    filtered = filtered.sort_values(["ENCODED_MCT", "TA_YM"])

    latest_idx = filtered.groupby("ENCODED_MCT")["TA_YM"].idxmax()
    latest = filtered.loc[latest_idx].copy()
    latest.insert(1, "snapshot_date", pd.Timestamp.now().strftime("%Y-%m-%d"))

    if not store_df.empty:
        latest = latest.merge(store_df, on="ENCODED_MCT", how="left")

    if "MCT_BRD_NUM" in latest.columns:
        latest["is_chain"] = latest["MCT_BRD_NUM"].notna().astype(int)
    else:
        latest["is_chain"] = 0

    has_delivery = pd.Series(0, index=latest.index)
    if "delivery_flag" in latest.columns:
        has_delivery = has_delivery | latest["delivery_flag"].fillna(0).astype(int)
        latest = latest.drop(columns=["delivery_flag"])
    if "DLV_SAA_RAT" in latest.columns:
        has_delivery = has_delivery | (latest["DLV_SAA_RAT"].fillna(0) > 0).astype(int)
    latest["has_delivery"] = has_delivery.astype(int)

    latest["TA_YM"] = latest["TA_YM"].dt.strftime("%Y-%m-%d")

    non_numeric = {"ENCODED_MCT", "MCT_NM", "MCT_SIGUNGU_NM", "HPSN_MCT_ZCD_NM", "TRADE_AREA", "snapshot_date", "TA_YM"}
    for col in latest.columns:
        if col in non_numeric:
            continue
        latest[col] = pd.to_numeric(latest[col], errors="coerce")

    latest = convert_grade_columns(latest)

    keep = [col for col in FEATURE_KEEP_COLUMNS if col in latest.columns]
    latest = latest[keep].copy()

    return latest


def save_utf8_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


__all__ = [
    "CAFE_CATEGORIES",
    "load_total_dataset",
    "load_store_metadata",
    "filter_cafe_categories",
    "rename_total_columns",
    "prepare_latest_snapshot",
    "save_utf8_csv",
]
