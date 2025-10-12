# src/feature_engineering.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline

PROTECTED_FEATURE_COLUMNS: tuple[str, ...] = (
    "RC_M1_SAA",
    "RC_M1_TO_UE_CT",
    "RC_M1_AV_NP_AT",
    "M12_SME_RY_SAA_PCE_RT",
    "M12_SME_RY_ME_MCT_RAT",
    "DLV_SAA_RAT",
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
    "MCT_OPE_MS_CN",
    "is_chain",
    "has_delivery",
)



# === Helper utilities =====================================================

BUCKET_PATTERN = re.compile(r"(\d{1,3})-(\d{1,3})%")
PERCENT_PATTERN = re.compile(r"(\d{1,3})%")


def _parse_bucket(value: object) -> Optional[float]:
    """Parse bucket-style percentage strings into floats (0~1 range)."""
    if value is None:
        return np.nan
    if isinstance(value, (int, float)):
        if isinstance(value, (float, np.floating)) and np.isnan(value):
            return np.nan
        return float(value)

    s = str(value)
    if "90%초과" in s:
        return 0.95

    if match := BUCKET_PATTERN.search(s):
        lo = float(match.group(1)) / 100.0
        hi = float(match.group(2)) / 100.0
        return (lo + hi) / 2.0

    if match := PERCENT_PATTERN.search(s):
        return float(match.group(1)) / 100.0

    return np.nan


# === Transformers =========================================================


class BucketToNumericTransformer(BaseEstimator, TransformerMixin):
    """Convert bucket-style categorical columns to numeric values."""

    def __init__(self) -> None:
        self.bucket_columns_: list[str] = []

    def fit(self, X: pd.DataFrame, y=None):
        obj_cols = X.select_dtypes(include=["object"]).columns
        bucket_cols: list[str] = []
        for col in obj_cols:
            sample = X[col].dropna().astype(str).head(50).tolist()
            if any(("%" in v) or ("초과" in v) or ("-" in v) for v in sample):
                bucket_cols.append(col)
        self.bucket_columns_ = bucket_cols
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        for col in self.bucket_columns_:
            X[col] = X[col].apply(_parse_bucket)
        return X


@dataclass
class SummaryFeatureConfig:
    female_cols: tuple[str, str] = ("M12_FME_20_RAT", "M12_FME_30_RAT")
    male_cols: tuple[str, str] = ("M12_MAL_40_RAT", "M12_MAL_50_RAT")
    ensure_cols: tuple[str, ...] = ("share_newbie", "share_revisit")
    log_threshold: float = 1.5


class SummaryFeatureTransformer(BaseEstimator, TransformerMixin):
    """Add aggregated demographic ratios; log features optional."""

    def __init__(self, config: SummaryFeatureConfig | None = None, enable_log: bool = False) -> None:
        self.config = config or SummaryFeatureConfig()
        self.enable_log = enable_log
        self.numeric_columns_: list[str] = []
        self.log_columns_: list[str] = []

    def fit(self, X: pd.DataFrame, y=None):
        numeric = X.select_dtypes(include=["number"])
        self.numeric_columns_ = numeric.columns.tolist()
        self.log_columns_ = []
        if self.enable_log:
            for col in self.numeric_columns_:
                series = numeric[col]
                try:
                    max_val = series.max(skipna=True)
                except Exception:
                    continue
                if pd.isna(max_val) or max_val <= self.config.log_threshold:
                    continue
                self.log_columns_.append(col)
        return self

    def _safe_sum(self, frame: pd.DataFrame, cols: tuple[str, ...]) -> pd.Series:
        existing = [c for c in cols if c in frame.columns]
        if not existing:
            return pd.Series(np.nan, index=frame.index)
        return frame[existing].sum(axis=1, skipna=True)

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        X["FE_MZ_female_ratio"] = self._safe_sum(X, self.config.female_cols)
        X["FE_mid_aged_male_ratio"] = self._safe_sum(X, self.config.male_cols)

        for col in self.config.ensure_cols:
            if col not in X.columns:
                X[col] = np.nan

        if self.enable_log:
            for col in self.log_columns_:
                if col not in X.columns:
                    continue
                series = X[col]
                X[f"log1p_{col}"] = np.log1p(series.clip(lower=0))

        return X


class LowVarianceHighCorrelationDropper(BaseEstimator, TransformerMixin):
    """Drop numerical columns with low variance or high pairwise correlation."""

    def __init__(
        self,
        lowvar_thresh: float = 1e-6,
        corr_thresh: float = 0.9,
        protected_columns: tuple[str, ...] | None = None,
    ) -> None:
        self.lowvar_thresh = lowvar_thresh
        self.corr_thresh = corr_thresh
        self.protected_columns = set(protected_columns or ())
        self.columns_to_drop_: set[str] = set()
        self.dropped_lowvar_: set[str] = set()
        self.dropped_highcorr_: set[str] = set()

    def fit(self, X: pd.DataFrame, y=None):
        df = X.copy()
        num_cols = df.select_dtypes(include=["number"]).columns.tolist()
        variances = df[num_cols].var(numeric_only=True)
        keep = variances[variances > self.lowvar_thresh].index.tolist()
        self.dropped_lowvar_ = set(num_cols) - set(keep)

        df = df[keep + [c for c in df.columns if c not in num_cols]]
        num_cols_post = df.select_dtypes(include=["number"]).columns.tolist()
        corr = df[num_cols_post].corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
        self.dropped_highcorr_ = {
            column for column in upper.columns if any(upper[column] > self.corr_thresh)
        }
        self.columns_to_drop_ = self.dropped_lowvar_.union(self.dropped_highcorr_)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        return X.drop(columns=list(self.columns_to_drop_), errors="ignore")


# === Convenience helpers ==================================================


def build_feature_engineering_pipeline(
    lowvar_thresh: float = 0.0,
    corr_thresh: float = 0.99,
    protected_columns: tuple[str, ...] = PROTECTED_FEATURE_COLUMNS,
) -> Pipeline:
    return Pipeline(
        steps=[
            ("bucket", BucketToNumericTransformer()),
            ("summary", SummaryFeatureTransformer(enable_log=False)),
            (
                "prune",
                LowVarianceHighCorrelationDropper(
                    lowvar_thresh=lowvar_thresh,
                    corr_thresh=corr_thresh,
                    protected_columns=protected_columns,
                ),
            ),
        ]
    )


def bucket_to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    return BucketToNumericTransformer().fit_transform(df)


def add_summary_features(df: pd.DataFrame) -> pd.DataFrame:
    return SummaryFeatureTransformer().fit(df).transform(df)


def drop_lowvar_highcorr(
    df: pd.DataFrame, lowvar_thresh: float = 1e-6, corr_thresh: float = 0.9
):
    transformer = LowVarianceHighCorrelationDropper(
        lowvar_thresh=lowvar_thresh, corr_thresh=corr_thresh
    )
    transformed = transformer.fit_transform(df)
    return transformed, {
        "dropped_lowvar": transformer.dropped_lowvar_,
        "dropped_highcorr": transformer.dropped_highcorr_,
    }



