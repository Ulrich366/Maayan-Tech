"""Standalone smoke for Maayan flowing-points helpers (no FastAPI deps)."""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import Optional


def _normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(ascii_only.lower().split())


def _is_node_flowing(node, leak_node_id: Optional[str]) -> bool:
    status = (getattr(node, "status", "") or "").lower()
    if status in ("leak", "burst"):
        return False
    if bool(getattr(node, "is_anomaly", False)):
        return False
    if leak_node_id and node.id == leak_node_id:
        return False
    return True


@dataclass
class FakeNode:
    id: str
    status: str = "normal"
    is_anomaly: bool = False


def main() -> None:
    assert _normalize_search_text("Cité des Palmiers") == "cite des palmiers"
    assert _normalize_search_text("  Douala  ") == "douala"

    leak = FakeNode(id="J7", status="leak")
    ok = FakeNode(id="J1", status="normal", is_anomaly=False)
    anomalous = FakeNode(id="J2", status="normal", is_anomaly=True)

    assert _is_node_flowing(ok, None) is True
    assert _is_node_flowing(ok, "J7") is True
    assert _is_node_flowing(ok, "J1") is False
    assert _is_node_flowing(leak, None) is False
    assert _is_node_flowing(anomalous, None) is False
    assert math.isfinite(1.0)

    print("maayan flowing-points helpers OK")


if __name__ == "__main__":
    main()
