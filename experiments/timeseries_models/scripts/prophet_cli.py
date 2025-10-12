from __future__ import annotations

import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

DEFAULT_OUTPUT_DIR = Path("experiments") / "timeseries_models" / "outputs"
DEFAULT_PANEL_PATH = DEFAULT_OUTPUT_DIR / "cafe_timeseries_panel.csv"
DEFAULT_FORECAST_PATH = DEFAULT_OUTPUT_DIR / "prophet" / "prophet_forecast.csv"
DEFAULT_METRICS_PATH = DEFAULT_OUTPUT_DIR / "prophet" / "prophet_metrics.csv"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, dtype={"ENCODED_MCT": str})


def load_panel(path: Path) -> pd.DataFrame:
    panel = _read_csv(path)
    panel["snapshot_date"] = pd.to_datetime(panel["snapshot_date"], errors="coerce")
    panel = panel.dropna(subset=["snapshot_date"])
    return panel.sort_values(["ENCODED_MCT", "snapshot_date"]).reset_index(drop=True)


def load_forecast(path: Path) -> pd.DataFrame:
    forecast = _read_csv(path)
    forecast["ds"] = pd.to_datetime(forecast["ds"], errors="coerce")
    forecast = forecast.dropna(subset=["ds"])
    return forecast.sort_values(["ENCODED_MCT", "ds"]).reset_index(drop=True)


def load_metrics(path: Path) -> pd.DataFrame:
    metrics = _read_csv(path)
    return metrics.sort_values("mae", ascending=False).reset_index(drop=True)


def format_store_list(rows: pd.DataFrame) -> str:
    lines = []
    for _, row in rows.iterrows():
        mae = row.get("mae", float("nan"))
        rmse = row.get("rmse", float("nan"))
        mape = row.get("mape", float("nan"))
        lines.append(
            f"{row['ENCODED_MCT']}: MAE={mae:.3f}, RMSE={rmse:.3f}, MAPE={mape:.1f}%"
        )
    return "\n".join(lines)



def plot_store(
    panel: pd.DataFrame,
    forecast: pd.DataFrame,
    metrics: pd.DataFrame,
    store_id: str,
    save_path: Path | None,
    show: bool,
) -> None:
    history = panel[panel["ENCODED_MCT"] == store_id]
    future = forecast[forecast["ENCODED_MCT"] == store_id]

    if history.empty and future.empty:
        raise ValueError(f"Store {store_id} not found in panel or forecast data")

    fig, ax = plt.subplots(figsize=(10, 5))
    if not history.empty:
        ax.plot(history["snapshot_date"], history["sales_grade"], label="Actual", color="#1f77b4")
    if not future.empty:
        ax.plot(future["ds"], future["yhat"], label="Forecast", color="#ff7f0e", linestyle="--")
        ax.fill_between(
            future["ds"],
            future["yhat_lower"],
            future["yhat_upper"],
            color="#ff7f0e",
            alpha=0.2,
            label="Forecast interval",
        )

    metric_row = metrics[metrics["ENCODED_MCT"] == store_id]
    title = f"Store {store_id}"
    if not metric_row.empty:
        row = metric_row.iloc[0]
        title += f" | MAE={row['mae']:.3f}, RMSE={row['rmse']:.3f}, MAPE={row['mape']:.1f}%"
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Sales grade")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.autofmt_xdate()

    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=200, bbox_inches="tight")
        print(f"Saved plot -> {save_path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect Prophet forecasts, list outliers, and plot store-level results."
    )
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL_PATH, help="Panel CSV path")
    parser.add_argument(
        "--forecast",
        type=Path,
        default=DEFAULT_FORECAST_PATH,
        help="Prophet forecast CSV path",
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        default=DEFAULT_METRICS_PATH,
        help="Prophet metrics CSV path",
    )
    parser.add_argument("--store-id", type=str, help="Store ID to plot")
    parser.add_argument(
        "--save-dir",
        type=Path,
        help="Optional directory to save the plot as <store_id>.png",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display matplotlib window (set when running in an environment with GUI)",
    )
    parser.add_argument(
        "--top-outliers",
        type=int,
        default=0,
        help="List top-N outliers by MAE (largest MAE first)",
    )
    parser.add_argument(
        "--outlier-threshold",
        type=float,
        default=1.0,
        help="MAE threshold used to flag outliers",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    panel = load_panel(args.panel)
    forecast = load_forecast(args.forecast)
    metrics = load_metrics(args.metrics)

    if args.top_outliers:
        outliers = metrics[metrics["mae"] >= args.outlier_threshold]
        outliers = outliers.nlargest(args.top_outliers, "mae")
        if outliers.empty:
            print(
                f"No stores exceed MAE threshold {args.outlier_threshold}."
            )
        else:
            print("Outliers by MAE:")
            print(format_store_list(outliers))

    if args.store_id:
        save_path = None
        if args.save_dir is not None:
            save_path = args.save_dir / f"{args.store_id}.png"
        plot_store(panel, forecast, metrics, args.store_id, save_path, args.show)
    elif not args.top_outliers:
        print("Nothing to do: provide --store-id to plot or --top-outliers to list stores.")


if __name__ == "__main__":
    main()
