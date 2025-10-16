# analyzer/paths.py
import os
from glob import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP_BASE = os.path.join(ROOT, "experiments", "clusters_k4_baseline")

def path_exists(p: str) -> bool:
    return os.path.exists(p) and os.path.isfile(p)

def dir_exists(p: str) -> bool:
    return os.path.exists(p) and os.path.isdir(p)

def find_latest_cluster_csv() -> str | None:
    """
    outputs/latest_cluster/cluster_result.csv 우선,
    없으면 outputs/*/cluster_result.csv 중 최근 변경 순으로 탐색
    """
    cand = os.path.join(EXP_BASE, "outputs", "latest_cluster", "cluster_result.csv")
    if path_exists(cand):
        return cand

    pattern = os.path.join(EXP_BASE, "outputs", "*", "cluster_result.csv")
    files = glob(pattern)
    if not files:
        # 루트 직하도 시도
        cand2 = os.path.join(EXP_BASE, "outputs", "cluster_result.csv")
        return cand2 if path_exists(cand2) else None

    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0]

def find_feature_csv() -> str | None:
    # 너가 준 경로 우선
    cand1 = os.path.join(EXP_BASE, "data", "processed", "cafe_features_processed.csv")
    if path_exists(cand1):
        return cand1
    # 대안
    cand2 = os.path.join(EXP_BASE, "data", "cafe_features_processed.csv")
    return cand2 if path_exists(cand2) else None
