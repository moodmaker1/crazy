# analyzer/data_loader.py
import pandas as pd
from .paths import find_latest_cluster_csv, find_feature_csv

def load_cluster_df() -> pd.DataFrame:
    p = find_latest_cluster_csv()
    if not p:
        raise FileNotFoundError("cluster_result.csv 경로를 찾지 못했습니다.")
    df = pd.read_csv(p)
    # 컬럼 표준화(있을 수도 있는 케이스)
    if "ENCODED_MCT" not in df.columns:
        # 대안 키들 추정
        for c in ["encoded_mct", "mct_id", "store_id", "STORE_ID"]:
            if c in df.columns:
                df = df.rename(columns={c: "ENCODED_MCT"})
                break
    return df

def load_feature_df() -> pd.DataFrame:
    p = find_feature_csv()
    if not p:
        raise FileNotFoundError("cafe_features_processed.csv 경로를 찾지 못했습니다.")
    df = pd.read_csv(p)
    if "ENCODED_MCT" not in df.columns:
        for c in ["encoded_mct", "mct_id", "store_id", "STORE_ID"]:
            if c in df.columns:
                df = df.rename(columns={c: "ENCODED_MCT"})
                break
    return df
