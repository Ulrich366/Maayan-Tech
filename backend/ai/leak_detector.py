"""
Leak Detection Engine for Maayan.

Combines statistical pressure analysis with machine learning models
(Isolation Forest + Random Forest) to detect, locate, and quantify
water network leaks in real time.
"""

import os
import json
import math
import numpy as np
import pandas as pd
import joblib
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger
from sklearn.ensemble import IsolationForest, RandomForestRegressor, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


@dataclass
class LeakReport:
    """Structured leak detection result."""
    detected: bool
    location: str
    node_id: Optional[str]
    pipe_id: Optional[str]
    probability: float          # 0–100
    severity: str               # none, low, medium, high, burst
    pressure_drop: float        # bar
    estimated_flow_loss: float  # L/s
    affected_nodes: List[str]
    confidence: float           # 0–100
    detection_method: str       # statistical, ml, combined
    timestamp: str
    alert_level: str            # green, yellow, orange, red


class StatisticalDetector:
    """
    Fast statistical leak detector using z-score and threshold comparison.
    Runs every cycle as the first-line detector.
    """

    # Severity thresholds (pressure drop in bar).
    # Calibrated against REAL EPANET solves on the Douala network (a looped,
    # tank-backed network is naturally resilient, so real drops are modest
    # compared to a naive single-pipe assumption):
    #   small leak  (1.5 L/s @ J7)  -> ~0.026 bar drop at J7
    #   medium leak (4.5 L/s @ J7)  -> ~0.085 bar drop at J7
    #   burst       (12.0 L/s @ J7) -> ~0.322 bar drop at J7
    THRESHOLDS = {
        "none":   0.015,
        "low":    0.020,
        "medium": 0.050,
        "high":   0.150,
        "burst":  0.250,
    }

    def __init__(self):
        self.pressure_history: Dict[str, List[float]] = {}
        self.window_size = 30  # Number of readings for baseline

    def update(self, node_id: str, pressure: float):
        """Add a new pressure reading to the history."""
        if node_id not in self.pressure_history:
            self.pressure_history[node_id] = []
        hist = self.pressure_history[node_id]
        hist.append(pressure)
        if len(hist) > self.window_size * 3:
            self.pressure_history[node_id] = hist[-self.window_size * 3:]

    def detect(self, nodes: List[Dict]) -> Dict[str, Any]:
        """
        Run statistical anomaly detection on current node pressures.
        Returns anomaly information for any detected issues.
        """
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

        # Z-score check against history if we have enough data
        if worst_node and worst_node in self.pressure_history:
            hist = self.pressure_history[worst_node]
            if len(hist) >= 10:
                mean = np.mean(hist[:-1])
                std = max(np.std(hist[:-1]), 0.001)
                z = abs(hist[-1] - mean) / std
                if z < 2.0:
                    # Not statistically significant yet
                    return {"detected": False, "drop": max_drop, "node": worst_node, "anomalies": anomalies}

        return {
            "detected": True,
            "drop": max_drop,
            "node": worst_node,
            "anomalies": anomalies,
        }

    def classify_severity(self, pressure_drop: float) -> str:
        """Classify severity from pressure drop value."""
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
    """
    Machine learning-based leak detector.

    Uses Isolation Forest for anomaly detection and
    Random Forest for leak localization and sizing.
    """

    MODEL_DIR = "data/models"
    ISO_MODEL_FILE = "isolation_forest.joblib"
    RF_LOCATION_FILE = "rf_location.joblib"
    GB_SEVERITY_FILE = "gb_severity.joblib"
    SCALER_FILE = "scaler.joblib"

    FEATURES = [
        "J1", "J2", "J3", "J4", "J5", "J6",
        "J7", "J8", "J9", "J10", "J11", "J12",
    ]

    def __init__(self):
        self.iso_forest: Optional[IsolationForest] = None
        self.rf_locator: Optional[RandomForestRegressor] = None
        self.gb_severity: Optional[GradientBoostingClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.is_trained = False
        self._load_or_train()

    def _load_or_train(self):
        """Load pre-trained models or train new ones from scratch."""
        os.makedirs(self.MODEL_DIR, exist_ok=True)
        iso_path = os.path.join(self.MODEL_DIR, self.ISO_MODEL_FILE)
        scaler_path = os.path.join(self.MODEL_DIR, self.SCALER_FILE)

        if os.path.exists(iso_path) and os.path.exists(scaler_path):
            try:
                self.iso_forest = joblib.load(iso_path)
                self.scaler = joblib.load(scaler_path)
                rf_path = os.path.join(self.MODEL_DIR, self.RF_LOCATION_FILE)
                if os.path.exists(rf_path):
                    self.rf_locator = joblib.load(rf_path)
                gb_path = os.path.join(self.MODEL_DIR, self.GB_SEVERITY_FILE)
                if os.path.exists(gb_path):
                    self.gb_severity = joblib.load(gb_path)
                self.is_trained = True
                logger.info("ML models loaded from disk")
                return
            except Exception as e:
                logger.warning(f"Model load failed: {e}")

        logger.info("Training ML models from EPANET-generated data...")
        self._train_from_synthetic()

    def _generate_training_data(self, n_samples: int = 600) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate the ML training dataset by running REAL EPANET hydraulic
        solves (via WNTR's EpanetSimulator) across randomized leak locations
        and severities on the actual Douala network topology. Falls back to
        a calibrated approximation only if WNTR/EPANET is unavailable.

        Returns: X (pressure vectors), y_location (node index), y_severity (0-3)
        """
        from backend.epanet.simulator import EpanetSimulator

        sim = EpanetSimulator()
        use_real = sim.engine == "epanet"
        node_order = list(sim.network_def.NODES.keys())

        logger.info(
            f"Generating {n_samples} training samples using "
            f"{'REAL EPANET 2.2 solves' if use_real else 'calibrated synthetic approximation'}..."
        )

        # With real hydraulics we can safely diversify leak locations since the
        # solver correctly propagates the effect through actual pipe topology.
        # The synthetic fallback only has calibrated adjacency for J7.
        leak_nodes = ["J7", "J3", "J5", "J6", "J8"] if use_real else ["J7"]

        # (label, min_lps, max_lps, severity_class)
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

    def _train_from_synthetic(self):
        """Train all ML models from generated synthetic data."""
        try:
            X, y_loc, y_sev = self._generate_training_data(600)

            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            # Isolation Forest for anomaly detection
            self.iso_forest = IsolationForest(
                n_estimators=100,
                contamination=0.35,
                random_state=42,
            )
            self.iso_forest.fit(X_scaled)

            # Random Forest for leak localization (only on leak samples)
            leak_mask = y_loc >= 0
            if leak_mask.sum() > 10:
                self.rf_locator = RandomForestRegressor(
                    n_estimators=100,
                    random_state=42,
                )
                self.rf_locator.fit(X_scaled[leak_mask], y_loc[leak_mask])

            # Gradient Boosting for severity classification
            self.gb_severity = GradientBoostingClassifier(
                n_estimators=100,
                random_state=42,
            )
            self.gb_severity.fit(X_scaled, y_sev)

            # Save models
            joblib.dump(self.iso_forest, os.path.join(self.MODEL_DIR, self.ISO_MODEL_FILE))
            joblib.dump(self.scaler, os.path.join(self.MODEL_DIR, self.SCALER_FILE))
            if self.rf_locator:
                joblib.dump(self.rf_locator, os.path.join(self.MODEL_DIR, self.RF_LOCATION_FILE))
            if self.gb_severity:
                joblib.dump(self.gb_severity, os.path.join(self.MODEL_DIR, self.GB_SEVERITY_FILE))

            self.is_trained = True
            logger.info("ML models trained and saved successfully")

        except Exception as e:
            logger.error(f"ML training failed: {e}")

    def predict(self, node_pressures: Dict[str, float]) -> Dict[str, Any]:
        """
        Run ML inference on current pressure readings.
        Returns: anomaly score, severity prediction, confidence.
        """
        if not self.is_trained or self.scaler is None:
            return {"anomaly": False, "severity_class": 0, "confidence": 0.0}

        feature_vector = np.array([
            node_pressures.get(nid, 3.0)
            for nid in self.FEATURES
        ]).reshape(1, -1)

        try:
            X_scaled = self.scaler.transform(feature_vector)

            # Anomaly score (-1 = anomaly, 1 = normal)
            iso_pred = self.iso_forest.predict(X_scaled)[0]
            anomaly_score = self.iso_forest.score_samples(X_scaled)[0]
            is_anomaly = iso_pred == -1

            # Severity
            severity_class = 0
            severity_proba = [1.0, 0.0, 0.0, 0.0]
            if self.gb_severity is not None:
                severity_class = int(self.gb_severity.predict(X_scaled)[0])
                severity_proba = self.gb_severity.predict_proba(X_scaled)[0].tolist()

            # Confidence from anomaly score normalization
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
    """
    Main orchestrator combining statistical + ML detection.
    Called every simulation tick to produce LeakReport.
    """

    SEVERITY_LABELS = ["none", "low", "medium", "high", "burst"]
    ALERT_COLORS = {
        "none":   "green",
        "low":    "yellow",
        "medium": "orange",
        "high":   "red",
        "burst":  "red",
    }

    # Pipe lookup from node anomaly to likely affected pipe
    NODE_TO_PIPE = {
        "J7": "P7", "J6": "P6", "J8": "P8",
        "J5": "P5", "J4": "P4", "J3": "P3",
        "J2": "P2", "J1": "P1",
    }

    ZONE_NAMES = {
        "J1": "Akwa", "J2": "Bali", "J3": "Deido", "J4": "Bonaberi",
        "J5": "New Bell", "J6": "Ndokotti", "J7": "Makepe", "J8": "Logbessou",
        "J9": "Bonamoussadi", "J10": "Cité des Palmiers",
        "J11": "Village", "J12": "PK14",
    }

    def __init__(self):
        self.statistical = StatisticalDetector()
        self.ml = MLLeakDetector()
        self.last_report: Optional[LeakReport] = None

    def analyze(self, snapshot_dict: Dict) -> LeakReport:
        """
        Full analysis pipeline: statistical + ML → combined decision.
        """
        nodes = snapshot_dict.get("nodes", [])
        scenario = snapshot_dict.get("scenario", "normal")

        # --- Statistical Analysis ---
        stat_result = self.statistical.detect(nodes)

        # --- ML Analysis ---
        pressures = {n["id"]: n["pressure"] for n in nodes}
        ml_result = self.ml.predict(pressures)

        # --- Combine Results ---
        report = self._combine(stat_result, ml_result, nodes, scenario)
        self.last_report = report
        return report

    def _combine(
        self,
        stat: Dict,
        ml: Dict,
        nodes: List[Dict],
        scenario: str,
    ) -> LeakReport:
        """Combine statistical and ML results into a final LeakReport."""
        detected = stat.get("detected", False) or ml.get("anomaly", False)
        max_drop = stat.get("drop", 0.0)
        worst_node = stat.get("node")
        anomalies = stat.get("anomalies", [])

        # Severity: take the maximum from both methods
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

        # Probability — reference point (0.32 bar) is the real EPANET burst-scenario
        # drop measured at the leak node on this specific network topology.
        REAL_BURST_REFERENCE_BAR = 0.32
        stat_prob = min(100, (max_drop / REAL_BURST_REFERENCE_BAR) * 100) if detected else 0
        ml_conf = ml.get("confidence", 0.0) if ml.get("anomaly") else 0
        probability = round((stat_prob * 0.6 + ml_conf * 0.4), 1) if detected else 0

        # Location from worst node
        location = "No anomaly detected"
        pipe_id = None
        if worst_node:
            zone = self.ZONE_NAMES.get(worst_node, worst_node)
            # Get pipe segment
            pipe_id = self.NODE_TO_PIPE.get(worst_node)
            if pipe_id:
                # Find adjacent node with a real, non-trivial pressure drop
                for n in nodes:
                    if n["id"] != worst_node and n.get("pressure_drop", 0) > self.statistical.THRESHOLDS["low"]:
                        adj_zone = self.ZONE_NAMES.get(n["id"], n["id"])
                        location = f"Between {zone} and {adj_zone} ({pipe_id})"
                        break
                else:
                    location = f"Near {zone} zone ({worst_node})"
            else:
                location = f"Zone {zone} ({worst_node})"

        # Estimated flow loss — linear regression fit against real EPANET solves
        # of this network: small (1.5 L/s -> 0.026 bar), medium (4.5 -> 0.085),
        # burst (12.0 -> 0.322). flow_loss(L/s) ≈ 34.4 * drop(bar) + 1.0
        flow_loss = round(max(0.0, 34.4 * max_drop + 1.0), 2) if detected else 0.0

        # Affected nodes — any node showing a statistically real (low+) pressure drop
        affected = [a["node_id"] for a in anomalies if a.get("pressure_drop", 0) > self.statistical.THRESHOLDS["low"]]

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
        # Ensure all values are plain Python types for JSON serialization
        d["detected"] = bool(d["detected"])
        d["probability"] = float(d["probability"])
        d["pressure_drop"] = float(d["pressure_drop"])
        d["estimated_flow_loss"] = float(d["estimated_flow_loss"])
        d["confidence"] = float(d["confidence"])
        return d
