"""
Analiza la telemetría de UI del widget (archivo JSONL, NO MongoDB):
open / close / expand / collapse / product_click. Responde con datos la pregunta de
diseño "¿sidebar sí o no?": tasa de expand y de product_click por apertura.

Lee el archivo que escribe el endpoint /ui-event (por defecto logs/ui_events.jsonl,
configurable con CHATBOT_UI_EVENTS_LOG). Solo lectura.

Uso:
    .venv/Scripts/python.exe evaluation/perf/analyze_ui_events.py [--log logs/ui_events.jsonl] [--days N]
"""
from __future__ import annotations
import argparse
import json
import os
import pathlib
from collections import Counter
from datetime import datetime, timedelta, timezone


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=os.getenv("CHATBOT_UI_EVENTS_LOG", "logs/ui_events.jsonl"))
    ap.add_argument("--days", type=int, default=0, help="solo eventos de los últimos N días (0=todos)")
    args = ap.parse_args()

    path = pathlib.Path(args.log)
    if not path.exists():
        print(f"Aún no existe {path} (sin eventos registrados todavía).")
        return

    cutoff = None
    if args.days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    counts: Counter = Counter()
    users_open: set[str] = set()
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if cutoff is not None:
            try:
                ts = datetime.fromisoformat(rec.get("timestamp", ""))
                if ts < cutoff:
                    continue
            except ValueError:
                pass
        ev = rec.get("event")
        counts[ev] += 1
        total += 1
        if ev == "open" and rec.get("user_id"):
            users_open.add(rec["user_id"])

    if total == 0:
        print(f"{path} está vacío.")
        return

    opens = counts.get("open", 0) or 1
    print("=" * 56)
    print(f"TELEMETRÍA DE UI ({total} eventos) — {path}")
    print("=" * 56)
    for ev in ("open", "close", "expand", "collapse", "product_click"):
        print(f"  {ev:<14} {counts.get(ev, 0)}")
    print("-" * 56)
    print(f"Aperturas: {counts.get('open', 0)}  | usuarios distintos que abrieron: {len(users_open)}")
    print(f"Tasa de EXPAND por apertura:        {counts.get('expand', 0) / opens:.0%}")
    print(f"Tasa de PRODUCT_CLICK por apertura: {counts.get('product_click', 0) / opens:.0%}")
    print("\nLectura: una tasa alta de 'expand' indica que los usuarios necesitan más "
          "ancho → favorece el panel expandible/sidebar.")


if __name__ == "__main__":
    main()
