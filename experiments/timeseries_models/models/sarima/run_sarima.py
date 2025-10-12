# -*- coding: utf-8 -*-
"""매장별 SARIMA 예측 스크립트 (statsmodels 기반)."""
from __future__ import annotations

import argparse
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from numpy.linalg import LinAlgError

try:
    from statsmodels.tools.sm_exceptions import ConvergenceWarning
    from statsmodels.tsa.statespace.sarimax import SARIMAX
except ImportError as exc:  # pragma: no cover
    raise SystemExit("statsmodels 라이브러리가 필요합니다. `pip install statsmodels` 로 설치해주세요.") from exc

warnings.filterwarnings("ignore", message="Too few observations to estimate starting parameters")
warnings.filterwarnings("ignore", message="Non-invertible starting MA parameters")
warnings.filterwarnings("ignore", message="Non-stationary starting autoregressive parameters")
warnings.filterwarnings("ignore", category=ConvergenceWarning)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = PROJECT_ROOT / "experiments" / "timeseries_models" / "outputs"
DEFAULT_PANEL_PATH = DATA_DIR / "cafe_timeseries_panel.csv"
DEFAULT_OUT_DIR = PROJECT_ROOT / "experiments" / "timeseries_models" / "outputs" / "sarima"
MIN_HISTORY_DEFAULT = 12
EVAL_WINDOW_DEFAULT = 3
FORECAST_HORIZON_DEFAULT = 3
SEASONAL_PERIOD = 12
VALUE_FLOOR = 0.0
VALUE_CAP = 1.05
CONF_ALPHA = 0.05

ORDER_GRID: List[Tuple[int, int, int]] = [
    (0, 1, 1),
    (1, 0, 1),
    (1, 1, 1),
    (0, 1, 0),
    (1, 1, 0),
]


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


def split_history(series: pd.DataFrame, eval_window: int) -> tuple[pd.Series, pd.Series]:
    target = series.set_index("snapshot_date")["sales_grade"].astype(float)
    target = target.asfreq("MS")
    target = target.interpolate(method="linear", limit_direction="both")
    if len(target) <= eval_window:
        return target, pd.Series(dtype=float)
    return target.iloc[:-eval_window], target.iloc[-eval_window:]


def compute_metrics(actual: Iterable[float], predicted: Iterable[float]) -> Dict[str, float]:
    actual_arr = np.asarray(list(actual), dtype=float)
    pred_arr = np.asarray(list(predicted), dtype=float)
    if actual_arr.size == 0:
        return {"mae": np.nan, "rmse": np.nan, "mape": np.nan}
    diff = actual_arr - pred_arr
    mae = np.mean(np.abs(diff))
    rmse = np.sqrt(np.mean(diff ** 2))
    with np.errstate(divide="ignore", invalid="ignore"):
        denominator = np.where(actual_arr == 0, np.nan, actual_arr)
        mape = np.nanmean(np.abs(diff) / denominator) * 100
    return {"mae": float(mae), "rmse": float(rmse), "mape": float(mape)}


def _candidate_seasonal_orders(length: int) -> List[Tuple[int, int, int, int]]:
    candidates: List[Tuple[int, int, int, int]] = [(0, 0, 0, 0)]
    if length >= SEASONAL_PERIOD:
        candidates.append((1, 0, 0, SEASONAL_PERIOD))
        candidates.append((0, 1, 1, SEASONAL_PERIOD))
    if length >= 2 * SEASONAL_PERIOD:
        candidates.append((1, 1, 1, SEASONAL_PERIOD))
    return candidates


def fit_sarima(history: pd.Series) -> Optional[object]:
    series = history.astype(float)
    best_model = None
    best_aic = float("inf")

    seasonal_grid = _candidate_seasonal_orders(len(series))

    for order in ORDER_GRID:
        for seasonal_order in seasonal_grid:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    model = SARIMAX(
                        series,
                        order=order,
                        seasonal_order=seasonal_order,
                        enforce_stationarity=False,
                        enforce_invertibility=False,
                    )
                    fitted = model.fit(disp=False, maxiter=200)
            except (LinAlgError, ValueError, IndexError, TypeError):
                continue

            if not np.isfinite(fitted.aic):
                continue
            if fitted.aic < best_aic:
                best_aic = fitted.aic
                best_model = fitted

    return best_model


