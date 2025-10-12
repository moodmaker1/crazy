from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    DEFAULT_RANDOM_STATE,
    MODEL_FILENAME,
    create_run_directory,
    get_processed_dataset_path,
    setup_run_logger,
)
from src.feature_engineering import build_feature_engineering_pipeline
from src.preprocess import build_preprocessor, drop_unnecessary, load_dataframe
from src.model_selection import build_pipeline, evaluate_embeddings

DATA_PATH = get_processed_dataset_path()
RANDOM_STATE = DEFAULT_RANDOM_STATE
LOWVAR_THRESHOLD = 1e-6
CORR_THRESHOLD = 0.9
PCA_COMPONENTS = 20
CLUSTER_GRID = [3, 4, 5, 6]
ESTIMATORS = ["kmeans", "gmm"]


def main() -> None:
    run_dir = create_run_directory(prefix="model_selection")
    logger = setup_run_logger(run_dir, name="cafe_clustering.model_selection")
    metrics_path = run_dir / "model_compare_metrics.csv"
    best_model_path = run_dir / MODEL_FILENAME

    logger.info("Using dataset: %s", DATA_PATH)
    logger.info("Outputs will be stored in %s", run_dir)

    df = load_dataframe(DATA_PATH, encoding="utf-8-sig")
    if df.empty:
        raise ValueError("Empty dataframe")

    if "MCT_BRD_NUM" in df.columns:
        df["is_chain"] = df["MCT_BRD_NUM"].notna().astype(int)
    else:
        df["is_chain"] = 0

    if "DLV_SAA_RAT" in df.columns:
        df["has_delivery"] = df["DLV_SAA_RAT"].fillna(0).gt(0).astype(int)

    X = drop_unnecessary(df.copy())

    probe_pipeline = build_feature_engineering_pipeline(
        lowvar_thresh=LOWVAR_THRESHOLD,
        corr_thresh=CORR_THRESHOLD,
    )
    X_probed = probe_pipeline.fit_transform(X)
    dropped = probe_pipeline.named_steps["prune"].columns_to_drop_
    if dropped:
        logger.info("Feature pipeline will drop columns: %s", sorted(dropped))

    feature_pipeline = build_feature_engineering_pipeline(
        lowvar_thresh=LOWVAR_THRESHOLD,
        corr_thresh=CORR_THRESHOLD,
    )
    preprocessor, _, _ = build_preprocessor(X_probed)

    results: list[dict] = []
    for estimator in ESTIMATORS:
        for k in CLUSTER_GRID:
            pipe = build_pipeline(
                preprocessor=preprocessor,
                feature_engineering=feature_pipeline,
                use_pca=True,
                pca_components=PCA_COMPONENTS,
                estimator=estimator,
                n_clusters=k,
                random_state=RANDOM_STATE,
            )
            pipe.fit(X)

            transformed = pipe.named_steps["feature_engineering"].transform(X)
            Z = pipe.named_steps["preprocess"].transform(transformed)
            if "pca" in pipe.named_steps:
                Z = pipe.named_steps["pca"].transform(Z)
            if estimator == "kmeans":
                labels = pipe.named_steps["cluster"].labels_
            else:
                labels = pipe.named_steps["cluster"].predict(Z)

            scores = evaluate_embeddings(Z, labels)
            results.append({"estimator": estimator, "k": k, **scores})
            logger.info(
                "[%s] k=%s -> silhouette=%.4f, CH=%.1f, DBI=%.4f",
                estimator,
                k,
                scores["silhouette"],
                scores["ch"],
                scores["dbi"],
            )

            if estimator == "kmeans" and k == 3:
                joblib.dump(pipe, best_model_path)
                logger.info("Candidate model stored at %s", best_model_path)

    pd.DataFrame(results).to_csv(metrics_path, index=False)
    logger.info("model_compare_metrics.csv -> %s", metrics_path)


if __name__ == "__main__":
    main()
