"""
AI illicit-probability classifier - Technical Defense Document, section 2.

Scope note (also in docs/BUILT_VS_ROADMAP.md): this live per-wallet
classifier is trained on a synthetic dataset shaped like the real
threat model, not the actual Elliptic / Elliptic++ dataset (203,769
real labelled Bitcoin transactions) - that benchmark exists separately
in train_elliptic_benchmark.py, using the real published dataset (see
its own docstring for exactly why the two aren't interchangeable).
What IS real here:

  - a genuine RandomForestClassifier (scikit-learn), actually trained,
    actually serialized, actually loaded and run at inference time - nothing about the inference path is mocked.
  - the feature schema mirrors the reference literature's design used
    on this exact task: local transaction/wallet features + neighbourhood
    -aggregated features (in/out-degree, fee ratio, timing regularity,
    peel-chain involvement, mixer proximity).
  - training data is synthetically generated to match documented
    laundering / licit-activity patterns (not invented target metrics - see docs/BUILT_VS_ROADMAP.md for exact numbers achieved on this
    synthetic set vs the published Elliptic targets in the Technical
    Defense Document).

Swap-in path to the real dataset: replace `_synthetic_training_data()`
with an Elliptic++ CSV loader; the feature vector, model class and
`/api/trace` call site are already correct and do not change.
"""
import os
import random
import pickle
import json

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, precision_score, recall_score

MODEL_PATH = os.path.join(os.path.dirname(__file__), "illicit_classifier.pkl")

FEATURE_NAMES = [
    "in_degree", "out_degree", "avg_fee_ratio", "timing_regularity",
    "peel_chain_score", "mixer_proximity", "value_zscore", "unique_counterparties",
]


def _synthetic_training_data(n=6000, seed=7):
    """
    Builds a labelled synthetic dataset shaped like the Elliptic feature
    family. Illicit examples are generated with the signatures documented
    in the fraud-typology literature this project cites (peel chains,
    mixer proximity, high fan-out, irregular timing); licit examples look
    like ordinary wallets and merchant/exchange activity.
    """
    rng = np.random.default_rng(seed)
    n_illicit = n // 2
    n_licit = n - n_illicit

    illicit = np.column_stack([
        rng.poisson(1.2, n_illicit),                       # in_degree - low, funds pushed through fast
        rng.poisson(6.0, n_illicit),                        # out_degree - high fan-out (peel chain)
        rng.beta(2, 6, n_illicit),                          # avg_fee_ratio - fee-shaving common
        rng.beta(1.5, 4, n_illicit),                         # timing_regularity - irregular
        rng.beta(5, 2, n_illicit),                          # peel_chain_score - high
        rng.beta(3, 3, n_illicit),                          # mixer_proximity - elevated
        rng.normal(1.4, 1.1, n_illicit),                    # value_zscore
        rng.poisson(3.0, n_illicit),                        # unique_counterparties - low-moderate
    ])
    licit = np.column_stack([
        rng.poisson(4.0, n_licit),                          # in_degree - normal wallet activity
        rng.poisson(3.0, n_licit),                          # out_degree
        rng.beta(2, 3, n_licit),                            # avg_fee_ratio - market-rate fees
        rng.beta(4, 1.5, n_licit),                           # timing_regularity - can be regular (payroll etc.) or not
        rng.beta(1.5, 6, n_licit),                          # peel_chain_score - low
        rng.beta(1, 8, n_licit),                            # mixer_proximity - near zero
        rng.normal(0.0, 1.0, n_licit),                      # value_zscore
        rng.poisson(8.0, n_licit),                          # unique_counterparties - exchanges/merchants see many
    ])

    X = np.vstack([illicit, licit])
    y = np.concatenate([np.ones(n_illicit), np.zeros(n_licit)])
    idx = rng.permutation(len(X))
    return X[idx], y[idx]


def train_and_save():
    X, y = _synthetic_training_data()
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    clf = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=5,
        class_weight="balanced_subsample", random_state=7,
    )
    clf.fit(X_train, y_train)

    proba = clf.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)
    metrics = {
        "auroc": round(float(roc_auc_score(y_test, proba)), 4),
        "precision": round(float(precision_score(y_test, preds)), 4),
        "recall": round(float(recall_score(y_test, preds)), 4),
        "trained_on": "synthetic Elliptic-schema dataset (offline build - see module docstring)",
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": clf, "feature_names": FEATURE_NAMES, "metrics": metrics}, f)
    return metrics


_cache = None


def _load():
    global _cache
    if _cache is None:
        if not os.path.exists(MODEL_PATH):
            train_and_save()
        with open(MODEL_PATH, "rb") as f:
            _cache = pickle.load(f)
    return _cache


def get_metrics():
    return _load()["metrics"]


ELLIPTIC_BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), "elliptic_benchmark_metrics.json")


def get_elliptic_benchmark():
    """
    The REAL Elliptic Bitcoin dataset benchmark - a separate, one-time
    offline run (engine/train_elliptic_benchmark.py) of this same model
    architecture against real labelled data, saved to
    elliptic_benchmark_metrics.json. Deliberately NOT the same thing as
    get_metrics() above, which reports the live, currently-loaded model's
    self-metrics on its synthetic training set - conflating the two would
    misrepresent which numbers came from real vs. synthetic data. Returns
    None if the benchmark file isn't present (it's committed to the repo,
    but a fresh clone without it should degrade gracefully rather than 500).
    """
    if not os.path.exists(ELLIPTIC_BENCHMARK_PATH):
        return None
    with open(ELLIPTIC_BENCHMARK_PATH, "r") as f:
        return json.load(f)


