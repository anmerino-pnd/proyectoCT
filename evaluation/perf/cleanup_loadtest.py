"""
Limpia los datos generados por loadtest.py (sesiones con prefijo LOADTEST_).
Borra de tbl_sessions y tbl_message_backup. Dry-run por defecto; usa --apply.

Uso:
    .venv/Scripts/python.exe evaluation/perf/cleanup_loadtest.py            # dry-run
    .venv/Scripts/python.exe evaluation/perf/cleanup_loadtest.py --apply    # borra
"""
from __future__ import annotations
import argparse

from ct.settings.clients import (
    get_mongo_client,
    mongo_collection_message_backup,
    mongo_collection_sessions,
)

FILT = {"session_id": {"$regex": "^LOADTEST_"}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = get_mongo_client().get_default_database()
    backup = db[mongo_collection_message_backup]
    sessions = db[mongo_collection_sessions]

    nb = backup.count_documents(FILT)
    ns = sessions.count_documents(FILT)
    print(f"LOADTEST_ en message_backup: {nb:,}  | en sessions: {ns:,}")

    if not args.apply:
        print("[dry-run] Nada borrado. Reejecuta con --apply.")
        return

    r1 = backup.delete_many(FILT)
    r2 = sessions.delete_many(FILT)
    print(f"Borrados: message_backup={r1.deleted_count:,}  sessions={r2.deleted_count:,}")


if __name__ == "__main__":
    main()
