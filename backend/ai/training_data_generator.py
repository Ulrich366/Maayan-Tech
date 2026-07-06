"""
Training Data Generator for Maayan ML Models.

Generates 500+ leak scenario samples by running REAL EPANET 2.2 hydraulic
solves (via WNTR) against the actual Douala network topology, varying leak
location, severity, and time-of-day. This satisfies the project requirement:
"Train initially using simulated data generated automatically from EPANET."

No pressure values in the output CSV are hand-invented — every row is the
literal output of an EPANET hydraulic solve for a randomly sampled leak
configuration.

Usage: python -m backend.ai.training_data_generator
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.ai.model_trainer import NODE_FEATURES as NODE_IDS, SCENARIO_TO_CLASS

# Candidate leak locations. Only used with the real EPANET solver, which
# correctly propagates the hydraulic effect of a leak at any junction
# through the network's actual pipe topology, loops, and tank/reservoir heads.
LEAK_CANDIDATE_NODES = ["J7", "J3", "J5", "J6", "J8"]

SEVERITY_BINS = [
    # (label, min_lps, max_lps, class_id)
    ("normal", 0.0, 0.0, 0),
    ("small",  0.5, 2.5, 1),
    ("medium", 2.5, 6.5, 2),
    ("burst",  8.0, 15.0, 3),
]
BIN_WEIGHTS = [0.35, 0.20, 0.25, 0.20]


def generate_dataset(n_samples: int = 600) -> pd.DataFrame:
    """
    Generate the training dataset using real EPANET hydraulic solves.

    Each row is one instantaneous EPANET solve at a randomized time-of-day
    with a randomized leak configuration (or none, for the "normal" class).
    """
    from backend.epanet.simulator import EpanetSimulator

    sim = EpanetSimulator()
    if sim.engine != "epanet":
        raise RuntimeError(
            "Real EPANET/WNTR is not available in this environment. "
            "Install it with `pip install wntr` to generate physically-real "
            "training data. (No fallback is used here intentionally — "
            "this script's whole purpose is to produce genuine EPANET output.)"
        )

    logger.info(f"Real EPANET engine confirmed (WNTR). Generating {n_samples} solves...")
    logger.info(f"Baseline pressures (bar, live from EPANET): {sim.baseline_pressures}")

    rows = []
    for i in range(n_samples):
        bin_idx = np.random.choice(len(SEVERITY_BINS), p=BIN_WEIGHTS)
        label, lo, hi, class_id = SEVERITY_BINS[bin_idx]

        if label == "normal":
            leak_node = "none"
            leak_demand = 0.0
        else:
            leak_node = str(np.random.choice(LEAK_CANDIDATE_NODES))
            leak_demand = round(float(np.random.uniform(lo, hi)), 3)

        solved = sim._solve(leak_node if leak_node != "none" else None, leak_demand)

        row = {nid: round(solved["pressure_bar"][nid], 4) for nid in NODE_IDS}
        row["leak_node"] = leak_node
        row["leak_node_idx"] = NODE_IDS.index(leak_node) if leak_node in NODE_IDS else -1
        row["leak_severity_lps"] = leak_demand
        row["scenario"] = label
        row["label"] = class_id
        row["sample_id"] = i
        rows.append(row)

        if (i + 1) % 100 == 0:
            logger.info(f"  ...{i + 1}/{n_samples} real EPANET solves complete")

    return pd.DataFrame(rows)


def save_dataset(df: pd.DataFrame, output_dir: str = "data/training"):
    """Save training dataset to CSV with metadata."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = os.path.join(output_dir, f"training_data_{timestamp}.csv")
    df.to_csv(csv_path, index=False)
    logger.info(f"Dataset saved: {csv_path} ({len(df)} samples)")

    df.to_csv(os.path.join(output_dir, "training_data_latest.csv"), index=False)

    meta = {
        "generated_at": timestamp,
        "source": "real EPANET 2.2 hydraulic solves via WNTR",
        "samples": len(df),
        "features": NODE_IDS,
        "scenario_distribution": df["scenario"].value_counts().to_dict(),
        "label_distribution": df["label"].value_counts().to_dict(),
    }
    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)

    return csv_path


if __name__ == "__main__":
    logger.info("Generating training dataset from REAL EPANET simulations...")
    df = generate_dataset(n_samples=600)
    path = save_dataset(df)
    logger.info(f"Done. Scenario distribution:\n{df['scenario'].value_counts()}")
    logger.info(f"Saved to: {path}")
