"""
Continuous learning orchestrator for Maayan ML models.

Records labeled observations from live simulation (and operator feedback),
periodically retrains on the growing dataset, and hot-reloads improved models.
"""

import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

from backend.ai.learning_store import LearningStore
from backend.ai.model_trainer import load_metrics, save_models, train_models

ENABLED = os.getenv("ML_CONTINUOUS_LEARNING", "true").lower() == "true"
RETRAIN_MIN_NEW_SAMPLES = int(os.getenv("ML_RETRAIN_MIN_SAMPLES", "50"))
SAMPLE_INTERVAL_SECONDS = float(os.getenv("ML_SAMPLE_INTERVAL_SECONDS", "30"))
MIN_COMBINED_SAMPLES = int(os.getenv("ML_MIN_TRAINING_SAMPLES", "80"))


class ContinuousLearner:
    """Manages sample collection and background retraining."""

    def __init__(self, ml_detector):
        self.ml = ml_detector
        self.store = LearningStore()
        self._lock = threading.Lock()
        self._retraining = False
        self._samples_since_retrain = 0
        self._total_recorded = 0
        self._last_retrain_at: Optional[str] = None
        self._last_retrain_result: Optional[Dict[str, Any]] = None

    def observe(self, snapshot_dict: Dict[str, Any], report_dict: Dict[str, Any]) -> None:
        """Record a labeled observation and maybe trigger retraining."""
        if not ENABLED:
            return

        ground_truth = snapshot_dict.get("ground_truth")
        if not ground_truth:
            return

        pressures = {n["id"]: n["pressure"] for n in snapshot_dict.get("nodes", [])}
        city = snapshot_dict.get("city", "douala")

        recorded = self.store.record_simulation_sample(
            pressures,
            ground_truth,
            city=city,
            min_interval_seconds=SAMPLE_INTERVAL_SECONDS,
        )

        if recorded:
            self._total_recorded += 1
            self._samples_since_retrain += 1
            logger.debug(
                f"Learning sample recorded (#{self._total_recorded}, "
                f"since_retrain={self._samples_since_retrain})"
            )
            self._maybe_schedule_retrain()

    def record_feedback(
        self,
        pressures: Dict[str, float],
        leak_node: Optional[str],
        severity_class: int,
        city: str = "douala",
    ) -> None:
        """Ingest operator-verified labels and retrain sooner."""
        self.store.record_operator_feedback(pressures, leak_node, severity_class, city)
        self._samples_since_retrain += 5  # weight feedback higher
        self._maybe_schedule_retrain(force=True)

    def _maybe_schedule_retrain(self, force: bool = False) -> None:
        threshold = 1 if force else RETRAIN_MIN_NEW_SAMPLES
        if self._samples_since_retrain < threshold:
            return
        if self._retraining:
            return

        threading.Thread(target=self._retrain_worker, daemon=True).start()

    def _retrain_worker(self) -> None:
        with self._lock:
            if self._retraining:
                return
            self._retraining = True

        try:
            df = self.store.load_combined_dataset()
            if len(df) < MIN_COMBINED_SAMPLES:
                logger.info(
                    f"Continuous learning: {len(df)} samples — "
                    f"need {MIN_COMBINED_SAMPLES} before retrain"
                )
                return

            logger.info(f"Continuous learning: retraining on {len(df)} samples...")
            previous = load_metrics().get("latest", {})
            models, metrics = train_models(df)

            # Keep new model unless holdout accuracy drops significantly
            prev_acc = previous.get("severity_accuracy")
            new_acc = metrics.get("severity_accuracy", 0)
            if prev_acc is not None and new_acc < prev_acc - 0.05:
                logger.warning(
                    f"Retrain skipped — severity accuracy dropped "
                    f"({prev_acc:.3f} -> {new_acc:.3f})"
                )
                self._samples_since_retrain = 0
                return

            save_models(models, metrics)
            self.ml.hot_reload(models)

            self._samples_since_retrain = 0
            self._last_retrain_at = datetime.utcnow().isoformat()
            self._last_retrain_result = metrics
            logger.info(
                f"Continuous learning: models updated — "
                f"severity_acc={metrics['severity_accuracy']}, "
                f"samples={metrics['samples']}"
            )
        except Exception as e:
            logger.error(f"Continuous learning retrain failed: {e}")
        finally:
            self._retraining = False

    def get_status(self) -> Dict[str, Any]:
        metrics_data = load_metrics()
        return {
            "enabled": ENABLED,
            "retraining": self._retraining,
            "total_recorded": self._total_recorded,
            "samples_since_retrain": self._samples_since_retrain,
            "retrain_threshold": RETRAIN_MIN_NEW_SAMPLES,
            "last_retrain_at": self._last_retrain_at,
            "last_retrain_metrics": self._last_retrain_result or metrics_data.get("latest"),
            "metrics_history": metrics_data.get("history", [])[-10:],
            **self.store.get_stats(),
        }

    def force_retrain(self) -> Dict[str, Any]:
        """Manually trigger a retrain (API / CLI)."""
        if not self._retraining:
            threading.Thread(target=self._retrain_worker, daemon=True).start()
        return {"scheduled": True, "status": self.get_status()}
