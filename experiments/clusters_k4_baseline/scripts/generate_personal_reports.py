# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import pandas as pd

DEFAULT_CLUSTER_PATH = Path("outputs/latest_cluster/cluster_result.csv")
DEFAULT_FEATURES_PATH = Path("data/processed/cafe_features_processed.csv")
DEFAULT_OUTPUT_PATH = Path("outputs/reports/personalized_reports.csv")

FEATURE_RULES: Dict[str, Dict[str, float | str]] = {
    "LOYALTY_SCORE": {
        "label": "충성도",
        "keyword_positive": "충성 고객 강점",
        "keyword_negative": "충성 고객 약화",
        "positive_message": "단골 고객 비중이 군집 평균보다 높습니다.",
        "negative_message": "단골 고객 비중이 낮아 재방문 유도가 필요합니다.",
        "threshold": 5.0,
    },
    "MCT_UE_CLN_NEW_RAT": {
        "label": "신규 고객",
        "keyword_positive": "신규 고객 유입 호조",
        "keyword_negative": "신규 고객 유입 부족",
        "positive_message": "신규 고객 비중이 군집 평균보다 높습니다.",
        "negative_message": "신규 고객 비중이 낮으니 외부 노출과 프로모션을 검토하세요.",
        "threshold": 3.0,
    },
    "DLV_SAA_RAT": {
        "label": "배달 비중",
        "keyword_positive": "배달 채널 강점",
        "keyword_negative": "배달 채널 약점",
        "positive_message": "배달 매출 비중이 군집 평균을 웃돌고 있습니다.",
        "negative_message": "배달 채널 활용도가 낮습니다.",
        "threshold": 5.0,
    },
    "RC_M1_SAA": {
        "label": "최근 매출",
        "keyword_positive": "매출 호조",
        "keyword_negative": "매출 둔화",
        "positive_message": "최근 매출 등급이 군집 평균보다 높습니다.",
        "negative_message": "최근 매출 등급이 군집 평균보다 낮습니다.",
        "threshold": 0.05,
    },
}

NEGATIVE_PRIORITY: List[str] = [
    "충성 고객 약화",
    "신규 고객 유입 부족",
    "배달 채널 약점",
    "매출 둔화",
]


def load_cluster_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "cluster" not in df.columns:
        raise ValueError("cluster_result.csv must contain a 'cluster' column")
    return df


def load_feature_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "ENCODED_MCT" not in df.columns:
        raise ValueError("features dataset must include 'ENCODED_MCT'")
    return df


def compute_cluster_reference(df: pd.DataFrame) -> pd.DataFrame:
    cols = [col for col in FEATURE_RULES if col in df.columns]
    if not cols:
        raise ValueError("None of the FEATURE_RULES columns exist in the merged dataset")
    return df.groupby("cluster")[cols].mean()


def severity_label(delta: float, threshold: float) -> str:
    gap = abs(delta)
    if gap >= threshold * 3:
        return "심각"
    if gap >= threshold * 2:
        return "주의"
    return "관찰"


def build_report(row: pd.Series, cluster_mean: pd.Series) -> Dict[str, List[str]]:
    strengths: List[str] = []
    gaps: List[tuple[str, float, str]] = []

    for feature, rule in FEATURE_RULES.items():
        if feature not in row or feature not in cluster_mean:
            continue
        value = row[feature]
        ref = cluster_mean[feature]
        if pd.isna(value) or pd.isna(ref):
            continue
        delta = value - ref
        threshold = float(rule.get("threshold", 1.0))

        if delta >= threshold:
            strengths.append(f"- {rule['keyword_positive']}: {rule['positive_message']}")
        elif delta <= -threshold:
            sev = severity_label(delta, threshold)
            gaps.append((rule["keyword_negative"], abs(delta), f"- {rule['keyword_negative']}: {rule['negative_message']} (단계: {sev})"))

    gaps.sort(key=lambda item: (NEGATIVE_PRIORITY.index(item[0]) if item[0] in NEGATIVE_PRIORITY else len(NEGATIVE_PRIORITY), -item[1]))
    gap_texts = [text for _, _, text in gaps[:3]]

    if not strengths:
        strengths = ["- 두드러진 강점이 확인되지 않았습니다."]
    if not gap_texts:
        gap_texts = ["- 긴급 개선 항목이 확인되지 않았습니다."]

    return {"strengths": strengths, "improvements": gap_texts}


def format_report(row: pd.Series, details: Dict[str, List[str]]) -> str:
    store = row.get("MCT_NM", "정보 없음")
    cluster = int(row["cluster"])
    lines = [
        f"매장명: {store}",
        f"소속 군집: Cluster {cluster}",
        "[강점 요약]",
        *details["strengths"],
        "[개선 권장]",
        *details["improvements"],
    ]
    return "\n".join(lines)


def generate_reports(cluster_df: pd.DataFrame, feature_df: pd.DataFrame) -> pd.DataFrame:
    merged = cluster_df.merge(feature_df, on="ENCODED_MCT", how="left", suffixes=("", "_feat"))
    if merged.empty:
        raise ValueError("Merged dataset is empty; check input files")

    cluster_ref = compute_cluster_reference(merged)
    rows = []
    for _, row in merged.iterrows():
        ref = cluster_ref.loc[row["cluster"]]
        details = build_report(row, ref)
        rows.append({
            "ENCODED_MCT": row["ENCODED_MCT"],
            "cluster": int(row["cluster"]),
            "report_text": format_report(row, details),
        })
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="군집 기반 개인화 리포트 생성")
    parser.add_argument("--cluster", type=Path, default=DEFAULT_CLUSTER_PATH, help="cluster_result.csv 경로")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES_PATH, help="전처리된 feature CSV 경로")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="리포트 저장 경로")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cluster_df = load_cluster_data(args.cluster)
    features_df = load_feature_data(args.features)
    reports = generate_reports(cluster_df, features_df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    reports.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"[REPORT] 리포트를 저장했습니다 -> {args.output}")


if __name__ == "__main__":
    main()
