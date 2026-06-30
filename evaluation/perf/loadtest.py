"""
F3 — Generador de carga asíncrono contra POST /chat (lee el stream completo).

Pensado para correr con el servidor en modo LLM mockeado (CT_FAKE_LLM=1), así
mide la INFRA real (event loop, Mongo de historial/persistencia, threadpool, SSE)
sin costo de OpenAI. Hace una rampa de concurrencia y reporta, por nivel:
throughput (req/s), latencia p50/p95/p99 y tasa de error.

Usa user_id con prefijo LOADTEST_ para poder limpiar después
(ver cleanup_loadtest.py).

Uso:
    .venv/Scripts/python.exe evaluation/perf/loadtest.py \
        --url http://127.0.0.1:8012/chat \
        --concurrency 1,2,5,10,20,40 --requests 60
"""
from __future__ import annotations
import argparse
import asyncio
import json
import pathlib
import time

import aiohttp
import numpy as np

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def _one(session: aiohttp.ClientSession, url: str, payload: dict) -> tuple[float, int]:
    t0 = time.perf_counter()
    try:
        async with session.post(url, json=payload) as r:
            async for _ in r.content.iter_any():  # drena el stream completo
                pass
            return time.perf_counter() - t0, r.status
    except Exception:
        return time.perf_counter() - t0, -1


async def _run_level(url: str, concurrency: int, total: int, query: str) -> dict:
    sem = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=180)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async def task(i: int):
            async with sem:
                payload = {
                    "user_query": query,
                    "user_id": f"LOADTEST_{concurrency}_{i}",
                    "listaPrecio": "2",
                }
                return await _one(session, url, payload)

        t0 = time.perf_counter()
        results = await asyncio.gather(*[task(i) for i in range(total)])
        wall = time.perf_counter() - t0

    lat = np.array([r[0] for r in results], dtype=float)
    statuses = [r[1] for r in results]
    ok = sum(1 for s in statuses if s == 200)
    errors = total - ok
    return {
        "concurrency": concurrency,
        "requests": total,
        "wall_seconds": round(wall, 3),
        "throughput_rps": round(total / wall, 3) if wall > 0 else 0,
        "ok": ok,
        "errors": errors,
        "error_rate": round(errors / total, 4) if total else 0,
        "latency_seconds": {
            "p50": round(float(np.percentile(lat, 50)), 3),
            "p95": round(float(np.percentile(lat, 95)), 3),
            "p99": round(float(np.percentile(lat, 99)), 3),
            "max": round(float(lat.max()), 3),
        },
        "status_codes": {str(s): statuses.count(s) for s in sorted(set(statuses))},
    }


async def main_async(args) -> None:
    levels = [int(x) for x in args.concurrency.split(",")]
    print(f"Target: {args.url}")
    print(f"{'conc':>5} {'reqs':>5} {'rps':>8} {'p50':>7} {'p95':>7} {'p99':>7} {'max':>7} {'err%':>6}")
    out = []
    for conc in levels:
        total = max(args.requests, conc * 3)
        res = await _run_level(args.url, conc, total, args.query)
        out.append(res)
        lt = res["latency_seconds"]
        print(f"{conc:>5} {res['requests']:>5} {res['throughput_rps']:>8} "
              f"{lt['p50']:>7} {lt['p95']:>7} {lt['p99']:>7} {lt['max']:>7} "
              f"{res['error_rate'] * 100:>5.1f}%")

    payload = {"url": args.url, "query": args.query, "levels": out}
    (OUT_DIR / "loadtest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON -> {OUT_DIR / 'loadtest.json'}")
    print("Nota: si el throughput se aplana al subir la concurrencia, el worker está "
          "serializando (probable: pymongo síncrono en el event loop).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8012/chat")
    ap.add_argument("--concurrency", default="1,2,5,10,20,40")
    ap.add_argument("--requests", type=int, default=60, help="requests por nivel (mínimo)")
    ap.add_argument("--query", default="hola, esto es una prueba de carga")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
