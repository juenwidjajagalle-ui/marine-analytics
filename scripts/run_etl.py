"""
Jalankan ETL tanpa browser (untuk Windows Task Scheduler / cron).

    cd marine_bi
    python -m scripts.run_etl --mode incremental
    python -m scripts.run_etl --mode full
    python -m scripts.run_etl --print-ddl > sql/create_warehouse.sql
"""
from __future__ import annotations

import argparse
import sys

from config.settings import get_analytics_settings, get_db_settings
from core import schema


def main() -> int:
    ap = argparse.ArgumentParser(description="Marine BI Analytics ETL")
    ap.add_argument("--mode", choices=["incremental", "full"], default="incremental")
    ap.add_argument("--print-ddl", action="store_true", help="Cetak DDL star schema lalu keluar")
    args = ap.parse_args()

    db, an = get_db_settings(), get_analytics_settings()
    if args.print_ddl:
        print(schema.ddl_script(db.dw_schema, db.database))
        return 0

    from core.database import make_engine
    from etl.pipeline import run_etl

    engine = make_engine(db)
    res = run_etl(engine, db, an, mode=args.mode,
                  progress=lambda msg, pct: print(f"[{pct:5.0%}] {msg}", flush=True))
    print(f"\nStatus : {res.status}  ({res.duration_s}s)\n{res.message}")
    for k, v in res.dq.items():
        print(f"  - {k}: {v}")
    return 0 if res.status in ("SUCCESS", "SKIPPED") else 1


if __name__ == "__main__":
    sys.exit(main())
