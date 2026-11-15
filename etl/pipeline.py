"""
Orkestrasi ETL end-to-end.

  EXTRACT   dbo.vessels, dbo.V_Voyages, dbo.NOON_REPORT_COPY
  TRANSFORM pembersihan, konversi tipe, surrogate/natural keys, validasi EGT
  LOAD      dw.DIM_VESSEL, dw.DIM_VOYAGE, dw.FACT_NOON_REPORT
  ANALYZE   Median EGT -> Deviation -> Baseline -> MAD -> Modified Z -> Status
            -> dw.FACT_CYLINDER_ANOMALY + ringkasan di FACT_NOON_REPORT
  FINALIZE  dw.DIM_DATE, atribut DIM_VOYAGE, watermark, log

Mode:
  full         : kosongkan fact lalu muat ulang semuanya (disarankan saat pertama kali)
  incremental  : hanya baris yang CREATED/MODIFIED setelah watermark terakhir;
                 anomali dihitung ulang untuk kapal yang terdampak saja
"""
from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from analytics.thermal import ANOMALY, ThermalParams, compute_thermal
from config.settings import AnalyticsSettings, DatabaseSettings
from etl import extract, load, transform

_RUN_LOCK = threading.Lock()          # kunci di dalam 1 proses (Streamlit + watcher)
_DB_LOCK_NAME = "marine_bi_etl"       # kunci antar proses (Streamlit, scripts.run_etl, scripts.auto_etl)

ProgressFn = Callable[[str, float], None]


def _acquire_db_lock(engine: Engine):
    """Ambil application lock SQL Server (sp_getapplock) agar ETL tidak jalan ganda dari
    proses lain. Return (koneksi pemegang lock | None, berhasil?). Jika fitur ini gagal
    dipakai (mis. izin), ETL tetap jalan dengan kunci lokal saja."""
    conn = None
    try:
        conn = engine.connect()
        code = conn.execute(text(
            "SET NOCOUNT ON; DECLARE @r int; "
            "EXEC @r = sp_getapplock @Resource = :res, @LockMode = 'Exclusive', "
            "@LockOwner = 'Session', @LockTimeout = 0; SELECT @r;"), {"res": _DB_LOCK_NAME}).scalar()
        if code is not None and int(code) >= 0:
            return conn, True
        conn.close()
        return None, False
    except Exception:  # noqa: BLE001
        if conn is not None:
            conn.invalidate()
        return None, True


def _release_db_lock(conn) -> None:
    if conn is None:
        return
    try:
        conn.execute(text("EXEC sp_releaseapplock @Resource = :res, @LockOwner = 'Session';"),
                     {"res": _DB_LOCK_NAME})
        conn.commit()
        conn.close()
    except Exception:  # noqa: BLE001
        conn.invalidate()      # buang koneksi -> sesi ditutup -> lock pasti lepas


@dataclass
class ETLResult:
    mode: str
    status: str = "RUNNING"
    run_id: int | None = None
    rows_extracted: int = 0
    rows_loaded: int = 0
    rows_removed: int = 0
    cylinder_rows: int = 0
    anomalies: int = 0
    vessels_recomputed: int = 0
    watermark_from: object = None
    watermark_to: object = None
    duration_s: float = 0.0
    dq: dict = field(default_factory=dict)
    message: str = ""
    steps: list[str] = field(default_factory=list)


