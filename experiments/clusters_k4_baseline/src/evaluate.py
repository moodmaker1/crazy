# src/evaluate.py
from __future__ import annotations

from sklearn.metrics import silhouette_score


def silhouette_on_val(model, X_val):
    """검증 세트에서 실루엣 점수를 계산한다."""
    pre = model.named_steps.get("preprocess")
    clu = model.named_steps.get("cluster")
    if pre is None or clu is None:
        raise ValueError("Pipeline must have steps named 'preprocess' and 'cluster'.")

    if "feature_engineering" in model.named_steps:
        X_val_transformed = model.named_steps["feature_engineering"].transform(X_val)
    else:
        X_val_transformed = X_val

    Z_val = pre.transform(X_val_transformed)
    labels = clu.predict(Z_val)
    unique_labels = set(labels)
    if len(unique_labels) < 2:
        print('[EVAL] Silhouette Score: nan (only one cluster present)')
        return float('nan')
    score = silhouette_score(Z_val, labels)
    print(f"[EVAL] Silhouette Score: {score:.4f}")
    return score