def _build_forecast_frame(store_id: str, forecast_obj, horizon: int) -> pd.DataFrame:
    pred_mean = forecast_obj.predicted_mean.iloc[:horizon]
    conf_int = forecast_obj.conf_int(alpha=CONF_ALPHA).iloc[:horizon]

    if isinstance(pred_mean.index, pd.PeriodIndex):
        index = pred_mean.index.to_timestamp()
    else:
        index = pd.DatetimeIndex(pred_mean.index)

    return pd.DataFrame(
        {
            "ENCODED_MCT": store_id,
            "ds": index,
            "yhat": np.clip(pred_mean.to_numpy(), VALUE_FLOOR, VALUE_CAP),
            "yhat_lower": np.clip(conf_int.iloc[:, 0].to_numpy(), VALUE_FLOOR, VALUE_CAP),
            "yhat_upper": np.clip(conf_int.iloc[:, 1].to_numpy(), VALUE_FLOOR, VALUE_CAP),
        }
    )


def forecast_store(series: pd.DataFrame, horizon: int, eval_window: int) -> ForecastResult:
    store_id = series["ENCODED_MCT"].iloc[0]
    history, eval_set = split_history(series, eval_window)

    model = fit_sarima(history)

    if model is None:
        last_value = history.iloc[-1]
        forecast_index = pd.date_range(history.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
        forecast_df = pd.DataFrame(
            {
                "ENCODED_MCT": store_id,
                "ds": forecast_index,
                "yhat": np.clip(np.full(horizon, last_value), VALUE_FLOOR, VALUE_CAP),
                "yhat_lower": np.clip(np.full(horizon, last_value), VALUE_FLOOR, VALUE_CAP),
                "yhat_upper": np.clip(np.full(horizon, last_value), VALUE_FLOOR, VALUE_CAP),
            }
        )
        metrics = {"mae": np.nan, "rmse": np.nan, "mape": np.nan}
        if not eval_set.empty:
            naive = np.full(len(eval_set), last_value)
            metrics = compute_metrics(eval_set.values, naive)
        metrics.update(
            {
                "ENCODED_MCT": store_id,
                "train_points": len(history),
                "eval_points": len(eval_set),
                "model": "naive_last_value",
            }
        )
        return ForecastResult(store_id, forecast_df, metrics)

    future_forecast = model.get_forecast(steps=horizon)
    forecast_df = _build_forecast_frame(store_id, future_forecast, horizon)

    metrics = {"mae": np.nan, "rmse": np.nan, "mape": np.nan}
    if not eval_set.empty:
        eval_forecast = model.get_forecast(steps=len(eval_set))
        eval_mean = eval_forecast.predicted_mean.iloc[: len(eval_set)]
        metrics = compute_metrics(eval_set.values, eval_mean.values)

    metrics.update(
        {
            "ENCODED_MCT": store_id,
            "train_points": len(history),
            "eval_points": len(eval_set),
            "model": str(model.model_orders),
        }
    )
    return ForecastResult(store_id=store_id, forecast=forecast_df, metrics=metrics)


def run_sarima(panel: pd.DataFrame, min_history: int, horizon: int, eval_window: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    results: List[ForecastResult] = []
    for _, group in panel.groupby("ENCODED_MCT"):
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
    parser = argparse.ArgumentParser(description="SARIMA 기반 매출 등급 예측")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL_PATH, help="시계열 패널 CSV 경로")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="결과 디렉터리")
    parser.add_argument("--min-history", type=int, default=MIN_HISTORY_DEFAULT, help="최소 학습 월 수")
    parser.add_argument("--horizon", type=int, default=FORECAST_HORIZON_DEFAULT, help="예측 기간(개월)")
    parser.add_argument("--eval-window", type=int, default=EVAL_WINDOW_DEFAULT, help="검증 윈도 크기")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    panel = load_panel(args.panel)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    forecast_df, metrics_df = run_sarima(
        panel,
        min_history=args.min_history,
        horizon=args.horizon,
        eval_window=args.eval_window,
    )

    forecast_path = args.out_dir / "sarima_forecast.csv"
    metrics_path = args.out_dir / "sarima_metrics.csv"
    forecast_df.to_csv(forecast_path, index=False, encoding="utf-8-sig")
    metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    print(f"[SARIMA] 예측 결과 저장 -> {forecast_path}")
    print(f"[SARIMA] 평가 지표 저장 -> {metrics_path}")


if __name__ == "__main__":
    main()
