"""
Persistent store for continuous-learning training samples.

Accumulates labeled pressure vectors from live simulation ticks (ground truth
from EPANET scenarios) and optional operator feedback for Phase 2 hardware.
"""

import os
import json
import hashlib
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from backend.ai.model_trainer import NODE_FEATURES, SCENARIO_TO_CLASS

CONTINUOUS_DIR = "data/training"
CONTINUOUS_FILE = os.path.join(CONTINUOUS_DIR, "continuous_samples.csv")
FEEDBACK_FILE = os.path.join(CONTINUOUS_DIR, "operator_feedback.csv")
LATEST_BASELINE = os.path.join(CONTINUOUS_DIR, "training_data_latest.csv")

COLUMNS = (
    NODE_FEATURES
    + ["leak_node", "leak_node_idx", "leak_severity_lps", "scenario", "label", "city", "source", "recorded_at"]
)


class LearningStore:
    """Thread-safe append-only store for ML training observations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last_fingerprint: Dict[str, float] = {}
        os.makedirs(CONTINUOUS_DIR, exist_ok=True)

    def _fingerprint(self, pressures: Dict[str, float], scenario: str, city: str) -> str:
        rounded = tuple(round(pressures.get(n, 0.0), 3) for n in NODE_FEATURES)
        raw = f"{city}|{scenario}|{rounded}"
        return hashlib.md5(raw.encode()).hexdigest()

    def record_simulation_sample(
        self,
        pressures: Dict[str, float],
        ground_truth: Dict[str, Any],
        city: str = "douala",
        min_interval_seconds: float = 30.0,
    ) -> bool:
        """
        Store one labeled sample from a live simulation tick.
        Rate-limited per (city, scenario, pressure fingerprint).
        Returns True if a new row was appended.
        """
        scenario = ground_truth.get("scenario", "normal")
        leak_node = ground_truth.get("leak_node") or "none"
        leak_demand = float(ground_truth.get("leak_demand", 0.0))
        severity_class = int(ground_truth.get("severity_class", SCENARIO_TO_CLASS.get(scenario, 0)))
        leak_node_idx = NODE_FEATURES.index(leak_node) if leak_node in NODE_FEATURES else -1

        fp = self._fingerprint(pressures, scenario, city)
        now = datetime.utcnow().timestamp()

        with self._lock:
            last = self._last_fingerprint.get(fp, 0.0)
            if now - last < min_interval_seconds:
                return False
            self._last_fingerprint[fp] = now

            row = {nid: round(pressures.get(nid, 0.0), 4) for nid in NODE_FEATURES}
            row.update({
                "leak_node": leak_node,
                "leak_node_idx": leak_node_idx,
                "leak_severity_lps": leak_demand,
                "scenario": scenario,
                "label": severity_class,
                "city": city,
                "source": "simulation",
                "recorded_at": datetime.utcnow().isoformat(),
            })
            self._append_row(CONTINUOUS_FILE, row)
            return True

    def record_operator_feedback(
        self,
        pressures: Dict[str, float],
        leak_node: Optional[str],
        severity_class: int,
        city: str = "douala",
    ) -> None:
        """Store a human-verified label (Phase 2 / field validation)."""
        leak_node = leak_node or "none"
        leak_node_idx = NODE_FEATURES.index(leak_node) if leak_node in NODE_FEATURES else -1
        scenario = {0: "normal", 1: "small", 2: "medium", 3: "burst"}.get(severity_class, "normal")

        row = {nid: round(pressures.get(nid, 0.0), 4) for nid in NODE_FEATURES}
        row.update({
            "leak_node": leak_node,
            "leak_node_idx": leak_node_idx,
            "leak_severity_lps": 0.0,
            "scenario": scenario,
            "label": severity_class,
            "city": city,
            "source": "operator",
            "recorded_at": datetime.utcnow().isoformat(),
        })
        with self._lock:
            self._append_row(FEEDBACK_FILE, row)

    def _append_row(self, path: str, row: Dict[str, Any]) -> None:
        df_new = pd.DataFrame([row])
        if os.path.exists(path):
            df_new.to_csv(path, mode="a", header=False, index=False)
        else:
            df_new.to_csv(path, index=False)
        self._trim_file(path)

    def _trim_file(self, path: str, max_rows: int = 10000) -> None:
        try:
            df = pd.read_csv(path)
            if len(df) > max_rows:
                df.tail(max_rows).to_csv(path, index=False)
        except Exception as e:
            logger.warning(f"Could not trim {path}: {e}")

    def load_combined_dataset(self) -> pd.DataFrame:
        """Merge baseline EPANET training data with continuous + feedback samples."""
        frames: List[pd.DataFrame] = []

        if os.path.exists(LATEST_BASELINE):
            frames.append(pd.read_csv(LATEST_BASELINE))

        for path in (CONTINUOUS_FILE, FEEDBACK_FILE):
            if os.path.exists(path):
                try:
                    df = pd.read_csv(path)
                    if len(df) > 0:
                        frames.append(df)
                except Exception as e:
                    logger.warning(f"Could not read {path}: {e}")

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)

        # Deduplicate near-identical pressure vectors
        pressure_cols = NODE_FEATURES
        combined["_fp"] = combined[pressure_cols].round(3).astype(str).agg("|".join, axis=1)
        combined = combined.drop_duplicates(subset=["_fp", "label", "leak_node"], keep="last")
        combined = combined.drop(columns=["_fp"])

        if "leak_node_idx" not in combined.columns:
            combined["leak_node_idx"] = combined["leak_node"].apply(
                lambda n: NODE_FEATURES.index(n) if n in NODE_FEATURES else -1
            )

        return combined

    def count_samples(self) -> Dict[str, int]:
        counts = {"baseline": 0, "continuous": 0, "feedback": 0, "combined": 0}
        if os.path.exists(LATEST_BASELINE):
            try:
                counts["baseline"] = len(pd.read_csv(LATEST_BASELINE))
            except Exception:
                pass
        if os.path.exists(CONTINUOUS_FILE):
            try:
                counts["continuous"] = len(pd.read_csv(CONTINUOUS_FILE))
            except Exception:
                pass
        if os.path.exists(FEEDBACK_FILE):
            try:
                counts["feedback"] = len(pd.read_csv(FEEDBACK_FILE))
            except Exception:
                pass
        counts["combined"] = len(self.load_combined_dataset())
        return counts

    def get_stats(self) -> Dict[str, Any]:
        counts = self.count_samples()
        latest_recorded = None
        if os.path.exists(CONTINUOUS_FILE):
            try:
                df = pd.read_csv(CONTINUOUS_FILE)
                if len(df) > 0 and "recorded_at" in df.columns:
                    latest_recorded = df["recorded_at"].iloc[-1]
            except Exception:
                pass
        return {
            "sample_counts": counts,
            "latest_continuous_sample": latest_recorded,
        }
