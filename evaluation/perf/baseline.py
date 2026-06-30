"""
F0 — Baseline de carga y latencia desde `message_backup` (solo lectura).

Calcula, a partir del histórico real:
  - volumen (total, rango de fechas, requests/día, día y hora pico),
  - distribución de latencia end-to-end (`duration_seconds`: p50/p90/p95/p99/max),
  - throughput de tokens (`tokens_per_second`),
  - mezcla de modelos (`model_used`),
  - una estimación de concurrencia media en hora pico vía Little's law (L = λ·W).

Uso:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evaluation/perf/baseline.py
Salida: resumen en consola + evaluation/perf/out/baseline.json
"""
from __future__ import annotations
import json
import pathlib
from collections import Counter, defaultdict
from datetime import timezone

import numpy as np

from ct.settings.clients import get_mongo_client, mongo_collection_message_backup

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _pct(values: list[float]) -> dict:
    if not values:
        return {}
    arr = np.array(values, dtype=float)
    return {
        "n": int(arr.size),
        "mean": round(float(arr.mean()), 3),
        "p50": round(float(np.percentile(arr, 50)), 3),
        "p90": round(float(np.percentile(arr, 90)), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
        "p99": round(float(np.percentile(arr, 99)), 3),
        "max": round(float(arr.max()), 3),
    }


def main() -> None:
    db = get_mongo_client().get_default_database()
    col = db[mongo_collection_message_backup]

    cur = col.find(
        {},
        {
            "timestamp": 1,
            "duration_seconds": 1,
            "tokens_per_second": 1,
            "total_tokens": 1,
            "model_used": 1,
            "label": 1,
        },
    )

    total = 0
    answered = 0
    durations: list[float] = []
    tps: list[float] = []
    models: Counter = Counter()
    per_day: Counter = Counter()
    per_hour: Counter = Counter()       # hora del día (UTC) 0-23
    per_minute: dict[str, int] = defaultdict(int)  # bucket de 60s -> conteo (para pico)
    ts_min = None
    ts_max = None

    for d in cur:
        total += 1
        ts = d.get("timestamp")
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts_min = ts if ts_min is None or ts < ts_min else ts_min
            ts_max = ts if ts_max is None or ts > ts_max else ts_max
            per_day[ts.strftime("%Y-%m-%d")] += 1
            per_hour[ts.hour] += 1
            per_minute[ts.strftime("%Y-%m-%d %H:%M")] += 1

        if d.get("label") is True:
            answered += 1
            ds = d.get("duration_seconds")
            if isinstance(ds, (int, float)) and ds > 0:
                durations.append(float(ds))
            t = d.get("tokens_per_second")
            if isinstance(t, (int, float)) and t > 0:
                tps.append(float(t))
            models[str(d.get("model_used", "?"))] += 1

    # Pico: día con más requests, y minuto más cargado (proxy de ráfaga).
    peak_day = per_day.most_common(1)[0] if per_day else (None, 0)
    peak_minute = max(per_minute.items(), key=lambda kv: kv[1]) if per_minute else (None, 0)

    dur_stats = _pct(durations)
    # Little's law: concurrencia media ~ tasa de llegada * tiempo de servicio.
    # tasa de llegada pico (req/s) estimada del minuto más cargado.
    peak_rps = round(peak_minute[1] / 60.0, 4) if peak_minute[0] else 0.0
    mean_service = dur_stats.get("mean", 0)
    est_concurrency_peak = round(peak_rps * mean_service, 2) if mean_service else 0.0

    n_days = max(1, len(per_day))
    summary = {
        "total_docs": total,
        "answered_label_true": answered,
        "date_range": {
            "from": ts_min.isoformat() if ts_min else None,
            "to": ts_max.isoformat() if ts_max else None,
            "days_with_traffic": len(per_day),
        },
        "volume": {
            "avg_requests_per_day": round(total / n_days, 1),
            "peak_day": {"date": peak_day[0], "requests": peak_day[1]},
            "peak_minute": {"minute_utc": peak_minute[0], "requests": peak_minute[1]},
            "peak_rps_estimate": peak_rps,
        },
        "latency_end_to_end_seconds": dur_stats,
        "tokens_per_second": _pct(tps),
        "model_mix": dict(models.most_common()),
        "requests_by_hour_utc": {str(h): per_hour.get(h, 0) for h in range(24)},
        "estimated_mean_concurrency_at_peak": est_concurrency_peak,
        "notes": [
            "duration_seconds incluye el tiempo del LLM (dominante); no es latencia de infra pura.",
            "peak_rps_estimate usa el minuto más cargado del histórico (proxy de ráfaga).",
            "est_concurrency = Little's law (L=λ·W) con W=mean(duration). Es PROMEDIO, no el pico instantáneo.",
        ],
    }

    (OUT_DIR / "baseline.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Resumen legible
    print("=" * 64)
    print("BASELINE message_backup")
    print("=" * 64)
    print(f"Total docs:            {total:,}  (answered/label=True: {answered:,})")
    print(f"Rango:                 {summary['date_range']['from']}  ->  {summary['date_range']['to']}")
    print(f"Días con tráfico:      {len(per_day)}")
    print(f"Req/día (prom):        {summary['volume']['avg_requests_per_day']}")
    print(f"Día pico:              {peak_day[0]}  ({peak_day[1]} req)")
    print(f"Minuto pico:           {peak_minute[0]} UTC  ({peak_minute[1]} req)  ~{peak_rps} req/s")
    print("-" * 64)
    if dur_stats:
        print("Latencia end-to-end (s):")
        print(f"  mean {dur_stats['mean']}  p50 {dur_stats['p50']}  p90 {dur_stats['p90']}"
              f"  p95 {dur_stats['p95']}  p99 {dur_stats['p99']}  max {dur_stats['max']}")
    if summary["tokens_per_second"]:
        t = summary["tokens_per_second"]
        print(f"Tokens/seg:            mean {t['mean']}  p50 {t['p50']}  p95 {t['p95']}")
    print(f"Concurrencia media estimada en pico (L=λ·W): {est_concurrency_peak}")
    print("-" * 64)
    print("Modelos:", ", ".join(f"{k}={v}" for k, v in models.most_common()))
    print(f"\nJSON -> {OUT_DIR / 'baseline.json'}")


if __name__ == "__main__":
    main()
