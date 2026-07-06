"""
Shared ML training utilities for Maayan leak detection models.
"""

import os
from typing import Dict, List, Optional, Tuple, Any

import joblib
import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

NODE_FEATURES = [
    "J1", "J2", "J3", "J4", "J5", "J6",
    "J7", "J8", "J9", "J10", "J11", "J12",
]

SCENARIO_TO_CLASS = {"normal": 0, "small": 1, "medium": 2, "burst": 3}

MODEL_DIR = "data/models"
ISO_MODEL_FILE = "isolation_forest.joblib"
RF_LOCATION_FILE = "rf_location.joblib"
GB_SEVERITY_FILE = "gb_severity.joblib"
SCALER_FILE = "scaler.joblib"
METRICS_FILE = "training_metrics.json"


def dataframe_to_arrays(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert a training dataframe to (X, y_location, y_severity)."""
    X = df[NODE_FEATURES].to_numpy(dtype=float)
    y_sev = df["label"].to_numpy(dtype=int)

    if "leak_node_idx" in df.columns:
        y_loc = df["leak_node_idx"].to_numpy(dtype=int)
    else:
        y_loc = np.array([
            NODE_FEATURES.index(str(row)) if str(row) in NODE_FEATURES else -1
            for row in df.get("leak_node", ["none"] * len(df))
        ])

    return X, y_loc, y_sev


def train_models(
    df: pd.DataFrame,
    random_state: int = 42,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Train all leak-detection models from a dataframe.
    Returns (models_dict, metrics_dict).
    """
    if len(df) < 40:
        raise ValueError(f"Need at least 40 samples to train, got {len(df)}")

    X, y_loc, y_sev = dataframe_to_arrays(df)

    try:
        X_train, X_test, y_loc_train, y_loc_test, y_sev_train, y_sev_test = train_test_split(
            X, y_loc, y_sev, test_size=0.2, random_state=random_state, stratify=y_sev
        )
    except ValueError:
        X_train, X_test, y_loc_train, y_loc_test, y_sev_train, y_sev_test = train_test_split(
            X, y_loc, y_sev, test_size=0.2, random_state=random_state
        )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    iso_forest = IsolationForest(
        n_estimators=100,
        contamination=min(0.45, max(0.15, (y_sev > 0).mean() + 0.1)),
        random_state=random_state,
    )
    iso_forest.fit(X_train_scaled)

    rf_locator = None
    leak_mask = y_loc_train >= 0
    if leak_mask.sum() > 10:
        rf_locator = RandomForestRegressor(n_estimators=100, random_state=random_state)
        rf_locator.fit(X_train_scaled[leak_mask], y_loc_train[leak_mask])

    gb_severity = GradientBoostingClassifier(n_estimators=100, random_state=random_state)
    gb_severity.fit(X_train_scaled, y_sev_train)

    # Evaluate on holdout
    sev_pred = gb_severity.predict(X_test_scaled)
    severity_accuracy = float(accuracy_score(y_sev_test, sev_pred))

    localization_mae = None
    if rf_locator is not None:
        leak_test = y_loc_test >= 0
        if leak_test.sum() > 0:
            loc_pred = rf_locator.predict(X_test_scaled[leak_test])
            localization_mae = float(mean_absolute_error(y_loc_test[leak_test], loc_pred))

    anomaly_rate = float((iso_forest.predict(X_test_scaled) == -1).mean())

    models = {
        "scaler": scaler,
        "iso_forest": iso_forest,
        "rf_locator": rf_locator,
        "gb_severity": gb_severity,
    }

    metrics = {
        "samples": int(len(df)),
        "severity_accuracy": round(severity_accuracy, 4),
        "localization_mae": round(localization_mae, 4) if localization_mae is not None else None,
        "anomaly_rate_holdout": round(anomaly_rate, 4),
        "scenario_distribution": df["scenario"].value_counts().to_dict() if "scenario" in df.columns else {},
    }

    return models, metrics


def save_models(models: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    """Persist trained models and metrics to disk."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(models["iso_forest"], os.path.join(MODEL_DIR, ISO_MODEL_FILE))
    joblib.dump(models["scaler"], os.path.join(MODEL_DIR, SCALER_FILE))
    if models.get("rf_locator") is not None:
        joblib.dump(models["rf_locator"], os.path.join(MODEL_DIR, RF_LOCATION_FILE))
    if models.get("gb_severity") is not None:
        joblib.dump(models["gb_severity"], os.path.join(MODEL_DIR, GB_SEVERITY_FILE))

    import json
    from datetime import datetime

    history_path = os.path.join(MODEL_DIR, METRICS_FILE)
    history: List[Dict] = []
    if os.path.exists(history_path):
        try:
            with open(history_path) as f:
                history = json.load(f).get("history", [])
        except Exception:
            history = []

    entry = {**metrics, "trained_at": datetime.utcnow().isoformat()}
    history.append(entry)
    history = history[-50:]

    with open(history_path, "w") as f:
        json.dump({"latest": entry, "history": history}, f, indent=2)

    logger.info(
        f"Models saved — samples={metrics['samples']}, "
        f"severity_acc={metrics['severity_accuracy']}, "
        f"loc_mae={metrics.get('localization_mae')}"
    )


def load_metrics() -> Dict[str, Any]:
    """Load latest training metrics."""
    import json
    path = os.path.join(MODEL_DIR, METRICS_FILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}
