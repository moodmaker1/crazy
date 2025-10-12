from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    DEFAULT_CLUSTER_COUNT,
    DEFAULT_RANDOM_STATE,
    DEFAULT_TEST_SIZE,
    DEFAULT_VAL_SIZE,
    MODEL_FILENAME,
    create_run_directory,
    get_processed_dataset_path,
    setup_run_logger,
)
from src.feature_engineering import build_feature_engineering_pipeline
from src.preprocess import build_preprocessor, drop_unnecessary, load_dataframe
from src.split_data import split_dataset
from src.train_model import train_kmeans
from src.evaluate import silhouette_on_val


def export_clusters(
    model,
    X_train: pd.DataFrame,
    X_val: pd.DataFrame,
    X_test: pd.DataFrame,
    ids=None,
    out_path: Path | str | None = None,
) -> None:
    if out_path is None:
        raise ValueError("out_path must be provided for export_clusters")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pre = model.named_steps["preprocess"]
    clu = model.named_steps["cluster"]
    feature_step = model.named_steps.get("feature_engineering")

    X_all = pd.concat([X_train, X_val, X_test], axis=0).reset_index(drop=True)
    if feature_step is not None:
        Z_all = feature_step.transform(X_all)
    else:
        Z_all = X_all
    Z_all = pre.transform(Z_all)
    labels = clu.predict(Z_all)

    out = X_all.copy()
    if ids is not None:
        id_all = pd.concat(ids, axis=0).reset_index(drop=True)
        out.insert(0, "ENCODED_MCT", id_all)
    out["cluster"] = labels
    out.to_csv(out_path, index=False, encoding="utf-8-sig")


def main() -> None:
    data_path = get_processed_dataset_path()
    run_dir = create_run_directory(prefix="clusters")
    logger = setup_run_logger(run_dir, name="cafe_clustering.train")
    model_path = run_dir / MODEL_FILENAME
    cluster_out_path = run_dir / "cluster_result.csv"

    logger.info("Using dataset: %s", data_path)
    logger.info("Run directory: %s", run_dir)
    logger.info("Clusters: %s | random_state=%s", DEFAULT_CLUSTER_COUNT, DEFAULT_RANDOM_STATE)

    df = load_dataframe(data_path)
    if df.empty:
        raise ValueError(f"Empty dataframe: {data_path}")

    id_series = df["ENCODED_MCT"] if "ENCODED_MCT" in df.columns else None

    df = drop_unnecessary(df)
    X = df.copy()

    X_train, X_val, X_test, _, _, _ = split_dataset(
        X,
        y=None,
        test_size=DEFAULT_TEST_SIZE,
        val_size=DEFAULT_VAL_SIZE,
        random_state=DEFAULT_RANDOM_STATE,
    )

    id_partitions = None
    if id_series is not None:
        id_train = id_series.loc[X_train.index].reset_index(drop=True)
        id_val = id_series.loc[X_val.index].reset_index(drop=True)
        id_test = id_series.loc[X_test.index].reset_index(drop=True)
        id_partitions = (id_train, id_val, id_test)

    X_train = X_train.reset_index(drop=True)
    X_val = X_val.reset_index(drop=True)
    X_test = X_test.reset_index(drop=True)


    feature_pipeline = None
    preprocessor_input = X_train

    probe_candidate = build_feature_engineering_pipeline()
    probe_pipeline = probe_candidate[0] if isinstance(probe_candidate, tuple) else probe_candidate
    preprocessor_input = probe_pipeline.fit_transform(X_train)
    prune_step = probe_pipeline.named_steps.get("prune")
    dropped = getattr(prune_step, "columns_to_drop_", set())
    if dropped:
        logger.info("Feature pipeline will drop columns: %s", sorted(dropped))

    feature_candidate = build_feature_engineering_pipeline()
    feature_pipeline = feature_candidate[0] if isinstance(feature_candidate, tuple) else feature_candidate

    preprocessor, _, _ = build_preprocessor(preprocessor_input)
    model = train_kmeans(
        X_train,
        preprocessor,
        feature_engineering=feature_pipeline,
        use_pca=False,
        n_clusters=DEFAULT_CLUSTER_COUNT,
        model_path=model_path,
        random_state=DEFAULT_RANDOM_STATE,
    )
    logger.info("Model saved to %s", model_path)

    score = silhouette_on_val(model, X_val)
    logger.info("Silhouette score (val): %.4f", score)

    export_clusters(
        model,
        X_train,
        X_val,
        X_test,
        ids=id_partitions,
        out_path=cluster_out_path,
    )
    logger.info("Cluster assignments saved to %s", cluster_out_path)


if __name__ == "__main__":
    main()
