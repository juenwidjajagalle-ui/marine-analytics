"""
Lapisan akses data untuk dashboard (membaca star schema `dw`), dengan cache Streamlit.
Semua query memakai parameter (aman dari SQL injection).
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass

import pandas as pd
import streamlit as st
from sqlalchemy import text

from config.settings import get_app_settings, get_db_settings
from core import schema
from core.database import make_engine

ALL = "__ALL__"
SPEED_CHOICES = ("SPEED_OVER_GROUND", "GEN_AVERAGE_SPEED", "AVG_SPEED")
_TTL = get_app_settings().cache_ttl_seconds


@st.cache_resource(show_spinner=False)
def get_engine():
    return make_engine(get_db_settings())


@st.cache_resource(show_spinner=False)
def get_auto_etl():
    """Satu watcher Auto ETL untuk seluruh server Streamlit (dibuat sekali, dipakai semua sesi).
    Return None bila dimatikan di secrets.toml ([auto_etl] enabled = false)."""
    from config.settings import get_analytics_settings, get_auto_etl_settings
    from etl.auto import AutoETLWatcher

    cfg = get_auto_etl_settings()
    if not cfg.enabled:
        return None
    return AutoETLWatcher(get_engine(), get_db_settings(), get_analytics_settings(),
                          cfg.interval_seconds, log=lambda m: print(f"[auto-etl] {m}", flush=True)).start()


def speed_col() -> str:
    """Kolom kecepatan operasional (whitelist, aman dipakai di SQL)."""
    from config.settings import get_analytics_settings
    c = get_analytics_settings().speed_column.upper()
    return c if c in SPEED_CHOICES else "SPEED_OVER_GROUND"


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Kolom turunan untuk dashboard (bukan bagian rumus anomali)."""
    if df.empty:
        return df
    sc = speed_col()
    if sc in df.columns:
        df["OPERATIONAL_SPEED"] = df[sc]
    if {"ME_MFO_CONS", "ME_MDO_CONS"} <= set(df.columns):
        both_null = df["ME_MFO_CONS"].isna() & df["ME_MDO_CONS"].isna()
        df["ME_TOTAL_CONS"] = (df["ME_MFO_CONS"].fillna(0) + df["ME_MDO_CONS"].fillna(0)).mask(both_null)
    return df


def _dw() -> str:
    return get_db_settings().dw_schema


def _read(sql: str, params: dict | None = None) -> pd.DataFrame:
    t0 = time.perf_counter()
    with get_engine().connect() as conn:
        df = pd.read_sql(text(sql), conn, params=params or {})
    took = time.perf_counter() - t0
    if took > 0.5:  # tampil di jendela PowerShell untuk membantu mencari bagian yang lambat
        first = " ".join(sql.split())[:90]
        print(f"[SQL {took:5.2f}s | {len(df):>6} rows] {first}", flush=True)
    return df


@dataclass(frozen=True)
class Filters:
    vessel: str = ALL
    voyage: str = ALL
    start: dt.date | None = None
    end: dt.date | None = None

    def where(self, alias: str = "f") -> tuple[str, dict]:
        cond, p = [], {}
        if self.start:
            cond.append(f"{alias}.REPORT_DATE >= :start")
            p["start"] = dt.datetime.combine(self.start, dt.time.min)
        if self.end:
            cond.append(f"{alias}.REPORT_DATE < :end")
            p["end"] = dt.datetime.combine(self.end + dt.timedelta(days=1), dt.time.min)
        if self.vessel != ALL:
            cond.append(f"{alias}.Vessel_Key = :vessel")
            p["vessel"] = self.vessel
        if self.voyage != ALL:
            cond.append(f"{alias}.Voyage_Key = :voyage")
            p["voyage"] = self.voyage
        return (" WHERE " + " AND ".join(cond)) if cond else "", p


# ------------------------------------------------------------------ status --
@st.cache_data(ttl=300, show_spinner="Connecting to the database…")
def warehouse_ready() -> tuple[bool, str]:
    try:
        # Cek keberadaan tabel dulu (SQL Server mengompilasi subquery walau di dalam CASE)
        exists = _read(f"SELECT OBJECT_ID(N'[{_dw()}].[FACT_NOON_REPORT]', N'U') AS oid")
        if pd.isna(exists.iloc[0, 0]):
            return False, "The star schema has not been created yet. Run the ETL from the ETL Pipeline page."
        df = _read(f"SELECT COUNT_BIG(*) AS n FROM [{_dw()}].[FACT_NOON_REPORT]")
        n = int(df.iloc[0, 0])
        if n == 0:
            return False, "The fact table is empty. Run a Full load from the ETL Pipeline page."
        return True, f"{n:,} noon reports available."
    except Exception as exc:  # noqa: BLE001
        return False, f"Cannot connect to the database: {exc}"


