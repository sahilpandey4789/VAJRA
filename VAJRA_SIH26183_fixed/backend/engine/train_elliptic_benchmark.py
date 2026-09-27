"""
Real Elliptic dataset benchmark - trains and evaluates a RandomForest
directly on the genuine, published Elliptic Bitcoin dataset (166
anonymized features per transaction, 203,769 transactions, 4,545
labelled illicit / 42,019 labelled licit / rest unknown).

HONEST SCOPE NOTE (read this before treating this as "the live model"):

Elliptic's 166 features are anonymized/PCA-transformed by the original
authors for confidentiality reasons -- they were never disclosed as
named, interpretable features. VAJRA's live per-wallet classifier
(`ml_model.py`, used by /api/trace) instead uses 8 NAMED engineered
features (in_degree, out_degree, avg_fee_ratio, timing_regularity,
peel_chain_score, mixer_proximity, value_zscore, unique_counterparties)
computed live from each traced wallet's transaction neighbourhood via
`wallet_features_from_tx()`.

These two feature spaces are NOT interchangeable. A model trained on
Elliptic's 166 anonymized columns cannot be fed VAJRA's 8-feature live
vector, and vice versa -- the column semantics don't line up. So this
script produces a SEPARATE, real, independently-verifiable benchmark
model -- proof VAJRA's approach (RandomForest, Elliptic-style feature
family, standard temporal evaluation) achieves real, reportable
numbers on the actual published dataset -- while the live /api/trace
path keeps using the 8-feature model in ml_model.py unchanged.

Evaluation follows the same temporal split convention as the original
Elliptic paper (Weber et al.): train on early time steps, test on
later ones, rather than a random shuffle -- this is the harder, more
honest test (no leakage from the future into training).

Usage:
    Place elliptic_txs_features.csv, elliptic_txs_classes.csv, and
    elliptic_txs_edgelist.csv in backend/data/elliptic/, then:

        python3 engine/train_elliptic_benchmark.py

    Produces engine/elliptic_benchmark_classifier.pkl and prints +
    saves real metrics to engine/elliptic_benchmark_metrics.json.
"""
import json
import os
import time

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)
import pickle

DATA_DIR = os.environ.get(
    "VAJRA_ELLIPTIC_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data", "elliptic"),
)
MODEL_OUT = os.path.join(os.path.dirname(__file__), "elliptic_benchmark_classifier.pkl")
METRICS_OUT = os.path.join(os.path.dirname(__file__), "elliptic_benchmark_metrics.json")


def run():
    t0 = time.time()
    feat_path = os.path.join(DATA_DIR, "elliptic_txs_features.csv")
    classes_path = os.path.join(DATA_DIR, "elliptic_txs_classes.csv")
    if not (os.path.exists(feat_path) and os.path.exists(classes_path)):
        raise FileNotFoundError(
            f"Expected Elliptic CSVs in {DATA_DIR} -- "
            "download from Kaggle (elliptic-data-set) and place there first."
        )

    feat = pd.read_csv(feat_path, header=None)
    n_cols = feat.shape[1]
    feat.columns = ["txId", "time_step"] + [f"f_{i}" for i in range(1, n_cols - 1)]
    classes = pd.read_csv(classes_path)

    merged = feat.merge(classes, on="txId", how="left")
    labeled = merged[merged["class"] != "unknown"].copy()
    labeled["y"] = (labeled["class"] == "1").astype(int)  # 1=illicit, 2=licit->0

    # Paper-standard temporal split: train on early time steps, test on later.
    train = labeled[labeled["time_step"] <= 34]
    test = labeled[labeled["time_step"] > 34]

    feature_cols = [c for c in labeled.columns if c.startswith("f_") or c == "time_step"]
    X_train, y_train = train[feature_cols].values, train["y"].values
    X_test, y_test = test[feature_cols].values, test["y"].values

    clf = RandomForestClassifier(
        n_estimators=300, max_depth=None, min_samples_leaf=2,
        class_weight="balanced_subsample", random_state=7, n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    proba = clf.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, preds).ravel()

    metrics = {
        "trained_on": "REAL Elliptic Bitcoin dataset (Kaggle elliptic-data-set)",
        "split_method": "temporal (paper-standard): train time_steps 1-34, test time_steps 35-49",
        "n_total_tx": int(len(feat)),
        "n_labeled": int(len(labeled)),
        "n_illicit_total": int(labeled["y"].sum()),
        "n_licit_total": int((labeled["y"] == 0).sum()),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "auroc": round(float(roc_auc_score(y_test, proba)), 4),
        "precision": round(float(precision_score(y_test, preds)), 4),
        "recall": round(float(recall_score(y_test, preds)), 4),
        "f1": round(float(f1_score(y_test, preds)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "n_features": len(feature_cols),
        "feature_schema": (
            "Elliptic's own 165 anonymized local+aggregated features + time_step -- "
            "NOT the same schema as VAJRA's live 8-feature engineered vector (see module docstring)"
        ),
        "trained_seconds": round(time.time() - t0, 1),
    }

    with open(MODEL_OUT, "wb") as f:
        pickle.dump({"model": clf, "feature_columns": feature_cols, "metrics": metrics}, f)
    with open(METRICS_OUT, "w") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"\nSaved model -> {MODEL_OUT}")
    print(f"Saved metrics -> {METRICS_OUT}")
    return metrics


if __name__ == "__main__":
    run()
