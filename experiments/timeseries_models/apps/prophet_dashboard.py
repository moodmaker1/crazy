from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DEFAULT_OUTPUT_DIR = Path("experiments") / "timeseries_models" / "outputs"
DEFAULT_PANEL_PATH = DEFAULT_OUTPUT_DIR / "cafe_timeseries_panel.csv"
DEFAULT_FORECAST_PATH = DEFAULT_OUTPUT_DIR / "prophet" / "prophet_forecast.csv"
DEFAULT_METRICS_PATH = DEFAULT_OUTPUT_DIR / "prophet" / "prophet_metrics.csv"


@st.cache_data(show_spinner=False)
def load_panel(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"ENCODED_MCT": str})
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce")
    return df.dropna(subset=["snapshot_date"]).sort_values(["ENCODED_MCT", "snapshot_date"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_forecast(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"ENCODED_MCT": str})
    df["ds"] = pd.to_datetime(df["ds"], errors="coerce")
    return df.dropna(subset=["ds"]).sort_values(["ENCODED_MCT", "ds"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_metrics(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"ENCODED_MCT": str})


def build_chart(history: pd.DataFrame, forecast: pd.DataFrame) -> alt.Chart:

    history_chart = alt.Chart(history).mark_line(color="#1f77b4").encode(
        x=alt.X("snapshot_date:T", title="Date"),
        y=alt.Y("sales_grade:Q", title="Sales grade"),
    )

    forecast_line = alt.Chart(forecast).mark_line(color="#ff7f0e", strokeDash=[4, 3]).encode(
        x="ds:T",
        y="yhat:Q",
    )

    interval = alt.Chart(forecast).mark_area(color="#ff7f0e", opacity=0.2).encode(
        x="ds:T",
        y="yhat_lower:Q",
        y2="yhat_upper:Q",
    )

    return (history_chart + interval + forecast_line).properties(title="Actual vs Forecast")


def main() -> None:
    st.set_page_config(page_title="Prophet Forecast Dashboard", layout="wide")

    panel_path = Path(st.secrets.get("panel_path", DEFAULT_PANEL_PATH))
    forecast_path = Path(st.secrets.get("forecast_path", DEFAULT_FORECAST_PATH))
    metrics_path = Path(st.secrets.get("metrics_path", DEFAULT_METRICS_PATH))

    try:
        panel = load_panel(panel_path)
        forecast = load_forecast(forecast_path)
        metrics = load_metrics(metrics_path)
    except FileNotFoundError as exc:
        st.error(f"Required file not found: {exc}")
        return

    st.sidebar.header("Filters")
    threshold = st.sidebar.slider("Outlier MAE threshold", 0.0, 5.0, 1.0, 0.1)
    outlier_only = st.sidebar.checkbox("Show outlier stores only", value=False)

    all_store_ids = metrics["ENCODED_MCT"].tolist()
    outlier_ids = metrics.loc[metrics["mae"] >= threshold, "ENCODED_MCT"].tolist()
    store_options = outlier_ids if outlier_only and outlier_ids else all_store_ids
    default_index = 0
    if outlier_only and outlier_ids:
        default_index = 0
    elif outlier_ids:
        default_id = outlier_ids[0]
        if default_id in store_options:
            default_index = store_options.index(default_id)

    store_id = st.sidebar.selectbox("Store ID", store_options, index=default_index if store_options else 0)

    if not store_options:
        st.warning("No stores available with the current filters.")
        return

    st.title("Prophet Forecast Dashboard")

    metrics_row = metrics.loc[metrics["ENCODED_MCT"] == store_id]
    cols = st.columns(3)
    if not metrics_row.empty:
        row = metrics_row.iloc[0]
        cols[0].metric("MAE", f"{row['mae']:.3f}")
        cols[1].metric("RMSE", f"{row['rmse']:.3f}")
        cols[2].metric("MAPE", f"{row['mape']:.1f}%")
    else:
        for col in cols:
            col.metric("-", "N/A")

    history = panel.loc[panel["ENCODED_MCT"] == store_id]
    future = forecast.loc[forecast["ENCODED_MCT"] == store_id]

    if history.empty and future.empty:
        st.warning("Selected store has no data in panel or forecast files.")
    else:
        chart = build_chart(history, future)
        st.altair_chart(chart, use_container_width=True)

    st.subheader("Top Outliers by MAE")
    top_outliers = (
        metrics.loc[metrics["mae"] >= threshold]
        .nlargest(10, "mae")
        .rename(columns={"ENCODED_MCT": "Store", "mae": "MAE", "rmse": "RMSE", "mape": "MAPE"})
    )
    if top_outliers.empty:
        st.info("No stores exceed the current MAE threshold.")
    else:
        st.dataframe(top_outliers.reset_index(drop=True))


if __name__ == "__main__":
    main()
