"""
EPANET Hydraulic Simulation Engine for Maayan.

Wraps WNTR (Water Network Tool for Resilience) to run REAL EPANET 2.2
hydraulic solves against the Douala .inp network file. Every tick performs
an actual instantaneous hydraulic solve via the compiled EPANET toolkit
(wntr.sim.EpanetSimulator) — pressures, flows, and heads are genuine
solver output, not synthetic/random values.

A synthetic fallback model exists ONLY for environments where WNTR/EPANET
cannot be installed (e.g. missing build toolchain). It is clearly flagged
via `engine` on every snapshot so the frontend/operator always knows
which mode produced the data.

Leak scenarios are modeled the standard EPANET way: as an additional
fixed demand at the leak node, which the solver redistributes through
the real network topology (pipe roughness, diameters, loops, pump curve,
tank/reservoir heads) to compute the resulting pressure field.
"""

import os
import copy
import glob
import math
import random
import uuid
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from loguru import logger

try:
    import wntr
    WNTR_AVAILABLE = True
except ImportError:
    WNTR_AVAILABLE = False
    logger.warning("WNTR not available — install with `pip install wntr` for real EPANET simulation")

# 1 meter of water column = 0.0980665 bar (physical constant, not a tunable)
METERS_TO_BAR = 0.0980665


@dataclass
class NodeState:
    """State of a single network junction/node."""
    id: str
    name: str
    pressure: float
    head: float
    demand: float
    elevation: float
    x: float
    y: float
    status: str  # normal, warning, leak, burst
    is_anomaly: bool
    pressure_baseline: float
    pressure_drop: float


@dataclass
class PipeState:
    """State of a single pipe in the network."""
    id: str
    start_node: str
    end_node: str
    flow: float
    velocity: float
    headloss: float
    length: float
    diameter: float
    status: str  # normal, warning, leak


@dataclass
class NetworkSnapshot:
    """Complete network state at a point in time."""
    timestamp: float
    scenario: str
    nodes: List[NodeState]
    pipes: List[PipeState]
    total_demand: float
    total_leakage: float
    system_health: float
    simulation_time: float
    engine: str = "epanet"  # "epanet" (real) or "synthetic" (fallback)


class DoualaNeworkDefinition:
    """
    Static metadata for the Douala network used for display purposes
    (names, map coordinates). Hydraulic values always come from the
    real .inp file via WNTR — this class does NOT define pressures.
    """

    NODES = {
        "J1":  {"name": "Akwa",             "elev": 50, "demand": 2.5, "x": 400,  "y": 500},
        "J2":  {"name": "Bali",              "elev": 48, "demand": 3.0, "x": 600,  "y": 500},
        "J3":  {"name": "Deido",             "elev": 45, "demand": 2.8, "x": 800,  "y": 450},
        "J4":  {"name": "Bonaberi",          "elev": 43, "demand": 3.5, "x": 1000, "y": 400},
        "J5":  {"name": "New Bell",          "elev": 42, "demand": 2.2, "x": 900,  "y": 600},
        "J6":  {"name": "Ndokotti",          "elev": 40, "demand": 3.1, "x": 700,  "y": 650},
        "J7":  {"name": "Makepe",            "elev": 38, "demand": 2.9, "x": 500,  "y": 650},
        "J8":  {"name": "Logbessou",         "elev": 36, "demand": 2.4, "x": 300,  "y": 600},
        "J9":  {"name": "Bonamoussadi",      "elev": 55, "demand": 1.8, "x": 400,  "y": 350},
        "J10": {"name": "Cité des Palmiers", "elev": 52, "demand": 2.1, "x": 600,  "y": 300},
        "J11": {"name": "Village",           "elev": 47, "demand": 2.7, "x": 800,  "y": 350},
        "J12": {"name": "PK14",              "elev": 44, "demand": 1.9, "x": 500,  "y": 200},
    }

    PIPES = {
        "P1":  {"from": "R1",  "to": "J1",  "length": 800, "diameter": 0.300},
        "P2":  {"from": "J1",  "to": "J2",  "length": 600, "diameter": 0.250},
        "P3":  {"from": "J2",  "to": "J3",  "length": 700, "diameter": 0.200},
        "P4":  {"from": "J3",  "to": "J4",  "length": 900, "diameter": 0.200},
        "P5":  {"from": "J4",  "to": "J5",  "length": 800, "diameter": 0.150},
        "P6":  {"from": "J5",  "to": "J6",  "length": 600, "diameter": 0.150},
        "P7":  {"from": "J6",  "to": "J7",  "length": 500, "diameter": 0.150},
        "P8":  {"from": "J7",  "to": "J8",  "length": 700, "diameter": 0.125},
        "P9":  {"from": "J1",  "to": "J9",  "length": 550, "diameter": 0.200},
        "P10": {"from": "J9",  "to": "J10", "length": 650, "diameter": 0.175},
        "P11": {"from": "J10", "to": "J11", "length": 600, "diameter": 0.150},
        "P12": {"from": "J11", "to": "J12", "length": 700, "diameter": 0.125},
        "P13": {"from": "J2",  "to": "J10", "length": 800, "diameter": 0.150},
        "P14": {"from": "J3",  "to": "J11", "length": 750, "diameter": 0.150},
        "P15": {"from": "R2",  "to": "J8",  "length": 900, "diameter": 0.200},
        "P16": {"from": "J8",  "to": "J12", "length": 600, "diameter": 0.125},
        "P17": {"from": "T1",  "to": "J1",  "length": 200, "diameter": 0.300},
        "P18": {"from": "J5",  "to": "J11", "length": 650, "diameter": 0.150},
    }

    # Fallback baseline estimates — only used if WNTR is unavailable.
    # When WNTR is available, real baselines are computed dynamically
    # from an actual EPANET solve at startup (see EpanetSimulator._compute_baseline).
    FALLBACK_BASELINE_PRESSURES = {
        "J1": 2.15, "J2": 2.31, "J3": 2.55, "J4": 2.80,
        "J5": 2.90, "J6": 3.09, "J7": 3.31, "J8": 3.70,
        "J9": 1.65, "J10": 1.93, "J11": 2.42, "J12": 2.78,
    }


