"""
F2 — Analiza la instrumentación de F1 ya persistida en `message_backup`:
latencia por tool (`tool_timings`) y por fase (`phase_timings`).

Es la fuente PREFERIDA de latencia por tool: usa args y distribución reales de
producción (mejor que un micro-benchmark sintético). Solo lectura.

Uso:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evaluation/perf/analyze_timings.py [--days 30]
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

from ct.settings.clients import get_mongo_client, mongo_collection_message_backup


def _pct(vals: list[float]) -> str:
    if not vals:
        return "(sin datos)"
    a = np.array(vals, float)
    return (f"n={a.size:>4}  p50={np.percentile(a,50):7.3f}  "
            f"p95={np.percentile(a,95):7.3f}  p99={np.percentile(a,99):7.3f}  max={a.max():7.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0, help="solo docs de los últimos N días (0=todos)")
    args = ap.parse_args()

    db = get_mongo_client().get_default_database()
    col = db[mongo_collection_message_backup]

    q: dict = {"tool_timings": {"$exists": True}}
    if args.days > 0:
        q["timestamp"] = {"$gte": datetime.now(timezone.utc) - timedelta(days=args.days)}

    per_tool: dict[str, list[float]] = defaultdict(list)
    per_tool_calls: dict[str, int] = defaultdict(int)
    per_phase: dict[str, list[float]] = defaultdict(list)
    docs = 0

    for d in col.find(q, {"tool_timings": 1, "phase_timings": 1}):
        docs += 1
        for t in (d.get("tool_timings") or []):
            name = t.get("tool", "?")
            per_tool[name].append(float(t.get("seconds", 0)))
            per_tool_calls[name] += 1
        for ph, sec in (d.get("phase_timings") or {}).items():
            if isinstance(sec, (int, float)):
                per_phase[ph].append(float(sec))

    print("=" * 74)
    print(f"ANÁLISIS DE TIMINGS (docs con instrumentación: {docs})")
    print("=" * 74)
    if docs == 0:
        print("Aún no hay documentos con `tool_timings` (instrumentación F1).")
        print("Se poblará conforme entren requests reales tras desplegar este cambio.")
        return

    print("\nPor FASE (segundos):")
    for ph in ("history_load", "agent_stream", "persist_messages"):
        print(f"  {ph:<18} {_pct(per_phase.get(ph, []))}")

    print("\nPor TOOL (segundos):")
    if not per_tool:
        print("  (ningún request usó tools en el periodo)")
    for name in sorted(per_tool, key=lambda k: -np.median(per_tool[k] or [0])):
        print(f"  {name:<22} calls={per_tool_calls[name]:>4}  {_pct(per_tool[name])}")


if __name__ == "__main__":
    main()
