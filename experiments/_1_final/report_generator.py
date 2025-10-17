# -*- coding: utf-8 -*-
"""Standalone 마케팅 리포트 헬퍼 (카페 방문 고객 특성 분석 전용)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
DEFAULT_CLUSTER_PATH = DATA_DIR / "cluster_result.csv"
DEFAULT_FEATURES_PATH = DATA_DIR / "cafe_features_processed.csv"

AGE_SEGMENT_COLUMNS: Dict[str, Tuple[str, str]] = {
    "M12_FME_1020_RAT": ("여성", "10-20대"),
    "M12_FME_30_RAT": ("여성", "30대"),
    "M12_FME_40_RAT": ("여성", "40대"),
    "M12_FME_50_RAT": ("여성", "50대"),
    "M12_FME_60_RAT": ("여성", "60대 이상"),
    "M12_MAL_1020_RAT": ("남성", "10-20대"),
    "M12_MAL_30_RAT": ("남성", "30대"),
    "M12_MAL_40_RAT": ("남성", "40대"),
    "M12_MAL_50_RAT": ("남성", "50대"),
    "M12_MAL_60_RAT": ("남성", "60대 이상"),
}

VISITOR_TYPE_COLUMNS: Dict[str, str] = {
    "RC_M1_SHC_RSD_UE_CLN_RAT": "주거 고객 비중",
    "RC_M1_SHC_WP_UE_CLN_RAT": "직장 고객 비중",
    "RC_M1_SHC_FLP_UE_CLN_RAT": "유동 고객 비중",
}

LOYALTY_METRICS: Dict[str, str] = {
    "MCT_UE_CLN_REU_RAT": "재방문 고객 비율",
    "MCT_UE_CLN_NEW_RAT": "신규 고객 비율",
    "LOYALTY_SCORE": "충성 고객 지수(0~100)",
}

AGE_SEGMENT_GAP_THRESHOLD = 3.0
VISITOR_GAP_THRESHOLD = 5.0
LOYALTY_GAP_THRESHOLD = 3.0

SEGMENT_RECOMMENDATIONS: Dict[Tuple[str, str], str] = {
    ("여성", "10-20대"): "SNS · 디저트 신규 메뉴를 강화해 젊은 여성 고객을 유지하세요.",
    ("여성", "30대"): "점심시간 모바일 주문 혜택으로 30대 여성 직장인을 공략하세요.",
    ("여성", "40대"): "웰니스·홈카페 패키지로 40대 여성 고객 체류 시간을 늘리세요.",
    ("여성", "50대"): "프리미엄 티·디카페인 라인으로 50대 여성 충성 고객을 확보하세요.",
    ("여성", "60대 이상"): "건강 음료와 편안한 좌석을 강조해 60대 여성 고객을 모으세요.",
    ("남성", "10-20대"): "스페셜티 체험 이벤트로 10-20대 남성 고객 유입을 늘리세요.",
    ("남성", "30대"): "출근·점심 테이크아웃 세트로 30대 남성 고객을 붙잡으세요.",
    ("남성", "40대"): "비즈니스 미팅 공간과 원두 기획전으로 40대 남성 수요를 공략하세요.",
    ("남성", "50대"): "프리미엄 원두·기프트 세트로 50대 남성 고객을 유지하세요.",
    ("남성", "60대 이상"): "전통 음료와 건강 메뉴로 60대 남성 고객 맞춤 프로모션을 진행하세요.",
}

VISIT_RECOMMENDATIONS: Dict[str, str] = {
    "RC_M1_SHC_RSD_UE_CLN_RAT": "주거 고객 대상 멤버십/적립 프로그램을 강화하세요.",
    "RC_M1_SHC_WP_UE_CLN_RAT": "출퇴근 시간대 한정 프로모션으로 직장 고객을 확보하세요.",
    "RC_M1_SHC_FLP_UE_CLN_RAT": "유동 고객을 위한 빠른 픽업과 간편 메뉴를 강조하세요.",
}

__all__ = ["generate_marketing_report1", "generate_report"]


def _project_path(path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (MODULE_DIR / candidate).resolve()


def _unique_existing_paths(candidates: List[Path | str | None]) -> List[Path]:
    existing: List[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = _project_path(candidate)
        key = resolved.as_posix()
        if key in seen:
            continue
        seen.add(key)
        if resolved.exists():
            existing.append(resolved)
    return existing


def _resolve_cluster_path(cluster_path: Optional[Path | str]) -> Path:
    candidates: List[Path | str | None] = [
        cluster_path,
        DEFAULT_CLUSTER_PATH,
    ]
    existing = _unique_existing_paths(candidates)
    if existing:
        return existing[0]
    raise FileNotFoundError("cluster_result.csv 경로를 찾을 수 없습니다.")


def _resolve_features_path(features_path: Optional[Path | str]) -> Path:
    candidates: List[Path | str | None] = [
        features_path,
        DEFAULT_FEATURES_PATH,
    ]
    existing = _unique_existing_paths(candidates)
    if existing:
        return existing[0]
    raise FileNotFoundError("cafe_features_processed.csv 경로를 찾을 수 없습니다.")


def _load_csv(path: Path, parse_dates: Optional[List[str]] = None) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", parse_dates=parse_dates)


def _deduplicate_merchants(df: pd.DataFrame) -> pd.DataFrame:
    if "ENCODED_MCT" not in df.columns:
        return df.copy()
    dedup = df.copy()
    if "snapshot_date" in dedup.columns:
        dedup["__snapshot"] = pd.to_datetime(dedup["snapshot_date"], errors="coerce")
        dedup.sort_values(["ENCODED_MCT", "__snapshot"], ascending=[True, False], inplace=True)
        dedup.drop_duplicates(subset=["ENCODED_MCT"], keep="first", inplace=True)
        dedup.drop(columns=["__snapshot"], inplace=True)
    else:
        dedup.drop_duplicates(subset=["ENCODED_MCT"], keep="first", inplace=True)
    return dedup


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def _format_percent(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}%"


def _format_score(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}점"


def _format_gap_pp(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}pp"


def _cluster_means(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    available = [col for col in columns if col in df.columns]
    if not available:
        raise ValueError("계산 가능한 지표가 없습니다. 입력 데이터를 확인하세요.")
    return df.groupby("cluster")[available].mean(numeric_only=True)


def _select_top_segments(row: pd.Series, cluster_row: pd.Series) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    for column, (gender, age_label) in AGE_SEGMENT_COLUMNS.items():
        if column not in row or column not in cluster_row:
            continue
        store_value = _to_float(row[column])
        cluster_value = _to_float(cluster_row[column])
        if store_value is None or cluster_value is None:
            continue
        gap = store_value - cluster_value
        segments.append(
            {
                "column": column,
                "gender": gender,
                "age_label": age_label,
                "label": f"{age_label} {gender}",
                "store_value": store_value,
                "cluster_avg": cluster_value,
                "gap": gap,
            }
        )
    if not segments:
        return []
    segments.sort(key=lambda item: (item["gap"], item["store_value"]), reverse=True)
    positives = [item for item in segments if item["gap"] >= AGE_SEGMENT_GAP_THRESHOLD]
    if len(positives) >= 2:
        return positives[:2]
    selected = positives + [item for item in segments if item not in positives]
    return selected[:2]


def _build_persona_summary(segments: List[Dict[str, Any]], revisit_gap: Optional[float]) -> str:
    if not segments:
        return "주요 고객층 정보를 찾지 못했습니다. 기본 고객 데이터를 확인해주세요."
    lines: List[str] = []
    first = segments[0]
    first_text = f"핵심 고객은 {first['label']}입니다"
    if first["gap"] >= AGE_SEGMENT_GAP_THRESHOLD:
        first_text += f" (클러스터 대비 {_format_gap_pp(first['gap'])})"
    lines.append(first_text)
    if len(segments) > 1:
        second = segments[1]
        second_text = f"보조 고객층은 {second['label']}"
        if second["gap"] >= AGE_SEGMENT_GAP_THRESHOLD:
            second_text += f"({_format_gap_pp(second['gap'])})"
        second_text += "입니다."
        lines.append(second_text)
    if revisit_gap is not None:
        if revisit_gap >= 0:
            lines.append("재방문 고객 비중이 평균 이상으로 안정적입니다.")
        elif revisit_gap <= -LOYALTY_GAP_THRESHOLD:
            lines.append("재방문 고객 비중이 평균 대비 낮아 관리가 필요합니다.")
    return " ".join(lines)


def _build_segment_payload(segments: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    payload: List[Dict[str, str]] = []
    for item in segments:
        payload.append(
            {
                "segment": item["label"],
                "store_value": _format_percent(item["store_value"]),
                "cluster_avg": _format_percent(item["cluster_avg"]),
                "gap": _format_gap_pp(item["gap"]),
            }
        )
    return payload


def _build_visit_mix(row: pd.Series, cluster_row: pd.Series) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for column, label in VISITOR_TYPE_COLUMNS.items():
        if column not in row or column not in cluster_row:
            continue
        store_value = _to_float(row[column])
        cluster_value = _to_float(cluster_row[column])
        if store_value is None or cluster_value is None:
            continue
        gap = store_value - cluster_value
        result.append(
            {
                "column": column,
                "factor": label,
                "store_value": store_value,
                "cluster_avg": cluster_value,
                "gap": gap,
            }
        )
    result.sort(key=lambda item: abs(item["gap"]), reverse=True)
    return result


def _build_loyalty_metrics(row: pd.Series, cluster_row: pd.Series) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    for column, label in LOYALTY_METRICS.items():
        if column not in row or column not in cluster_row:
            continue
        store_value = _to_float(row[column])
        cluster_value = _to_float(cluster_row[column])
        if store_value is None or cluster_value is None:
            continue
        details.append(
            {
                "column": column,
                "label": label,
                "store_value": store_value,
                "cluster_avg": cluster_value,
                "gap": store_value - cluster_value,
            }
        )
    return details


def _collect_customer_recommendations(
    segments: List[Dict[str, Any]],
    visit_mix: List[Dict[str, Any]],
    loyalty_details: List[Dict[str, Any]],
) -> List[str]:
    recommendations: List[str] = []
    for item in segments:
        rec = SEGMENT_RECOMMENDATIONS.get((item["gender"], item["age_label"]))
        if rec and rec not in recommendations:
            recommendations.append(rec)
    for item in visit_mix:
        if abs(item["gap"]) >= VISITOR_GAP_THRESHOLD:
            rec = VISIT_RECOMMENDATIONS.get(item["column"])
            if rec and rec not in recommendations:
                recommendations.append(rec)
    for item in loyalty_details:
        gap = item["gap"]
        if item["column"] == "MCT_UE_CLN_REU_RAT":
            if gap <= -LOYALTY_GAP_THRESHOLD:
                rec = "재방문 고객 대상 스탬프·적립 혜택을 강화하세요."
            elif gap >= LOYALTY_GAP_THRESHOLD:
                rec = "충성 고객을 위한 프리미엄 멤버십을 확장하세요."
            else:
                rec = None
        elif item["column"] == "MCT_UE_CLN_NEW_RAT" and gap >= LOYALTY_GAP_THRESHOLD:
            rec = "신규 고객을 멤버십에 연결해 재방문으로 전환하세요."
        elif item["column"] == "LOYALTY_SCORE" and gap <= -LOYALTY_GAP_THRESHOLD:
            rec = "전체 고객 충성도가 낮아 체류 경험 개선이 필요합니다."
        else:
            rec = None
        if rec and rec not in recommendations:
            recommendations.append(rec)
    if not recommendations:
        recommendations.append("핵심 고객층을 위한 맞춤 프로모션을 기획하세요.")
    return recommendations[:5]


def _evaluate_revisit_status(revisit_gap: Optional[float]) -> Tuple[str, str]:
    if revisit_gap is None:
        return (
            "재방문 데이터 확인 필요",
            "재방문 고객 지표가 없어 최신 데이터를 확인해주세요.",
        )

    gap_text = _format_gap_pp(revisit_gap)

    if revisit_gap >= LOYALTY_GAP_THRESHOLD:
        return (
            "재방문 고객층이 매우 탄탄해요",
            f"재방문 고객 비중이 클러스터 평균보다 {gap_text} 높습니다. 충성 고객 기반을 적극 활용하세요.",
        )

    if revisit_gap >= 0:
        return (
            "재방문 고객층이 안정적이에요",
            f"재방문 고객 비중이 클러스터 평균과 비슷합니다({gap_text}). 현재 수준을 유지하며 신규 전환 전략을 준비하세요.",
        )

    if revisit_gap <= -LOYALTY_GAP_THRESHOLD:
        return (
            "재방문 고객 확보가 시급해요",
            f"재방문 고객 비중이 클러스터 평균보다 {gap_text} 낮습니다. 충성 고객 케어 전략을 빠르게 실행하세요.",
        )

    return (
        "재방문 고객 보완이 필요해요",
        f"재방문 고객 비중이 평균보다 조금 낮습니다({gap_text}). 멤버십·스탬프 캠페인 등 보완 활동을 진행하세요.",
    )


def _build_insights(
    segments: List[Dict[str, Any]],
    visit_mix: List[Dict[str, Any]],
    loyalty_details: List[Dict[str, Any]],
) -> List[str]:
    insights: List[str] = []
    for item in segments:
        insights.append(f"{item['label']} 비중이 클러스터 평균 대비 {_format_gap_pp(item['gap'])}입니다.")
    for item in visit_mix:
        if abs(item["gap"]) >= VISITOR_GAP_THRESHOLD:
            direction = "높습니다" if item["gap"] > 0 else "낮습니다"
            insights.append(
                f"{item['factor']}이(가) 클러스터 평균보다 {_format_gap_pp(item['gap'])}로 {direction}."
            )
    for item in loyalty_details:
        if item["column"] == "MCT_UE_CLN_REU_RAT" and abs(item["gap"]) >= LOYALTY_GAP_THRESHOLD:
            direction = "높습니다" if item["gap"] > 0 else "낮습니다"
            insights.append(
                f"{item['label']}이(가) 클러스터 평균보다 {_format_gap_pp(item['gap'])}로 {direction}."
            )
    return insights


def _get_store_metadata(merchant_id: str, feature_df: pd.DataFrame) -> Dict[str, Any]:
    matched = feature_df.loc[feature_df["ENCODED_MCT"] == merchant_id]
    if matched.empty:
        return {}
    row = matched.iloc[0]
    metadata: Dict[str, Any] = {}
    if "MCT_NM" in row and not pd.isna(row["MCT_NM"]):
        metadata["store_name"] = str(row["MCT_NM"])
    if "TRADE_AREA" in row and not pd.isna(row["TRADE_AREA"]):
        metadata["trade_area"] = str(row["TRADE_AREA"])
    if "MCT_SIGUNGU_NM" in row and not pd.isna(row["MCT_SIGUNGU_NM"]):
        metadata["region"] = str(row["MCT_SIGUNGU_NM"])
    for column in ("is_chain", "has_delivery"):
        if column in row and not pd.isna(row[column]):
            try:
                metadata[column] = bool(int(row[column]))
            except (TypeError, ValueError):
                metadata[column] = bool(row[column])
    if "snapshot_date" in row and not pd.isna(row["snapshot_date"]):
        metadata["snapshot_date"] = str(row["snapshot_date"])
    return metadata


def generate_marketing_report1(
    store_code: str,
    *,
    cluster_path: Optional[Path | str] = None,
    features_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    cluster_csv = _resolve_cluster_path(cluster_path)
    features_csv = _resolve_features_path(features_path)

    cluster_df = _deduplicate_merchants(_load_csv(cluster_csv))
    feature_df = _deduplicate_merchants(_load_csv(features_csv))

    merged = cluster_df.merge(feature_df, on="ENCODED_MCT", how="left", suffixes=("", "_feat"))
    if merged.empty:
        raise ValueError("클러스터와 feature 데이터를 병합했지만 결과가 없습니다.")

    merged = _deduplicate_merchants(merged)
    target = merged.loc[merged["ENCODED_MCT"] == store_code]
    if target.empty:
        return {
            "error": f"ENCODED_MCT '{store_code}'에 해당하는 매장을 찾을 수 없습니다.",
            "store_code": store_code
        }

    row = target.iloc[0]
    cluster_id = int(row["cluster"])

    metric_columns = list(AGE_SEGMENT_COLUMNS.keys()) + list(VISITOR_TYPE_COLUMNS.keys()) + list(
        LOYALTY_METRICS.keys()
    )
    cluster_means = _cluster_means(merged, metric_columns)
    cluster_row = cluster_means.loc[cluster_id]

    loyalty_details = _build_loyalty_metrics(row, cluster_row)
    revisit_detail = next((item for item in loyalty_details if item["column"] == "MCT_UE_CLN_REU_RAT"), None)
    revisit_gap = revisit_detail["gap"] if revisit_detail else None

    segments = _select_top_segments(row, cluster_row)
    visit_mix = _build_visit_mix(row, cluster_row)

    persona_summary = _build_persona_summary(segments, revisit_gap)
    segment_payload = _build_segment_payload(segments)
    visit_payload = [
        {
            "factor": item["factor"],
            "store_value": _format_percent(item["store_value"]),
            "cluster_avg": _format_percent(item["cluster_avg"]),
            "gap": _format_gap_pp(item["gap"]),
        }
        for item in visit_mix
    ]

    loyalty_payload: List[Dict[str, str]] = []
    for item in loyalty_details:
        if item["column"] == "LOYALTY_SCORE":
            store_value_str = _format_score(item["store_value"])
            cluster_value_str = _format_score(item["cluster_avg"])
            gap_str = f"{item['gap']:+.2f}점"
        else:
            store_value_str = _format_percent(item["store_value"])
            cluster_value_str = _format_percent(item["cluster_avg"])
            gap_str = _format_gap_pp(item["gap"])
        loyalty_payload.append(
            {
                "metric": item["label"],
                "store_value": store_value_str,
                "cluster_avg": cluster_value_str,
                "gap": gap_str,
            }
        )

    recommendations = _collect_customer_recommendations(segments, visit_mix, loyalty_details)
    status, status_detail = _evaluate_revisit_status(revisit_gap)

    metadata = _get_store_metadata(store_code, feature_df)
    metadata["cluster"] = cluster_id

    trade_area_value = row.get("TRADE_AREA") if "TRADE_AREA" in row else None
    trade_area = str(trade_area_value) if pd.notna(trade_area_value) else None

    analysis: Dict[str, Any] = {
        "summary": persona_summary,
        "persona": persona_summary,
        "cluster": cluster_id,
        "top_segments": segment_payload,
        "visit_mix": visit_payload,
        "loyalty": {
            "summary": status_detail,
            "metrics": loyalty_payload,
        },
        "insights": _build_insights(segments, visit_mix, loyalty_details),
    }
    if trade_area is not None:
        analysis["trade_area"] = trade_area

    # ----------------------------------------------------------------------
    # ✅ Streamlit UI에서 표시할 요약 텍스트 생성
    # ----------------------------------------------------------------------
    insights_preview = analysis["insights"][:2]
    insights_text = "\n".join([f"   • {i}" for i in insights_preview])
    overview_text = f"""
📍 **매장명:** {metadata.get('store_name', '-')}
📊 **상태:** {status}
💬 **요약:** {status_detail}

👥 **핵심 고객 요약**
{analysis.get('summary', '-')}

🗺️ **상권 클러스터:** {analysis.get('cluster', '-')}

💡 **주요 인사이트 (상위 2개)**
{insights_text}
""".strip()

    # ----------------------------------------------------------------------
    # ✅ 최종 반환
    # ----------------------------------------------------------------------
    return {
        "store_code": store_code,
        "store_name": metadata.get("store_name"),
        "status": status,
        "status_detail": status_detail,
        "analysis": analysis,
        "recommendations": recommendations,
        "metadata": metadata,
        "overview_text": overview_text,  # ✅ Streamlit 표출용 요약 텍스트
    }


def generate_report(
    store_code: str,
    *,
    kind: str = "cluster",
    **kwargs: Any,
) -> Dict[str, Any]:
    if kind.lower() != "cluster":
        raise ValueError(f"지원하지 않는 리포트 종류입니다: {kind!r}")
    return generate_marketing_report1(store_code, **kwargs)