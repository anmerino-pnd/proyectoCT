"""
F5 (opt-in) — Índices recomendados para acotar crecimiento y acelerar lecturas.

⚠️  DESTRUCTIVO (TTL): crear un índice TTL sobre `message_backup.timestamp` BORRA
    automáticamente los documentos más viejos que `--ttl-days`. El histórico actual
    llega hasta 2025-06; con 90 días se eliminaría casi todo. NO se ejecuta solo.

Por eso este script:
  - por defecto solo MUESTRA (dry-run) qué haría y cuántos docs caerían bajo el TTL,
  - exige `--apply` para crear índices,
  - exige además `--ttl-days N` explícito para el índice TTL (si se omite, NO crea TTL).

Uso:
    # ver qué haría (no cambia nada):
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evaluation/perf/create_indexes.py
    # crear solo índices NO destructivos (session_id):
    ... create_indexes.py --apply
    # crear también TTL de 180 días (BORRA lo más viejo):
    ... create_indexes.py --apply --ttl-days 180
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone

from ct.settings.clients import (
    get_mongo_client,
    mongo_collection_message_backup,
    mongo_collection_sessions,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Crear los índices (si se omite, dry-run).")
    ap.add_argument("--ttl-days", type=int, default=None,
                    help="Días de retención para el índice TTL en message_backup (DESTRUCTIVO).")
    args = ap.parse_args()

    db = get_mongo_client().get_default_database()
    backup = db[mongo_collection_message_backup]
    sessions = db[mongo_collection_sessions]

    print("Índices NO destructivos propuestos:")
    print(f"  - {mongo_collection_sessions}.session_id (acelera get_session_history / ban)")
    print(f"  - {mongo_collection_message_backup}.timestamp (acelera baseline/reportes)")

    if args.ttl_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.ttl_days)
        would_delete = backup.count_documents({"timestamp": {"$lt": cutoff}})
        print(f"\n⚠️  TTL={args.ttl_days}d sobre message_backup.timestamp")
        print(f"    Documentos que el TTL eliminaría (timestamp < {cutoff.date()}): {would_delete:,}")

    if not args.apply:
        print("\n[dry-run] Nada cambiado. Reejecuta con --apply para crear los índices.")
        return

    # No destructivos
    sessions.create_index("session_id", name="ix_session_id")
    backup.create_index("timestamp", name="ix_timestamp")
    print("\n✔ Índices session_id y timestamp creados.")

    if args.ttl_days is not None:
        backup.create_index("timestamp", name="ttl_timestamp",
                            expireAfterSeconds=args.ttl_days * 86400)
        print(f"✔ Índice TTL creado (expireAfterSeconds={args.ttl_days * 86400}).")
    else:
        print("ℹ  Sin --ttl-days: no se creó índice TTL (no se borra nada).")

    print("\nÍndices actuales en message_backup:")
    for name, spec in backup.index_information().items():
        print(f"  {name}: {spec.get('key')}  ttl={spec.get('expireAfterSeconds')}")


if __name__ == "__main__":
    main()
