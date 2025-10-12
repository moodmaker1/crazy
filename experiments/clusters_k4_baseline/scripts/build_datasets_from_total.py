from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_pipeline.total_dataset import (
    CAFE_CATEGORIES,
    load_store_metadata,
    load_total_dataset,
    prepare_latest_snapshot,
    save_utf8_csv,
)
from src.feature_engineering import build_feature_engineering_pipeline
from src.preprocess import drop_unnecessary


def build_datasets(
    source: Path,
    store_meta: Path,
    latest_out: Path,
    processed_out: Path,
    model_input_out: Path,
    categories: tuple[str, ...] = CAFE_CATEGORIES,
) -> None:
    print(f"[INFO] Loading total dataset from {source}")
    total_df = load_total_dataset(source)

    print(f"[INFO] Loading store metadata from {store_meta}")
    store_df = load_store_metadata(store_meta)

    print("[INFO] Preparing latest snapshot for cafe categories")
    latest_snapshot = prepare_latest_snapshot(total_df, store_df, categories=categories)

    print(f"[SAVE] Latest cafe snapshot -> {latest_out}")
    save_utf8_csv(latest_snapshot, latest_out)

    print(f"[SAVE] Processed dataset -> {processed_out}")
    save_utf8_csv(latest_snapshot, processed_out)

    print("[INFO] Building model input features")
    feature_df = drop_unnecessary(latest_snapshot.copy(), keep_meta=False)
    feature_pipeline = build_feature_engineering_pipeline()
    transformed = feature_pipeline.fit_transform(feature_df)
    transformed_df = pd.DataFrame(transformed)

    model_input_out.parent.mkdir(parents=True, exist_ok=True)
    transformed_df.to_csv(model_input_out, index=False, encoding="utf-8-sig")
    print(f"[SAVE] Model input dataset -> {model_input_out}")

    print(f"[INFO] Cafe stores processed: {len(latest_snapshot):,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cafe datasets from total_data_final CSV")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/total/total_data_final.csv"),
        help="Path to total_data_final CSV",
    )
    parser.add_argument(
        "--store-meta",
        type=Path,
        default=Path("real_raw/big_data_set1_f.csv"),
        help="Path to store metadata CSV (big_data_set1_f.csv)",
    )
    parser.add_argument(
        "--latest-out",
        type=Path,
        default=Path("data/aggregated/cafe_marketing_latest.csv"),
        help="Where to save the latest snapshot CSV",
    )
    parser.add_argument(
        "--processed-out",
        type=Path,
        default=Path("data/processed/cafe_features_processed.csv"),
        help="Where to save the processed dataset",
    )
    parser.add_argument(
        "--model-input-out",
        type=Path,
        default=Path("data/processed/cafe_features_model_input.csv"),
        help="Where to save the model input dataset",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_datasets(
        source=args.source,
        store_meta=args.store_meta,
        latest_out=args.latest_out,
        processed_out=args.processed_out,
        model_input_out=args.model_input_out,
    )


if __name__ == "__main__":
    main()