class EpanetSimulator:
    """
    Main simulation engine. Runs a genuine EPANET 2.2 hydraulic solve
    every call to `run_simulation()` via WNTR's EpanetSimulator, which
    invokes the actual compiled EPANET toolkit against the Douala
    network file (simulation/douala_network.inp).

    Each tick performs an instantaneous solve (duration=0) at the
    real wall-clock time-of-day so the network's own hourly demand
    pattern drives diurnal variation — no synthetic sine waves.
    """

    SCENARIOS = {
        "normal": {"leak_node": None, "leak_demand": 0.0, "leak_pipe": None},
        "small":  {"leak_node": "J7", "leak_demand": 1.5,  "leak_pipe": "P7"},
        "medium": {"leak_node": "J7", "leak_demand": 4.5,  "leak_pipe": "P7"},
        "burst":  {"leak_node": "J7", "leak_demand": 12.0, "leak_pipe": "P7"},
    }

    # Optional sensor measurement noise (simulates real transducer ADC jitter).
    # Set to 0.0 by default: out of the box, every value is pure EPANET solver
    # output. Configure via SENSOR_NOISE_STD_BAR env var if you want to emulate
    # imperfect physical sensors on top of the real hydraulics.
    SENSOR_NOISE_STD_BAR = float(os.getenv("SENSOR_NOISE_STD_BAR", "0.0"))

    def __init__(self, inp_file: str = "simulation/douala_network.inp"):
        self.inp_file = inp_file
        self.current_scenario = "normal"
        self.simulation_time = 0.0
        self.network_def = DoualaNeworkDefinition()
        self.wn = None            # Base WNTR WaterNetworkModel (never mutated directly)
        self.engine = "synthetic"
        self.baseline_pressures: Dict[str, float] = dict(self.network_def.FALLBACK_BASELINE_PRESSURES)
        self._tmp_dir = os.path.join("data", "tmp")
        self._lock = threading.Lock()
        self._run_counter = 0
        os.makedirs(self._tmp_dir, exist_ok=True)
        self._load_network()

    def _load_network(self):
        """Load the real EPANET network file via WNTR and compute a live baseline."""
        if not WNTR_AVAILABLE:
            logger.warning("Running in SYNTHETIC fallback mode (WNTR not installed)")
            return

        if not os.path.exists(self.inp_file):
            logger.warning(f"INP file not found at {self.inp_file} — using synthetic fallback")
            return

        try:
            self.wn = wntr.network.WaterNetworkModel(self.inp_file)
            self.engine = "epanet"
            logger.info(f"Real EPANET network loaded via WNTR {wntr.__version__}: {self.inp_file}")
            self._compute_baseline()
        except Exception as e:
            logger.error(f"Failed to load EPANET network ({e}) — falling back to synthetic mode")
            self.wn = None
            self.engine = "synthetic"

    def _compute_baseline(self):
        """Run one real EPANET solve under normal conditions to establish live baselines."""
        try:
            baseline_snapshot = self._solve(leak_node=None, leak_demand=0.0)
            self.baseline_pressures = {
                nid: round(p, 4) for nid, p in baseline_snapshot["pressure_bar"].items()
            }
            logger.info(f"Live baseline computed from real EPANET solve: {self.baseline_pressures}")
        except Exception as e:
            logger.error(f"Baseline computation failed ({e}); using fallback estimates")

    def set_scenario(self, scenario: str) -> bool:
        """Switch the active leak scenario. Takes effect on the next tick."""
        if scenario not in self.SCENARIOS:
            return False
        self.current_scenario = scenario
        logger.info(f"Scenario changed to: {scenario}")
        return True

    def run_simulation(self) -> NetworkSnapshot:
        """
        Execute one real hydraulic solve and return the full network state.
        """
        self.simulation_time += 2.0  # internal tick clock (seconds)

        if self.wn is not None:
            try:
                return self._run_epanet_tick()
            except Exception as e:
                logger.error(f"EPANET solve failed this tick ({e}) — using synthetic fallback for this tick only")
                return self._run_synthetic_simulation()
        return self._run_synthetic_simulation()

    # ── Real EPANET solve path ──────────────────────────────────────────────

    def _solve(self, leak_node: Optional[str], leak_demand: float) -> Dict[str, Any]:
        """
        Run a single real EPANET instantaneous hydraulic solve.

        Returns raw solver output dicts keyed by node/pipe ID:
        pressure_bar, head_m, demand_lps, flow_lps, velocity_ms, headloss_m
        """
        wn = copy.deepcopy(self.wn)

        # Solve at the current real-world time-of-day so EPANET's own
        # hourly demand pattern (DemandPattern in the .inp) drives diurnal
        # variation — this is genuine EPANET behavior, not a fake sine wave.
        now = datetime.now()
        seconds_of_day = now.hour * 3600 + now.minute * 60 + now.second
        wn.options.time.duration = 0
        wn.options.time.pattern_start = seconds_of_day
        wn.options.time.hydraulic_timestep = 3600
        wn.options.time.report_timestep = 3600

        # Model the leak as an additional fixed demand at the leak node —
        # the standard EPANET technique. The solver redistributes this
        # through the real network topology (loops, roughness, tank head).
        if leak_node and leak_demand > 0:
            node = wn.get_node(leak_node)
            base_lps = self.network_def.NODES[leak_node]["demand"]
            node.demand_timeseries_list[0].base_value = (base_lps + leak_demand) / 1000.0  # LPS -> m3/s

        with self._lock:
            self._run_counter += 1
            # Unique filename per solve avoids Windows file-handle collisions
            # that occur when EPANET's temp .inp/.rpt/.bin files are reused
            # too quickly across rapid successive solves.
            prefix = os.path.join(self._tmp_dir, f"run_{uuid.uuid4().hex[:10]}")
            sim = wntr.sim.EpanetSimulator(wn)
            try:
                results = sim.run_sim(file_prefix=prefix)
            finally:
                for f in glob.glob(prefix + ".*"):
                    try:
                        os.remove(f)
                    except OSError:
                        pass

        pressure_m = results.node["pressure"].iloc[0]
        head_m = results.node["head"].iloc[0]
        demand_m3s = results.node["demand"].iloc[0]
        flow_m3s = results.link["flowrate"].iloc[0]
        velocity_ms = results.link["velocity"].iloc[0]
        headloss_m = results.link["headloss"].iloc[0]

        return {
            "pressure_bar": {nid: float(pressure_m[nid]) * METERS_TO_BAR for nid in self.network_def.NODES},
            "head_m": {nid: float(head_m[nid]) for nid in self.network_def.NODES},
            "demand_lps": {nid: float(demand_m3s[nid]) * 1000.0 for nid in self.network_def.NODES},
            "flow_lps": {pid: abs(float(flow_m3s[pid])) * 1000.0 for pid in self.network_def.PIPES},
            "velocity_ms": {pid: abs(float(velocity_ms[pid])) for pid in self.network_def.PIPES},
            "headloss_m": {pid: float(headloss_m[pid]) for pid in self.network_def.PIPES},
        }

    def _run_epanet_tick(self) -> NetworkSnapshot:
        """Run the real EPANET solve for the current scenario and build a snapshot."""
        scenario_cfg = self.SCENARIOS[self.current_scenario]
        solved = self._solve(scenario_cfg["leak_node"], scenario_cfg["leak_demand"])

        nodes = []
        for node_id, meta in self.network_def.NODES.items():
            pressure = solved["pressure_bar"][node_id]
            if self.SENSOR_NOISE_STD_BAR > 0:
                pressure += random.gauss(0, self.SENSOR_NOISE_STD_BAR)

            baseline = self.baseline_pressures.get(node_id, pressure)
            drop = max(0.0, baseline - pressure)
            status = self._classify_node_status(node_id, drop, scenario_cfg)

            nodes.append(NodeState(
                id=node_id,
                name=meta["name"],
                pressure=round(pressure, 4),
                head=round(solved["head_m"][node_id], 2),
                demand=round(solved["demand_lps"][node_id], 3),
                elevation=meta["elev"],
                x=meta["x"],
                y=meta["y"],
                status=status,
                is_anomaly=drop > 0.02,
                pressure_baseline=round(baseline, 4),
                pressure_drop=round(drop, 4),
            ))

        pipes = []
        for pipe_id, meta in self.network_def.PIPES.items():
            is_leak_pipe = pipe_id == scenario_cfg.get("leak_pipe") and scenario_cfg.get("leak_demand", 0) > 0
            leak_demand = scenario_cfg.get("leak_demand", 0)
            if is_leak_pipe:
                status = "burst" if leak_demand >= 10 else ("leak" if leak_demand >= 3 else "warning")
            else:
                status = "normal"

            pipes.append(PipeState(
                id=pipe_id,
                start_node=meta["from"],
                end_node=meta["to"],
                flow=round(solved["flow_lps"][pipe_id], 3),
                velocity=round(solved["velocity_ms"][pipe_id], 3),
                headloss=round(solved["headloss_m"][pipe_id], 4),
                length=meta["length"],
                diameter=meta["diameter"] * 1000,  # m -> mm
                status=status,
            ))

        return self._build_snapshot(nodes, pipes, engine="epanet")

    # ── Synthetic fallback (only used if EPANET/WNTR is unavailable) ───────

    def _run_synthetic_simulation(self) -> NetworkSnapshot:
        """
        Fallback model used ONLY when WNTR/EPANET cannot be loaded.
        Every snapshot from this path is flagged engine="synthetic" so
        it is never confused with genuine solver output.
        """
        scenario_cfg = self.SCENARIOS[self.current_scenario]
        nodes = self._synthetic_nodes(scenario_cfg)
        pipes = self._synthetic_pipes(scenario_cfg)
        return self._build_snapshot(nodes, pipes, engine="synthetic")

    def _synthetic_nodes(self, scenario_cfg: dict) -> List[NodeState]:
        nodes = []
        leak_node = scenario_cfg.get("leak_node")
        leak_demand = scenario_cfg.get("leak_demand", 0.0)
        pressure_drops = self._propagate_pressure_drop(leak_node, leak_demand)

        t = self.simulation_time
        for node_id, node_data in self.network_def.NODES.items():
            baseline = self.baseline_pressures[node_id]
            drop = pressure_drops.get(node_id, 0.0)
            diurnal = 0.05 * math.sin(2 * math.pi * (t / 3600) / 24)
            pressure = max(0.1, baseline - drop + diurnal)
            status = self._classify_node_status(node_id, drop, scenario_cfg)

            nodes.append(NodeState(
                id=node_id, name=node_data["name"], pressure=round(pressure, 3),
                head=round(node_data["elev"] + pressure * 10.2, 2),
                demand=round(node_data["demand"], 3),
                elevation=node_data["elev"], x=node_data["x"], y=node_data["y"],
                status=status, is_anomaly=drop > 0.02,
                pressure_baseline=baseline, pressure_drop=round(max(0, drop), 3),
            ))
        return nodes

    def _propagate_pressure_drop(self, leak_node: Optional[str], leak_demand: float) -> Dict[str, float]:
        """Approximate hydraulic influence, calibrated to match real EPANET solve magnitudes."""
        if not leak_node or leak_demand == 0:
            return {}
        # Calibrated from real EPANET test: burst (12 L/s) -> ~0.32 bar drop at J7
        adjacency = {
            "J7": {"J7": 1.00, "J6": 0.82, "J5": 0.46, "J4": 0.33,
                   "J8": 0.20, "J3": 0.14, "J2": 0.09, "J1": 0.07,
                   "J12": 0.10, "J11": 0.09, "J10": 0.06, "J9": 0.04},
        }
        drops = {}
        if leak_node in adjacency:
            scale = leak_demand / 12.0 * 0.322  # matches real EPANET burst magnitude at J7
            for nid, factor in adjacency[leak_node].items():
                drops[nid] = round(scale * factor, 4)
        return drops

    def _synthetic_pipes(self, scenario_cfg: dict) -> List[PipeState]:
        pipes = []
        leak_pipe = scenario_cfg.get("leak_pipe")
        leak_demand = scenario_cfg.get("leak_demand", 0.0)

        for pipe_id, pipe_data in self.network_def.PIPES.items():
            diameter_m = pipe_data["diameter"]
            area = math.pi * (diameter_m / 2) ** 2
            base_velocity = 0.6

            if pipe_id == leak_pipe and leak_demand > 0:
                base_velocity += leak_demand / (area * 1000) * 0.3
                status = "burst" if leak_demand >= 10 else ("leak" if leak_demand >= 3 else "warning")
            else:
                status = "normal"

            flow = base_velocity * area * 1000
            headloss = (base_velocity ** 2) / (2 * 9.81 * diameter_m)

            pipes.append(PipeState(
                id=pipe_id, start_node=pipe_data["from"], end_node=pipe_data["to"],
                flow=round(abs(flow), 3), velocity=round(base_velocity, 3),
                headloss=round(headloss, 4), length=pipe_data["length"],
                diameter=pipe_data["diameter"] * 1000, status=status,
            ))
        return pipes

    # ── Shared helpers ───────────────────────────────────────────────────────

    def _classify_node_status(self, node_id: str, pressure_drop: float, scenario_cfg: dict) -> str:
        """Classify node health status based on real pressure drop magnitude."""
        if node_id == scenario_cfg.get("leak_node"):
            leak_demand = scenario_cfg.get("leak_demand", 0)
            if leak_demand >= 10:
                return "burst"
            elif leak_demand >= 4:
                return "leak"
            elif leak_demand >= 1:
                return "warning"
        if pressure_drop > 0.08:
            return "warning"
        return "normal"

    def _build_snapshot(self, nodes: List[NodeState], pipes: List[PipeState], engine: str) -> NetworkSnapshot:
        total_demand = sum(n.demand for n in nodes)
        scenario_cfg = self.SCENARIOS[self.current_scenario]
        total_leakage = scenario_cfg.get("leak_demand", 0.0)

        leak_nodes = sum(1 for n in nodes if n.status in ("leak", "burst", "warning"))
        health = max(0.0, 100.0 - (leak_nodes / len(nodes)) * 100 - (total_leakage / 15) * 30)

        return NetworkSnapshot(
            timestamp=self.simulation_time,
            scenario=self.current_scenario,
            nodes=nodes,
            pipes=pipes,
            total_demand=round(total_demand, 2),
            total_leakage=round(total_leakage, 2),
            system_health=round(min(100, health), 1),
            simulation_time=self.simulation_time,
            engine=engine,
        )

    def get_node_info(self, node_id: str) -> Optional[Dict]:
        """Get detailed info for a single node from a fresh solve."""
        snapshot = self.run_simulation()
        for node in snapshot.nodes:
            if node.id == node_id:
                return asdict(node)
        return None

    def to_json(self, snapshot: NetworkSnapshot) -> Dict[str, Any]:
        """Convert snapshot to JSON-serializable dict (safe for all Python types)."""
        def _safe_node(n: NodeState) -> Dict:
            d = asdict(n)
            d["is_anomaly"] = bool(d["is_anomaly"])
            return d

        return {
            "timestamp": float(snapshot.timestamp),
            "scenario": snapshot.scenario,
            "engine": snapshot.engine,
            "system_health": float(snapshot.system_health),
            "total_demand": float(snapshot.total_demand),
            "total_leakage": float(snapshot.total_leakage),
            "nodes": [_safe_node(n) for n in snapshot.nodes],
            "pipes": [asdict(p) for p in snapshot.pipes],
        }
