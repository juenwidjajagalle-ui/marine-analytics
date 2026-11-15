"""
Auto ETL — memantau dbo.NOON_REPORT_COPY dan menjalankan ETL *incremental* secara
otomatis begitu ada data baru / data yang diubah.

Cara kerja (polling):
  1. Setiap `interval_seconds` detik, hitung baris sumber yang
     MAX(CREATED_DATE, MODIFIED_DATE) > watermark terakhir  (query ringan, COUNT saja).
  2. Jika jumlahnya > 0  -> jalankan run_etl(mode="incremental").
  3. Jika berhasil, `data_version` dinaikkan -> dashboard Streamlit membersihkan cache
     dan menampilkan data terbaru.

Dipakai oleh:
  * app.py (thread latar belakang selama Streamlit berjalan), dan
  * scripts/auto_etl.py (proses mandiri tanpa browser).
Modul ini tidak bergantung pada Streamlit.
"""
from __future__ import annotations

import datetime as dt
import threading
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.engine import Engine

from config.settings import AnalyticsSettings, DatabaseSettings
from etl import extract, load
from etl.pipeline import ETLResult, ProgressFn, run_etl


@dataclass
class CheckResult:
    watermark: dt.datetime | None
    new_rows: int
    latest_change: dt.datetime | None


def check_new_data(engine: Engine, db: DatabaseSettings) -> CheckResult:
    """Ada data baru di NOON_REPORT_COPY sejak ETL terakhir?
    Jika belum pernah ada ETL (watermark kosong), new_rows = 0: load pertama harus
    Full reload yang dijalankan manual dari halaman ETL Pipeline."""
    wm = load.get_watermark(engine, db.dw_schema)
    if wm is None:
        return CheckResult(None, 0, None)
    n, latest = extract.count_changes_since(engine, db, wm)
    return CheckResult(wm, n, latest)


def run_if_new_data(engine: Engine, db: DatabaseSettings, an: AnalyticsSettings,
                    progress: ProgressFn | None = None) -> tuple[CheckResult, ETLResult | None]:
    chk = check_new_data(engine, db)
    if chk.new_rows == 0:
        return chk, None
    return chk, run_etl(engine, db, an, mode="incremental", progress=progress)


def _now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


class AutoETLWatcher:
    """Thread latar belakang yang menjalankan pengecekan secara berkala."""

    def __init__(self, engine: Engine, db: DatabaseSettings, an: AnalyticsSettings,
                 interval_seconds: int = 60, log: Callable[[str], None] | None = None):
        self.engine, self.db, self.an = engine, db, an
        self.interval = max(10, int(interval_seconds))
        self._log = log or (lambda msg: None)
        self._stop = threading.Event()
        self._tick_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        # --- status (dibaca oleh UI) ---
        self.data_version = 0                    # naik setiap auto ETL berhasil
        self.last_check: dt.datetime | None = None
        self.last_check_new_rows = 0
        self.last_error: str | None = None
        self.last_run_at: dt.datetime | None = None
        self.last_run: ETLResult | None = None
        self.total_runs = 0

    # ------------------------------------------------------------------ API --
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> "AutoETLWatcher":
        if not self.running:
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="auto-etl", daemon=True)
            self._thread.start()
            self._log(f"Auto ETL started (check every {self.interval}s)")
        return self

    def stop(self) -> None:
        self._stop.set()

    def tick(self) -> CheckResult | None:
        """Satu kali pengecekan (+ ETL bila perlu). Aman dipanggil dari UI ('Check now')."""
        with self._tick_lock:
            try:
                chk = check_new_data(self.engine, self.db)
                self.last_check, self.last_check_new_rows, self.last_error = _now(), chk.new_rows, None
                if chk.new_rows == 0:
                    return chk
                self._log(f"{chk.new_rows:,} new/changed noon report row(s) since {chk.watermark} "
                          "-> running incremental ETL")
                res = run_etl(self.engine, self.db, self.an, mode="incremental")
                self.last_run, self.last_run_at = res, _now()
                if res.status == "SUCCESS":
                    self.total_runs += 1
                    self.data_version += 1
                    self.last_check_new_rows = 0
                elif res.status == "FAILED":
                    self.last_error = res.message.splitlines()[0]
                self._log(f"Auto ETL {res.status} ({res.duration_s}s): {res.message.splitlines()[0]}")
                return chk
            except Exception as exc:  # noqa: BLE001  (mis. DB mati sebentar -> coba lagi nanti)
                self.last_check, self.last_error = _now(), f"{type(exc).__name__}: {exc}"
                self._log(f"Auto ETL check failed: {self.last_error}")
                return None

    # ------------------------------------------------------------- internal --
    def _loop(self) -> None:
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self.interval)
