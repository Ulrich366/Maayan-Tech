"""
Leak Detection Engine for Maayan.

Combines statistical pressure analysis with machine learning models
(Isolation Forest + Random Forest) to detect, locate, and quantify
water network leaks in real time.

ML models continuously improve via backend.ai.continuous_learner as new
labeled simulation observations are collected.
"""

import os
import threading
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

import joblib
import numpy as np
from loguru import logger
from sklearn.ensemble import IsolationForest, RandomForestRegressor, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

from backend.ai.model_trainer import (
    NODE_FEATURES,
    MODEL_DIR,
    ISO_MODEL_FILE,
    RF_LOCATION_FILE,
    GB_SEVERITY_FILE,
    SCALER_FILE,
    train_models,
    save_models,
    load_metrics,
)
from backend.ai.learning_store import LearningStore
from backend.ai.continuous_learner import ContinuousLearner


@dataclass
class LeakReport:
    """Structured leak detection result."""
    detected: bool
    location: str
    node_id: Optional[str]
    pipe_id: Optional[str]
    probability: float
    severity: str
    pressure_drop: float
    estimated_flow_loss: float
    affected_nodes: List[str]
    confidence: float
    detection_method: str
    timestamp: str
    alert_level: str


class StatisticalDetector:
    """Fast statistical leak detector using z-score and threshold comparison."""

    THRESHOLDS = {
        "none":   0.015,
        "low":    0.020,
        "medium": 0.050,
        "high":   0.150,
        "burst":  0.250,
    }

    def __init__(self):
        self.pressure_history: Dict[str, List[float]] = {}
        self.window_size = 30

    def update(self, node_id: str, pressure: float):
        if node_id not in self.pressure_history:
            self.pressure_history[node_id] = []
        hist = self.pressure_history[node_id]
        hist.append(pressure)
        if len(hist) > self.window_size * 3:
            self.pressure_history[node_id] = hist[-self.window_size * 3:]

    def detect(self, nodes: List[Dict]) -> Dict[str, Any]:
        anomalies = []
        max_drop = 0.0
        worst_node = None

        for node in nodes:
            node_id = node["id"]
            pressure = node["pressure"]
            baseline = node["pressure_baseline"]
            drop = node["pressure_drop"]

            self.update(node_id, pressure)

            if drop > self.THRESHOLDS["none"]:
                anomalies.append({
                    "node_id": node_id,
                    "pressure_drop": drop,
                    "pressure": pressure,
                    "baseline": baseline,
                })
                if drop > max_drop:
                    max_drop = drop
                    worst_node = node_id

        if not anomalies:
            return {"detected": False, "drop": 0.0, "node": None, "anomalies": []}

        if worst_node and worst_node in self.pressure_history:
            hist = self.pressure_history[worst_node]
            if len(hist) >= 10:
                mean = np.mean(hist[:-1])
                std = max(np.std(hist[:-1]), 0.001)
                z = abs(hist[-1] - mean) / std
                if z < 2.0:
                    return {"detected": False, "drop": max_drop, "node": worst_node, "anomalies": anomalies}

        return {
            "detected": True,
            "drop": max_drop,
            "node": worst_node,
            "anomalies": anomalies,
        }

    def classify_severity(self, pressure_drop: float) -> str:
        if pressure_drop >= self.THRESHOLDS["burst"]:
            return "burst"
        elif pressure_drop >= self.THRESHOLDS["high"]:
            return "high"
        elif pressure_drop >= self.THRESHOLDS["medium"]:
            return "medium"
        elif pressure_drop >= self.THRESHOLDS["low"]:
            return "low"
        return "none"


