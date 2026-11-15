"""
Auto ETL tanpa browser: pantau NOON_REPORT_COPY, jalankan ETL incremental otomatis
setiap kali ada data baru / data yang diubah.

    python -m scripts.auto_etl                 # pantau terus (interval dari secrets.toml [auto_etl])
    python -m scripts.auto_etl --interval 30   # cek tiap 30 detik
    python -m scripts.auto_etl --once          # cek 1x lalu keluar (cocok untuk Task Scheduler)

Hentikan dengan Ctrl+C.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time

from config.settings import get_analytics_settings, get_auto_etl_settings, get_db_settings


def _log(msg: str) -> None:
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Marine BI Analytics - Auto ETL watcher")
    ap.add_argument("--interval", type=int, default=get_auto_etl_settings().interval_seconds,
                    help="jeda antar pengecekan (detik)")
    ap.add_argument("--once", action="store_true", help="cek satu kali lalu keluar")
    args = ap.parse_args()

    from core.database import make_engine
    from etl.auto import AutoETLWatcher

    db, an = get_db_settings(), get_analytics_settings()
    watcher = AutoETLWatcher(make_engine(db), db, an, args.interval, log=_log)

    if args.once:
        chk = watcher.tick()
        if chk is not None and chk.watermark is None:
            _log("No watermark yet - run a Full reload first (ETL Pipeline page or scripts.run_etl --mode full).")
        elif chk is not None and chk.new_rows == 0:
            _log("No new data.")
        return 1 if watcher.last_error else 0

    _log(f"Watching [{db.source_schema}].[{db.source_noon_table}] every {watcher.interval}s - Ctrl+C to stop")
    try:
        while True:
            chk = watcher.tick()
            if chk is not None and chk.watermark is None:
                _log("No watermark yet - run a Full reload first. Waiting...")
            time.sleep(watcher.interval)
    except KeyboardInterrupt:
        _log("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