# ----------------------------------------------------------------- options --
@st.cache_data(ttl=_TTL, show_spinner="Loading filters…")
def filter_options() -> dict:
    dw = _dw()
    vessels = _read(f"""
        SELECT v.Vessel_Key, v.NAME FROM [{dw}].[DIM_VESSEL] v
        WHERE EXISTS (SELECT 1 FROM [{dw}].[FACT_NOON_REPORT] f WHERE f.Vessel_Key = v.Vessel_Key)
        ORDER BY v.NAME""")
    voyages = _read(f"""
        SELECT Voyage_Key, Vessel_Key, Voyage_Label, First_Report_Date, Last_Report_Date, Report_Count
        FROM [{dw}].[DIM_VOYAGE] WHERE Report_Count > 0
        ORDER BY First_Report_Date DESC""")
    rng = _read(f"SELECT MIN(REPORT_DATE) AS mn, MAX(REPORT_DATE) AS mx FROM [{dw}].[FACT_NOON_REPORT]")
    mn, mx = rng.iloc[0]["mn"], rng.iloc[0]["mx"]
    return {
        "vessels": vessels,
        "voyages": voyages,
        "min_date": pd.Timestamp(mn).date() if pd.notna(mn) else dt.date.today(),
        "max_date": pd.Timestamp(mx).date() if pd.notna(mx) else dt.date.today(),
    }


# ------------------------------------------------------------ noon reports --
NOON_COLS = [
    "Noon_Report_Key", "REPORT_DATE", "Voyage_Key", "Vessel_Key", "NEXT_PORT", "AVG_SPEED", "RPM",
    "SLIP", "ME_MFO_CONS", "ME_MDO_CONS", "AE_MFO_CONS", "AE_MDO_CONS", "MFO_TOTAL_CONS",
    "SPEED_OVER_GROUND", "GEN_AVERAGE_SPEED", "DIST_OVER_GROUND", "DISTANCE_TO_GO", "ROB_MFO", "ROB_MDO", "ROB_FW",
    "WIND_DIRECTION", "FORCE", "SEA_COND", "AIR_TEMPERATURE", "SEA_TEMPERATURE", "SWELL_HEIGHT",
    "LATITUDE", "LONGITUDE", *schema.EGT_COLS,
    "MEDIAN_EGT", "VALID_CYLINDERS", "MAX_ABS_MODIFIED_Z", "ANOMALY_CYLINDERS", "Anomaly_Status",
]


@st.cache_data(ttl=_TTL, show_spinner="Loading noon reports…")
def noon_reports(flt: Filters, all_columns: bool = False) -> pd.DataFrame:
    dw = _dw()
    where, p = flt.where("f")
    cols = "f.*" if all_columns else ", ".join(f"f.[{c}]" for c in NOON_COLS)
    df = _read(f"""
        SELECT {cols}, v.NAME AS VESSEL_NAME, vo.Voyage_Label
        FROM [{dw}].[FACT_NOON_REPORT] f
        LEFT JOIN [{dw}].[DIM_VESSEL] v ON v.Vessel_Key = f.Vessel_Key
        LEFT JOIN [{dw}].[DIM_VOYAGE] vo ON vo.Voyage_Key = f.Voyage_Key
        {where}
        ORDER BY f.REPORT_DATE, f.Vessel_Key""", p)
    if not df.empty:
        df["REPORT_DATE"] = pd.to_datetime(df["REPORT_DATE"])
        df["Voyage_Label"] = df["Voyage_Label"].fillna("—")
    return add_derived(df)


@st.cache_data(ttl=_TTL, show_spinner="Loading anomaly results…")
def cylinder_anomalies(flt: Filters) -> pd.DataFrame:
    dw = _dw()
    where, p = flt.where("c")
    df = _read(f"""
        SELECT c.*, v.NAME AS VESSEL_NAME, vo.Voyage_Label
        FROM [{dw}].[FACT_CYLINDER_ANOMALY] c
        LEFT JOIN [{dw}].[DIM_VESSEL] v ON v.Vessel_Key = c.Vessel_Key
        LEFT JOIN [{dw}].[DIM_VOYAGE] vo ON vo.Voyage_Key = c.Voyage_Key
        {where}
        ORDER BY c.REPORT_DATE, c.Vessel_Key, c.Cylinder_No""", p)
    if not df.empty:
        df["REPORT_DATE"] = pd.to_datetime(df["REPORT_DATE"])
        df["Voyage_Label"] = df["Voyage_Label"].fillna("—")
    return df


@st.cache_data(ttl=_TTL, show_spinner=False)
def cylinder_for_report(noon_report_key: str) -> pd.DataFrame:
    return _read(f"""
        SELECT * FROM [{_dw()}].[FACT_CYLINDER_ANOMALY]
        WHERE Noon_Report_Key = :k ORDER BY Cylinder_No""", {"k": noon_report_key})


