# src/train_model.py
from __future__ import annotations

from pathlib import Path

import joblib

from src.model_selection import build_pipeline


def train_kmeans(
    X_train,
    preprocessor,
    feature_engineering=None,
    use_pca: bool = False,
    pca_components: int = 20,
    n_clusters: int = 5,
    model_path: str | Path | None = None,
    random_state: int = 42,
):
    """Train a K-Means pipeline assembled via `build_pipeline`."""
    if model_path is None:
        raise ValueError("model_path must be provided so the trained pipeline can be saved.")

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    pipeline = build_pipeline(
        preprocessor=preprocessor,
        feature_engineering=feature_engineering,
        use_pca=use_pca,
        pca_components=pca_components,
        estimator="kmeans",
        n_clusters=n_clusters,
        random_state=random_state,
    )

    pipeline.fit(X_train)
    joblib.dump(pipeline, model_path)
    return pipeline