class MLLeakDetector:
    """Machine learning leak detector with hot-reload support."""

    FEATURES = NODE_FEATURES

    def __init__(self):
        self.iso_forest: Optional[IsolationForest] = None
        self.rf_locator: Optional[RandomForestRegressor] = None
        self.gb_severity: Optional[GradientBoostingClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.is_trained = False
        self._model_lock = threading.Lock()
        self._load_or_train()

    def _load_or_train(self):
        os.makedirs(MODEL_DIR, exist_ok=True)
        iso_path = os.path.join(MODEL_DIR, ISO_MODEL_FILE)
        scaler_path = os.path.join(MODEL_DIR, SCALER_FILE)

        if os.path.exists(iso_path) and os.path.exists(scaler_path):
            try:
                with self._model_lock:
                    self.iso_forest = joblib.load(iso_path)
                    self.scaler = joblib.load(scaler_path)
                    rf_path = os.path.join(MODEL_DIR, RF_LOCATION_FILE)
                    if os.path.exists(rf_path):
                        self.rf_locator = joblib.load(rf_path)
                    gb_path = os.path.join(MODEL_DIR, GB_SEVERITY_FILE)
                    if os.path.exists(gb_path):
                        self.gb_severity = joblib.load(gb_path)
                    self.is_trained = True
                logger.info("ML models loaded from disk")
                return
            except Exception as e:
                logger.warning(f"Model load failed: {e}")

        logger.info("Training ML models from EPANET-generated data...")
        self._train_initial()

    def _generate_training_data(self, n_samples: int = 600):
        from backend.epanet.simulator import EpanetSimulator

        sim = EpanetSimulator()
        use_real = sim.engine == "epanet"
        node_order = list(sim.network_def.NODES.keys())

        logger.info(
            f"Generating {n_samples} training samples using "
            f"{'REAL EPANET 2.2 solves' if use_real else 'calibrated synthetic approximation'}..."
        )

        leak_nodes = ["J7", "J3", "J5", "J6", "J8"] if use_real else ["J7"]
        severity_bins = [
            ("normal", 0.0, 0.0, 0),
            ("small",  0.5, 2.5, 1),
            ("medium", 2.5, 6.5, 2),
            ("burst",  8.0, 15.0, 3),
        ]
        bin_weights = [0.35, 0.20, 0.25, 0.20]

        X, y_loc, y_sev = [], [], []
        for i in range(n_samples):
            bin_idx = np.random.choice(len(severity_bins), p=bin_weights)
            label, lo, hi, sev_class = severity_bins[bin_idx]

            if label == "normal":
                leak_node, leak_demand = None, 0.0
            else:
                leak_node = str(np.random.choice(leak_nodes))
                leak_demand = float(np.random.uniform(lo, hi))

            if use_real:
                solved = sim._solve(leak_node, leak_demand)
                pressures = np.array([solved["pressure_bar"][nid] for nid in node_order])
            else:
                drops = sim._propagate_pressure_drop(leak_node, leak_demand)
                pressures = np.array([
                    sim.baseline_pressures[nid] - drops.get(nid, 0.0) + np.random.normal(0, 0.005)
                    for nid in node_order
                ])

            X.append(pressures)
            y_loc.append(node_order.index(leak_node) if leak_node else -1)
            y_sev.append(sev_class)

            if use_real and (i + 1) % 100 == 0:
                logger.info(f"  ...{i + 1}/{n_samples} real EPANET solves complete")

        return np.array(X), np.array(y_loc), np.array(y_sev)

    def _train_initial(self):
        try:
            X, y_loc, y_sev = self._generate_training_data(600)
            import pandas as pd
            df = pd.DataFrame(X, columns=NODE_FEATURES)
            df["leak_node_idx"] = y_loc
            df["label"] = y_sev
            df["leak_node"] = [
                NODE_FEATURES[i] if i >= 0 else "none" for i in y_loc
            ]
            df["scenario"] = [
                {0: "normal", 1: "small", 2: "medium", 3: "burst"}.get(s, "normal")
                for s in y_sev
            ]

            store = LearningStore()
            os.makedirs("data/training", exist_ok=True)
            df.to_csv("data/training/training_data_latest.csv", index=False)

            models, metrics = train_models(df)
            save_models(models, metrics)
            self.hot_reload(models)
            logger.info("Initial ML models trained and saved successfully")
        except Exception as e:
            logger.error(f"ML training failed: {e}")

    def hot_reload(self, models: Dict[str, Any]) -> None:
        """Swap in freshly trained models without restarting the server."""
        with self._model_lock:
            self.scaler = models["scaler"]
            self.iso_forest = models["iso_forest"]
            self.rf_locator = models.get("rf_locator")
            self.gb_severity = models["gb_severity"]
            self.is_trained = True
        logger.info("ML models hot-reloaded")

    def predict(self, node_pressures: Dict[str, float]) -> Dict[str, Any]:
        with self._model_lock:
            if not self.is_trained or self.scaler is None:
                return {"anomaly": False, "severity_class": 0, "confidence": 0.0}

            feature_vector = np.array([
                node_pressures.get(nid, 3.0) for nid in self.FEATURES
            ]).reshape(1, -1)

            try:
                X_scaled = self.scaler.transform(feature_vector)
                iso_pred = self.iso_forest.predict(X_scaled)[0]
                anomaly_score = self.iso_forest.score_samples(X_scaled)[0]
                is_anomaly = iso_pred == -1

                severity_class = 0
                severity_proba = [1.0, 0.0, 0.0, 0.0]
                if self.gb_severity is not None:
                    severity_class = int(self.gb_severity.predict(X_scaled)[0])
                    severity_proba = self.gb_severity.predict_proba(X_scaled)[0].tolist()

                confidence = min(100, max(0, (abs(anomaly_score) + 0.5) * 60))

                return {
                    "anomaly": is_anomaly,
                    "anomaly_score": float(anomaly_score),
                    "severity_class": severity_class,
                    "severity_proba": severity_proba,
                    "confidence": round(confidence, 1),
                }
            except Exception as e:
                logger.error(f"ML prediction error: {e}")
                return {"anomaly": False, "severity_class": 0, "confidence": 0.0}


class LeakDetectionEngine:
    """Main orchestrator combining statistical + ML detection."""

    SEVERITY_LABELS = ["none", "low", "medium", "high", "burst"]
    ALERT_COLORS = {
        "none": "green", "low": "yellow", "medium": "orange",
        "high": "red", "burst": "red",
    }
    NODE_TO_PIPE = {
        "J7": "P7", "J6": "P6", "J8": "P8", "J5": "P5", "J4": "P4",
        "J3": "P3", "J2": "P2", "J1": "P1",
    }

    def __init__(self):
        self.statistical = StatisticalDetector()
        self.ml = MLLeakDetector()
        self.learner = ContinuousLearner(self.ml)
        self.last_report: Optional[LeakReport] = None

    def analyze(self, snapshot_dict: Dict) -> LeakReport:
        nodes = snapshot_dict.get("nodes", [])
        scenario = snapshot_dict.get("scenario", "normal")

        stat_result = self.statistical.detect(nodes)
        pressures = {n["id"]: n["pressure"] for n in nodes}
        ml_result = self.ml.predict(pressures)

        zone_names = {n["id"]: n.get("name", n["id"]) for n in nodes}
        report = self._combine(stat_result, ml_result, nodes, scenario, zone_names)
        self.last_report = report

        # Continuous learning: record labeled sample + maybe retrain
        self.learner.observe(snapshot_dict, self.to_dict(report))

        return report

    def _combine(
        self,
        stat: Dict,
        ml: Dict,
        nodes: List[Dict],
        scenario: str,
        zone_names: Optional[Dict[str, str]] = None,
    ) -> LeakReport:
        detected = stat.get("detected", False) or ml.get("anomaly", False)
        max_drop = stat.get("drop", 0.0)
        worst_node = stat.get("node")
        anomalies = stat.get("anomalies", [])

        stat_severity = self.statistical.classify_severity(max_drop)
        ml_severity_idx = ml.get("severity_class", 0)
        ml_severity = self.SEVERITY_LABELS[min(ml_severity_idx, 4)]

        severity_priority = {"none": 0, "low": 1, "medium": 2, "high": 3, "burst": 4}
        if severity_priority.get(ml_severity, 0) > severity_priority.get(stat_severity, 0):
            severity = ml_severity
        else:
            severity = stat_severity

        if not detected:
            severity = "none"

        REAL_BURST_REFERENCE_BAR = 0.32
        stat_prob = min(100, (max_drop / REAL_BURST_REFERENCE_BAR) * 100) if detected else 0
        ml_conf = ml.get("confidence", 0.0) if ml.get("anomaly") else 0
        probability = round((stat_prob * 0.6 + ml_conf * 0.4), 1) if detected else 0

        zone_names = zone_names or {}
        location = "No anomaly detected"
        pipe_id = None
        if worst_node:
            zone = zone_names.get(worst_node, worst_node)
            pipe_id = self.NODE_TO_PIPE.get(worst_node)
            if pipe_id:
                for n in nodes:
                    if n["id"] != worst_node and n.get("pressure_drop", 0) > self.statistical.THRESHOLDS["low"]:
                        adj_zone = zone_names.get(n["id"], n["id"])
                        location = f"Between {zone} and {adj_zone} ({pipe_id})"
                        break
                else:
                    location = f"Near {zone} zone ({worst_node})"
            else:
                location = f"Zone {zone} ({worst_node})"

        flow_loss = round(max(0.0, 34.4 * max_drop + 1.0), 2) if detected else 0.0
        affected = [
            a["node_id"] for a in anomalies
            if a.get("pressure_drop", 0) > self.statistical.THRESHOLDS["low"]
        ]

        return LeakReport(
            detected=detected,
            location=location,
            node_id=worst_node,
            pipe_id=pipe_id,
            probability=probability,
            severity=severity,
            pressure_drop=round(max_drop, 3),
            estimated_flow_loss=flow_loss,
            affected_nodes=affected,
            confidence=round(ml.get("confidence", 0.0), 1),
            detection_method="combined" if detected else "none",
            timestamp=datetime.utcnow().isoformat(),
            alert_level=self.ALERT_COLORS.get(severity, "green"),
        )

    def to_dict(self, report: LeakReport) -> Dict:
        d = asdict(report)
        d["detected"] = bool(d["detected"])
        d["probability"] = float(d["probability"])
        d["pressure_drop"] = float(d["pressure_drop"])
        d["estimated_flow_loss"] = float(d["estimated_flow_loss"])
        d["confidence"] = float(d["confidence"])
        return d

    def learning_status(self) -> Dict[str, Any]:
        return self.learner.get_status()
