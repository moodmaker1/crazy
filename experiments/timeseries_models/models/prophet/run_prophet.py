# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

try:
    from prophet import Prophet
except ImportError as exc:  # pragma: no cover
    raise SystemExit("prophet 라이브러리가 없습니다. `pip install prophet` 로 다시 설치해주세요.") from exc

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = PROJECT_ROOT / "experiments" / "timeseries_models" / "outputs"
DEFAULT_PANEL_PATH = DATA_DIR / "cafe_timeseries_panel.csv"
DEFAULT_OUT_DIR = PROJECT_ROOT / "experiments" / "timeseries_models" / "outputs" / "prophet"
MIN_HISTORY_DEFAULT = 12
EVAL_WINDOW_DEFAULT = 3
FORECAST_HORIZON_DEFAULT = 3
CAP_VALUE = 1.05
FLOOR_VALUE = 0.0
YEARLY_MIN_POINTS = 18
YEARLY_FOURIER_ORDER = 3


@dataclass
class ForecastResult:
    store_id: str
    forecast: pd.DataFrame
    metrics: Dict[str, float]


def load_panel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, encoding="utf-8")
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce")
    df = df.dropna(subset=["snapshot_date"])
    return df.sort_values(["ENCODED_MCT", "snapshot_date"]).reset_index(drop=True)


def split_history(series: pd.DataFrame, eval_window: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(series) <= eval_window:
        return series, pd.DataFrame(columns=series.columns)
    return series.iloc[:-eval_window], series.iloc[-eval_window:]


def compute_metrics(actual: pd.Series, predicted: pd.Series) -> Dict[str, float]:
    actual_arr = np.asarray(actual, dtype=float)
    pred_arr = np.asarray(predicted, dtype=float)
    if actual_arr.size == 0:
        return {"mae": np.nan, "rmse": np.nan, "mape": np.nan}
    diff = actual_arr - pred_arr
    mae = np.mean(np.abs(diff))
    rmse = np.sqrt(np.mean(diff ** 2))
    with np.errstate(divide="ignore", invalid="ignore"):
        denominator = np.where(actual_arr == 0, np.nan, actual_arr)
        mape = np.nanmean(np.abs(diff) / denominator) * 100
    return {"mae": float(mae), "rmse": float(rmse), "mape": float(mape)}


def build_prophet(history_length: int) -> Prophet:
    model = Prophet(
        growth="logistic",
        weekly_seasonality=False,
        daily_seasonality=False,
    )
    if history_length >= YEARLY_MIN_POINTS:
        model.add_seasonality(name="yearly", period=365.25, fourier_order=YEARLY_FOURIER_ORDER)
    return model


def _add_bounds(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cap"] = CAP_VALUE
    df["floor"] = FLOOR_VALUE
    return df


def forecast_store(series: pd.DataFrame, horizon: int, eval_window: int) -> ForecastResult:
    store_id = series["ENCODED_MCT"].iloc[0]
    data = series[["snapshot_date", "sales_grade"]].rename(columns={"snapshot_date": "ds", "sales_grade": "y"})
    history, eval_set = split_history(data, eval_window)

    history = _add_bounds(history)
    if not eval_set.empty:
        eval_set = _add_bounds(eval_set)

    model = build_prophet(len(history))
    model.fit(history)

    future = model.make_future_dataframe(periods=horizon, freq="MS", include_history=False)
    future = _add_bounds(future)
    forecast = model.predict(future)
    forecast = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    forecast[["yhat", "yhat_lower", "yhat_upper"]] = forecast[["yhat", "yhat_lower", "yhat_upper"]].clip(FLOOR_VALUE, CAP_VALUE)
    forecast.insert(0, "ENCODED_MCT", store_id)

    metrics = {"mae": np.nan, "rmse": np.nan, "mape": np.nan}
    if not eval_set.empty:
        eval_future = model.predict(eval_set[["ds", "cap", "floor"]])
        metrics = compute_metrics(eval_set["y"], eval_future["yhat"])

    metrics.update({
        "ENCODED_MCT": store_id,
        "train_points": len(history),
        "eval_points": len(eval_set),
    })
    return ForecastResult(store_id=store_id, forecast=forecast, metrics=metrics)


def run_prophet(panel: pd.DataFrame, min_history: int, horizon: int, eval_window: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    results: List[ForecastResult] = []
    grouped = panel.groupby("ENCODED_MCT")
    for _, group in grouped:
        if len(group) < min_history:
            continue
        group = group.sort_values("snapshot_date")
        result = forecast_store(group, horizon=horizon, eval_window=eval_window)
        results.append(result)

    if not results:
        raise ValueError("학습 가능한 매장이 없습니다.")

    forecast_df = pd.concat([r.forecast for r in results], ignore_index=True)
    metrics_df = pd.DataFrame([r.metrics for r in results])
    return forecast_df, metrics_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prophet 기반 매출 등급 예측")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL_PATH, help="시계열 패널 CSV 경로")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="결과 디렉터리")
    parser.add_argument("--min-history", type=int, default=MIN_HISTORY_DEFAULT, help="최소 학습 월 수")
    parser.add_argument("--horizon", type=int, default=FORECAST_HORIZON_DEFAULT, help="예측 기간(개월)")
    parser.add_argument("--eval-window", type=int, default=EVAL_WINDOW_DEFAULT, help="검증에 사용할 최근 개월 수")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    panel = load_panel(args.panel)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    forecast_df, metrics_df = run_prophet(
        panel,
        min_history=args.min_history,
        horizon=args.horizon,
        eval_window=args.eval_window,
    )

    forecast_path = args.out_dir / "prophet_forecast.csv"
    metrics_path = args.out_dir / "prophet_metrics.csv"
    forecast_df.to_csv(forecast_path, index=False, encoding="utf-8-sig")
    metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    print(f"[PROPHET] 예측 결과 저장 -> {forecast_path}")
    print(f"[PROPHET] 평가 지표 저장 -> {metrics_path}")


if __name__ == "__main__":
    main()
