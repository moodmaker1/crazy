# src/preprocess.py
from __future__ import annotations

import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler

DROP_COLS_DEFAULT = ["ENCODED_MCT", "TA_YM", "TA_DATE"]
DROP_COLS_MODEL_ONLY = [
    "MCT_NM",
    "MCT_BRD_NUM",
    "MCT_SIGUNGU_NM",
    "HPSN_MCT_ZCD_NM",
    "HPSN_MCT_BZN_CD_NM",
]


def load_dataframe(path_csv: str, encoding: str | None = None, **read_kwargs) -> pd.DataFrame:
    if encoding:
        return pd.read_csv(path_csv, encoding=encoding, **read_kwargs)

    encodings = ("utf-8", "utf-8-sig", "cp949")
    last_error: Exception | None = None
    for enc in encodings:
        try:
            return pd.read_csv(path_csv, encoding=enc, **read_kwargs)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise ValueError(f"Failed to read {path_csv} with encodings: {encodings}")


def drop_unnecessary(
    df: pd.DataFrame,
    extra_drop: list[str] | None = None,
    keep_meta: bool = False,
) -> pd.DataFrame:
    drop_cols = DROP_COLS_DEFAULT.copy()
    if not keep_meta:
        drop_cols += DROP_COLS_MODEL_ONLY
    if extra_drop:
        drop_cols += extra_drop
    drop_cols = [c for c in drop_cols if c in df.columns]
    return df.drop(columns=drop_cols)


def build_preprocessor(df: pd.DataFrame):
    cat_cols = [c for c in df.columns if df[c].dtype == "object"]
    num_cols = [c for c in df.columns if c not in cat_cols]

    skl_version = tuple(map(int, sklearn.__version__.split(".")[:2]))
    if skl_version >= (1, 2):
        onehot = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    else:
        onehot = OneHotEncoder(handle_unknown="ignore", sparse=False)

    cat_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", onehot),
        ]
    )

    num_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
        ]
    )

    pre = ColumnTransformer(
        transformers=[
            ("cat", cat_pipeline, cat_cols),
            ("num", num_pipeline, num_cols),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    return pre, cat_cols, num_cols