def wallet_features_from_tx(address, transactions):
    """Derive the engineered feature vector for one wallet from its local tx neighbourhood."""
    in_deg = sum(1 for t in transactions for o in t["outputs"] if o["address"] == address)
    out_deg = sum(1 for t in transactions if address in t["inputs"])
    fees = [t["fee"] for t in transactions if address in t["inputs"]]
    avg_fee_ratio = (sum(fees) / len(fees)) if fees else 0.0

    hops = sorted({t["hop"] for t in transactions if address in t["inputs"] or any(o["address"] == address for o in t["outputs"])})
    timing_regularity = 0.7 if len(hops) <= 2 else 0.4

    peel_targets = sum(1 for t in transactions if address in t["inputs"] and len(t["outputs"]) == 1 and t["outputs"][0]["value"] < 0.5)
    peel_chain_score = min(1.0, peel_targets / 8.0)

    mixer_hit = any(
        address in t["inputs"] and any("Mixer" in o["address"] for o in t["outputs"])
        for t in transactions
    )
    mixer_proximity = 1.0 if mixer_hit else 0.05

    values = [o["value"] for t in transactions for o in t["outputs"]]
    value_zscore = 0.0
    if values:
        mean_v = sum(values) / len(values)
        value_zscore = (max(values) - mean_v) / (mean_v + 1e-6)

    counterparties = set()
    for t in transactions:
        if address in t["inputs"]:
            counterparties.update(o["address"] for o in t["outputs"])
        for o in t["outputs"]:
            if o["address"] == address:
                counterparties.update(t["inputs"])

    return [
        min(in_deg, 20), min(out_deg, 20), min(avg_fee_ratio, 5.0),
        timing_regularity, peel_chain_score, mixer_proximity,
        max(-3.0, min(3.0, value_zscore)), min(len(counterparties), 50),
    ]


def predict_illicit_probability(feature_vector):
    bundle = _load()
    clf = bundle["model"]
    x = np.array(feature_vector, dtype=float).reshape(1, -1)
    return float(clf.predict_proba(x)[0, 1])


# Human-readable framing for each engineered feature, keyed by direction.
# Used only for the explanation UI - never changes the actual prediction.
_FEATURE_STORY = {
    "in_degree": ("Low inbound sender count", "Broad inbound sender pool"),
    "out_degree": ("High fan-out (peel-chain-like)", "Ordinary outflow count"),
    "avg_fee_ratio": ("Fee-shaving pattern in outgoing fees", "Market-rate transaction fees"),
    "timing_regularity": ("Irregular transaction timing", "Regular sweep-out timing"),
    "peel_chain_score": ("Peel chain detected", "No peel-chain structure"),
    "mixer_proximity": ("Mixer proximity elevated", "No mixer"),
    "value_zscore": ("Anomalous output value spread", "Typical output value spread"),
    "unique_counterparties": ("Narrow counterparty set", "Exchange fingerprint matched"),
}


def explain_prediction(feature_vector, top_n=5):
    """
    SHAP-style local explanation without a `shap` dependency (not
    installable in this offline build - see module docstring). Uses the
    RandomForest's global `feature_importances_` combined with how far
    this instance's feature value sits from the training set's licit-
    class mean, signed by direction, as a first-order local attribution.
    This is a documented approximation, not exact Shapley values - the
    swap-in path to real SHAP (`shap.TreeExplainer(clf)`) is a single
    call once the `shap` package can be installed in the deploy target.

    Returns a list of {feature, direction, magnitude, reason} sorted by
    |magnitude| descending, e.g.:
        {"feature": "peel_chain_score", "direction": "+", "magnitude": 0.41,
         "reason": "Peel chain detected"}
    """
    bundle = _load()
    clf = bundle["model"]
    importances = clf.feature_importances_
    x = np.array(feature_vector, dtype=float)

    # Reconstruct an approximate licit-class mean/std from the same
    # synthetic generator used to train (cheap, deterministic - no need
    # to store the whole training set on disk for this).
    licit_X, licit_y = _synthetic_training_data()
    licit_only = licit_X[licit_y == 0]
    means = licit_only.mean(axis=0)
    stds = licit_only.std(axis=0) + 1e-6

    contributions = []
    for i, name in enumerate(FEATURE_NAMES):
        z = (x[i] - means[i]) / stds[i]
        signed_weight = importances[i] * z
        raises_risk = signed_weight > 0
        contributions.append({
            "feature": name,
            "direction": "+" if raises_risk else "-",
            "magnitude": round(float(abs(signed_weight)), 4),
            "reason": _FEATURE_STORY.get(name, (name, name))[0 if raises_risk else 1],
        })
    contributions.sort(key=lambda c: c["magnitude"], reverse=True)
    return contributions[:top_n]


if __name__ == "__main__":
    m = train_and_save()
    print("Trained. Metrics:", m)