# ---------------------------------------------------------------- overview --
@st.cache_data(ttl=_TTL, show_spinner=False)
def monthly_summary(flt: Filters) -> pd.DataFrame:
    dw = _dw()
    where, p = flt.where("f")
    return _read(f"""
        SELECT d.Year_Month,
               COUNT(*) AS Reports,
               SUM(CASE WHEN f.Anomaly_Status = 'ANOMALY' THEN 1 ELSE 0 END) AS Anomaly_Reports,
               AVG(NULLIF(f.[{speed_col()}], 0)) AS Avg_Speed,
               SUM(ISNULL(f.ME_MFO_CONS, 0) + ISNULL(f.ME_MDO_CONS, 0)) AS ME_Cons
        FROM [{dw}].[FACT_NOON_REPORT] f
        JOIN [{dw}].[DIM_DATE] d ON d.Date_Key = f.Date_Key
        {where}
        GROUP BY d.Year_Month ORDER BY d.Year_Month""", p)


@st.cache_data(ttl=_TTL, show_spinner=False)
def vessel_summary(flt: Filters) -> pd.DataFrame:
    dw = _dw()
    where, p = flt.where("c")
    return _read(f"""
        SELECT c.Vessel_Key, MAX(v.NAME) AS NAME,
               SUM(CASE WHEN c.ANOMALY_STATUS = 'ANOMALY' THEN 1 ELSE 0 END) AS Anomalies,
               SUM(CASE WHEN c.ANOMALY_STATUS <> 'DATA_NOT_VALID' THEN 1 ELSE 0 END) AS Calculable,
               COUNT(DISTINCT c.Noon_Report_Key) AS Reports
        FROM [{dw}].[FACT_CYLINDER_ANOMALY] c
        LEFT JOIN [{dw}].[DIM_VESSEL] v ON v.Vessel_Key = c.Vessel_Key
        {where}
        GROUP BY c.Vessel_Key ORDER BY Anomalies DESC""", p)


@st.cache_data(ttl=_TTL, show_spinner="Loading fuel consumption history…")
def fuel_monthly(vessel: str = ALL) -> pd.DataFrame:
    """Rata-rata konsumsi BBM main engine (ME_MFO_CONS + ME_MDO_CONS) per laporan, per bulan.
    Hanya laporan dengan RPM > 0 dan konsumsi di rentang wajar (0 < x <= fuel_valid_max)."""
    from config.settings import get_analytics_settings
    max_cons = float(get_analytics_settings().fuel_valid_max)
    dw = _dw()
    p: dict = {"mx": max_cons}
    vessel_sql = ""
    if vessel != ALL:
        vessel_sql = " AND f.Vessel_Key = :vessel"
        p["vessel"] = vessel
    return _read(f"""
        WITH x AS (
            SELECT d.Year_Month, f.RPM, f.REPORT_DATE,
                   CASE WHEN f.ME_MFO_CONS IS NULL AND f.ME_MDO_CONS IS NULL THEN NULL
                        ELSE ISNULL(f.ME_MFO_CONS, 0) + ISNULL(f.ME_MDO_CONS, 0) END AS ME_TOTAL
            FROM [{dw}].[FACT_NOON_REPORT] f
            JOIN [{dw}].[DIM_DATE] d ON d.Date_Key = f.Date_Key
            WHERE 1 = 1 {vessel_sql}
        )
        SELECT Year_Month,
               COUNT(*)                                                         AS All_Reports,
               SUM(CASE WHEN RPM > 0 AND ME_TOTAL > 0 AND ME_TOTAL <= :mx THEN 1 ELSE 0 END) AS Valid_Reports,
               SUM(CASE WHEN RPM > 0 AND ME_TOTAL > :mx THEN 1 ELSE 0 END)       AS Outlier_Reports,
               AVG(CASE WHEN RPM > 0 AND ME_TOTAL > 0 AND ME_TOTAL <= :mx THEN ME_TOTAL END) AS Avg_Cons,
               SUM(CASE WHEN RPM > 0 AND ME_TOTAL > 0 AND ME_TOTAL <= :mx THEN ME_TOTAL ELSE 0 END) AS Total_Cons,
               MAX(REPORT_DATE)                                                  AS Last_Report
        FROM x
        GROUP BY Year_Month
        ORDER BY Year_Month""", p)


@st.cache_data(ttl=30, show_spinner=False)
def etl_runs(limit: int = 20) -> pd.DataFrame:
    try:
        return _read(f"SELECT TOP ({int(limit)}) * FROM [{_dw()}].[ETL_RUN_LOG] ORDER BY Run_Id DESC")
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def clear_caches() -> None:
    st.cache_data.clear()