def run_etl(engine: Engine, db: DatabaseSettings, an: AnalyticsSettings,
            mode: str = "incremental", progress: ProgressFn | None = None) -> ETLResult:
    mode = mode.lower()
    if mode not in {"full", "incremental"}:
        raise ValueError("mode must be 'full' or 'incremental'")
    res = ETLResult(mode=mode)
    dw = db.dw_schema

    def step(msg: str, pct: float) -> None:
        res.steps.append(msg)
        if progress:
            progress(msg, pct)

    if not _RUN_LOCK.acquire(blocking=False):
        res.status, res.message = "SKIPPED", "Another ETL run is already in progress."
        return res
    lock_conn, ok = _acquire_db_lock(engine)
    if not ok:
        _RUN_LOCK.release()
        res.status, res.message = "SKIPPED", "Another ETL run is already in progress (other process)."
        return res

    t0 = time.time()
    try:
        step("Ensuring the star schema (dw) exists", 0.03)
        load.ensure_warehouse(engine, dw)

        wm_from = load.get_watermark(engine, dw) if mode == "incremental" else None
        if mode == "incremental" and wm_from is None:
            step("No watermark yet → running a FULL load instead", 0.05)
            mode = res.mode = "full"
        res.watermark_from = wm_from
        res.run_id = load.log_start(engine, dw, mode, wm_from)

        # ---------------- EXTRACT ----------------
        step("Extract: vessel master (vessels)", 0.08)
        vessels_raw = extract.extract_vessels(engine, db)
        step("Extract: voyage (V_Voyages)", 0.12)
        voyages_raw = extract.extract_voyages(engine, db)
        step("Extract: noon report" + (f" (changed since {wm_from})" if wm_from else " (all rows)"), 0.18)
        noon_raw = extract.extract_noon_reports(engine, db, since=wm_from)
        res.rows_extracted = len(noon_raw)

        # ---------------- TRANSFORM ----------------
        step(f"Transform: cleaning {len(noon_raw):,} noon report rows", 0.35)
        dim_vessel = transform.transform_vessels(vessels_raw)
        dim_voyage = transform.transform_voyages(voyages_raw)
        fact, changed_keys, extra_voy, dq = transform.transform_noon_reports(
            noon_raw, dim_voyage, dim_vessel, an)
        if not extra_voy.empty:
            dim_voyage = pd.concat([dim_voyage, extra_voy], ignore_index=True)
        res.dq = dq
        res.watermark_to = dq.get("max_change_ts") if len(noon_raw) else wm_from

        params = ThermalParams.from_settings(an)

        # ---------------- LOAD + ANALYZE (1 transaksi) ----------------
        with engine.begin() as conn:
            load.reset_staging(conn, dw)
            step("Load: DIM_VESSEL & DIM_VOYAGE", 0.45)
            load.load_dim_vessel(conn, dim_vessel, dw)
            load.load_dim_voyage(conn, dim_voyage, dw)

            if mode == "full":
                step(f"Load: FACT_NOON_REPORT (full, {len(fact):,} rows)", 0.55)
                res.rows_loaded = load.load_fact_full(conn, fact, dw)
                vessels_to_compute = None
            else:
                step(f"Load: FACT_NOON_REPORT (incremental, {len(changed_keys):,} changed keys)", 0.55)
                res.rows_loaded, res.rows_removed, affected = load.load_fact_incremental(
                    conn, fact, changed_keys, dw)
                vessels_to_compute = sorted(affected)

            if vessels_to_compute is None or vessels_to_compute:
                step("Analyze: reading EGT history for the baseline", 0.65)
                egt_df = load.read_egt_for_vessels(conn, dw, vessels_to_compute)
                step(f"Analyze: Median EGT → Deviation → MAD → Modified Z ({len(egt_df):,} reports)", 0.75)
                cyl_df, summary_df = compute_thermal(egt_df, params)
                step(f"Load: FACT_CYLINDER_ANOMALY ({len(cyl_df):,} rows)", 0.85)
                res.cylinder_rows = load.load_thermal(conn, cyl_df, summary_df, vessels_to_compute, dw)
                res.anomalies = int((cyl_df["ANOMALY_STATUS"] == ANOMALY).sum()) if len(cyl_df) else 0
                res.vessels_recomputed = int(egt_df["Vessel_Key"].nunique()) if len(egt_df) else 0
            else:
                step("Analyze: no changed data → anomalies not recomputed", 0.85)

            step("Finalize: DIM_DATE, voyage attributes, watermark", 0.93)
            load.rebuild_dim_date(conn, dw, transform.build_date_dim)
            load.refresh_voyage_attributes(conn, dw)
            load.set_watermark(conn, dw, res.watermark_to)
            load.drop_staging(conn, dw)

        res.status = "SUCCESS"
        res.message = (f"{res.rows_loaded:,} reports loaded, {res.cylinder_rows:,} cylinder rows analysed, "
                       f"{res.anomalies:,} anomalies.")
        step("Done", 1.0)
    except Exception as exc:  # noqa: BLE001
        res.status = "FAILED"
        res.message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
        if progress:
            progress(f"FAILED: {type(exc).__name__}: {exc}", 1.0)
    finally:
        res.duration_s = round(time.time() - t0, 1)
        if res.run_id is not None:
            try:
                load.log_finish(engine, dw, res.run_id, res.status,
                                rows_extracted=res.rows_extracted, rows_loaded=res.rows_loaded,
                                rows_removed=res.rows_removed, cylinder_rows=res.cylinder_rows,
                                anomalies=res.anomalies, watermark_to=res.watermark_to,
                                message=res.message[:4000])
            except Exception:  # noqa: BLE001
                pass
        _release_db_lock(lock_conn)
        _RUN_LOCK.release()
    return res
