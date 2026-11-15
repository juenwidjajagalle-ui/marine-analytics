"""LOAD — menulis hasil transformasi ke star schema (schema `dw`)."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine

from core import schema

CHUNK = 1000


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    """Ganti NaN/NaT/pd.NA -> None agar pyodbc menulis NULL dengan benar."""
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].astype(object).where(out[c].notna(), None)
        elif out[c].dtype == object or pd.api.types.is_string_dtype(out[c]):
            out[c] = out[c].astype(object).where(out[c].notna(), None)
    return out


def insert_df(conn: Connection, df: pd.DataFrame, table: str, dw: str) -> int:
    if df.empty:
        return 0
    _prep(df).to_sql(table, conn, schema=dw, if_exists="append", index=False, chunksize=CHUNK)
    return len(df)


def ensure_warehouse(engine: Engine, dw: str) -> None:
    with engine.begin() as conn:
        for stmt in schema.warehouse_ddl(dw):
            conn.execute(text(stmt))


def reset_staging(conn: Connection, dw: str) -> None:
    for stmt in schema.staging_ddl(dw):
        conn.execute(text(stmt))


def drop_staging(conn: Connection, dw: str) -> None:
    for t in ("STG_NOON_REPORT", "STG_CHANGED_KEYS", "STG_THERMAL_SUMMARY"):
        conn.execute(text(f"IF OBJECT_ID(N'[{dw}].[{t}]', N'U') IS NOT NULL DROP TABLE [{dw}].[{t}];"))


# ---------------------------------------------------------------- dims ------
def load_dim_vessel(conn: Connection, df: pd.DataFrame, dw: str) -> int:
    conn.execute(text(f"DELETE FROM [{dw}].[DIM_VESSEL];"))
    return insert_df(conn, df, "DIM_VESSEL", dw)


def load_dim_voyage(conn: Connection, df: pd.DataFrame, dw: str) -> int:
    conn.execute(text(f"DELETE FROM [{dw}].[DIM_VOYAGE];"))
    return insert_df(conn, df.drop_duplicates("Voyage_Key", keep="first"), "DIM_VOYAGE", dw)


def refresh_voyage_attributes(conn: Connection, dw: str) -> None:
    conn.execute(text(f"""
        UPDATE v SET
            v.First_Report_Date = a.first_dt,
            v.Last_Report_Date  = a.last_dt,
            v.Report_Count      = ISNULL(a.cnt, 0)
        FROM [{dw}].[DIM_VOYAGE] v
        LEFT JOIN (
            SELECT Voyage_Key, MIN(REPORT_DATE) first_dt, MAX(REPORT_DATE) last_dt, COUNT(*) cnt
            FROM [{dw}].[FACT_NOON_REPORT] GROUP BY Voyage_Key
        ) a ON a.Voyage_Key = v.Voyage_Key;
    """))
    # Label voyage yang mudah dibaca (bukan GUID):
    #   ada nomor voyage  -> "SILVER TIGER · Voy 2401"
    #   tidak ada         -> "SILVER TIGER · 12 Nov 2023 – 20 Jan 2024"
    conn.execute(text(f"""
        UPDATE v SET v.Voyage_Label = LEFT(
            ISNULL(NULLIF(ve.NAME, N''), v.Vessel_Key) + N' · ' +
            CASE
                WHEN NULLIF(LTRIM(RTRIM(v.Voyage_No)), N'') IS NOT NULL THEN N'Voy ' + LTRIM(RTRIM(v.Voyage_No))
                WHEN v.First_Report_Date IS NOT NULL THEN
                    FORMAT(v.First_Report_Date, 'dd MMM yyyy', 'en-US') + N' – ' +
                    FORMAT(v.Last_Report_Date,  'dd MMM yyyy', 'en-US')
                ELSE N'Voyage ' + LEFT(v.Voyage_Key, 8)
            END, 100)
        FROM [{dw}].[DIM_VOYAGE] v
        LEFT JOIN [{dw}].[DIM_VESSEL] ve ON ve.Vessel_Key = v.Vessel_Key;
    """))


def rebuild_dim_date(conn: Connection, dw: str, build_fn) -> int:
    row = conn.execute(text(
        f"SELECT MIN(REPORT_DATE), MAX(REPORT_DATE) FROM [{dw}].[FACT_NOON_REPORT]")).one()
    conn.execute(text(f"DELETE FROM [{dw}].[DIM_DATE];"))
    if row[0] is None:
        return 0
    dim = build_fn(pd.Timestamp(row[0]), pd.Timestamp(row[1]))
    return insert_df(conn, dim, "DIM_DATE", dw)


# ---------------------------------------------------------------- fact ------
def load_fact_full(conn: Connection, fact: pd.DataFrame, dw: str) -> int:
    conn.execute(text(f"TRUNCATE TABLE [{dw}].[FACT_CYLINDER_ANOMALY];"))
    conn.execute(text(f"TRUNCATE TABLE [{dw}].[FACT_NOON_REPORT];"))
    return insert_df(conn, fact, "FACT_NOON_REPORT", dw)


def load_fact_incremental(conn: Connection, fact: pd.DataFrame, changed_keys: list[str],
                          dw: str) -> tuple[int, int, set[str]]:
    """Delete-then-insert via staging: baris yang berubah dihapus dulu lalu dimasukkan versi baru.
    Baris yang kini non-aktif/diarsipkan ikut terhapus dan tidak dimasukkan lagi.

    Return (rows_inserted, rows_deleted, vessel yang terdampak)."""
    if not changed_keys:
        return 0, 0, set()
    insert_df(conn, pd.DataFrame({"Noon_Report_Key": changed_keys}), "STG_CHANGED_KEYS", dw)
    insert_df(conn, fact, "STG_NOON_REPORT", dw)
    old_vessels = conn.execute(text(f"""
        SELECT DISTINCT f.Vessel_Key FROM [{dw}].[FACT_NOON_REPORT] f
        JOIN [{dw}].[STG_CHANGED_KEYS] k ON k.Noon_Report_Key = f.Noon_Report_Key;""")).scalars().all()
    conn.execute(text(f"""
        DELETE c FROM [{dw}].[FACT_CYLINDER_ANOMALY] c
        JOIN [{dw}].[STG_CHANGED_KEYS] k ON k.Noon_Report_Key = c.Noon_Report_Key;"""))
    removed = conn.execute(text(f"""
        DELETE f FROM [{dw}].[FACT_NOON_REPORT] f
        JOIN [{dw}].[STG_CHANGED_KEYS] k ON k.Noon_Report_Key = f.Noon_Report_Key;""")).rowcount
    cols = ", ".join(f"[{c}]" for c in schema.FACT_LOAD_COLUMNS)
    conn.execute(text(f"INSERT INTO [{dw}].[FACT_NOON_REPORT] ({cols}) "
                      f"SELECT {cols} FROM [{dw}].[STG_NOON_REPORT];"))
    affected = set(old_vessels) | set(fact["Vessel_Key"].dropna())
    return len(fact), int(removed or 0), affected


# ------------------------------------------------------------- thermal ------
def read_egt_for_vessels(conn: Connection, dw: str, vessels: list[str] | None) -> pd.DataFrame:
    cols = ", ".join(["Noon_Report_Key", "Vessel_Key", "Voyage_Key", "Date_Key", "REPORT_DATE", "RPM",
                      *schema.EGT_COLS])
    sql = f"SELECT {cols} FROM [{dw}].[FACT_NOON_REPORT]"
    if vessels is None:
        return pd.read_sql(text(sql), conn)
    if not vessels:
        return pd.DataFrame()
    stmt = text(sql + " WHERE Vessel_Key IN :v").bindparams(bindparam("v", expanding=True))
    return pd.read_sql(stmt, conn, params={"v": vessels})


def load_thermal(conn: Connection, cyl: pd.DataFrame, summary: pd.DataFrame,
                 vessels: list[str] | None, dw: str) -> int:
    if vessels is None:
        conn.execute(text(f"TRUNCATE TABLE [{dw}].[FACT_CYLINDER_ANOMALY];"))
    elif vessels:
        conn.execute(text(f"DELETE FROM [{dw}].[FACT_CYLINDER_ANOMALY] WHERE Vessel_Key IN :v")
                     .bindparams(bindparam("v", expanding=True)), {"v": vessels})
    n = insert_df(conn, cyl, "FACT_CYLINDER_ANOMALY", dw)
    insert_df(conn, summary, "STG_THERMAL_SUMMARY", dw)
    conn.execute(text(f"""
        UPDATE f SET
            f.MEDIAN_EGT = s.MEDIAN_EGT, f.VALID_CYLINDERS = s.VALID_CYLINDERS,
            f.MAX_ABS_MODIFIED_Z = s.MAX_ABS_MODIFIED_Z, f.ANOMALY_CYLINDERS = s.ANOMALY_CYLINDERS,
            f.Anomaly_Status = s.Anomaly_Status
        FROM [{dw}].[FACT_NOON_REPORT] f
        JOIN [{dw}].[STG_THERMAL_SUMMARY] s ON s.Noon_Report_Key = f.Noon_Report_Key;"""))
    return n


# --------------------------------------------------------- watermark/log ----
WATERMARK_SOURCE = "NOON_REPORT"


def get_watermark(engine: Engine, dw: str) -> dt.datetime | None:
    with engine.connect() as conn:
        row = conn.execute(text(f"SELECT Last_Change_TS FROM [{dw}].[ETL_WATERMARK] "
                                "WHERE Source_Name = :s"), {"s": WATERMARK_SOURCE}).first()
    return row[0] if row else None


def set_watermark(conn: Connection, dw: str, ts) -> None:
    if ts is None or (isinstance(ts, float) and np.isnan(ts)) or pd.isna(ts):
        return
    ts = pd.Timestamp(ts).to_pydatetime()
    conn.execute(text(f"""
        MERGE [{dw}].[ETL_WATERMARK] AS t
        USING (SELECT :s AS Source_Name) AS s ON t.Source_Name = s.Source_Name
        WHEN MATCHED THEN UPDATE SET Last_Change_TS = :ts, Updated_At = SYSDATETIME()
        WHEN NOT MATCHED THEN INSERT (Source_Name, Last_Change_TS, Updated_At)
             VALUES (:s, :ts, SYSDATETIME());"""), {"s": WATERMARK_SOURCE, "ts": ts})


def log_start(engine: Engine, dw: str, mode: str, wm_from) -> int:
    with engine.begin() as conn:
        row = conn.execute(text(f"""
            INSERT INTO [{dw}].[ETL_RUN_LOG] (Started_At, Mode, Status, Watermark_From)
            OUTPUT INSERTED.Run_Id VALUES (SYSDATETIME(), :m, 'RUNNING', :w);"""),
            {"m": mode, "w": wm_from}).one()
    return int(row[0])


def log_finish(engine: Engine, dw: str, run_id: int, status: str, **kw) -> None:
    def clean(v):
        if v is None or v is pd.NaT:
            return None
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, pd.Timestamp):
            return None if pd.isna(v) else v.to_pydatetime()
        return v
    params = {k: clean(v) for k, v in kw.items()}
    params.update(run_id=run_id, status=status)
    with engine.begin() as conn:
        conn.execute(text(f"""
            UPDATE [{dw}].[ETL_RUN_LOG] SET Finished_At = SYSDATETIME(), Status = :status,
                Rows_Extracted = :rows_extracted, Rows_Loaded = :rows_loaded,
                Rows_Removed = :rows_removed, Cylinder_Rows = :cylinder_rows,
                Anomalies = :anomalies, Watermark_To = :watermark_to, Message = :message
            WHERE Run_Id = :run_id;"""), params)