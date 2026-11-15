"""EXTRACT — membaca data mentah dari tabel sumber SQL Server."""
from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.settings import DatabaseSettings

# Timestamp perubahan baris sumber: ambil yang terbaru antara CREATED_DATE & MODIFIED_DATE
CHANGE_TS_EXPR = (
    "CASE WHEN ISNULL(MODIFIED_DATE, '19000101') > ISNULL(CREATED_DATE, '19000101') "
    "THEN MODIFIED_DATE ELSE CREATED_DATE END"
)


def _src(cfg: DatabaseSettings, table: str) -> str:
    hint = " WITH (NOLOCK)" if cfg.use_nolock else ""
    return f"[{cfg.source_schema}].[{table}]{hint}"


def extract_vessels(engine: Engine, cfg: DatabaseSettings) -> pd.DataFrame:
    sql = (f"SELECT CODE_VESSEL, NAME, SPEED, MFO_AT_PORT, MFO_AT_SEA, MDO_AT_PORT, "
           f"MDO_AT_SEA, FW FROM {_src(cfg, cfg.source_vessel_table)}")
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def extract_voyages(engine: Engine, cfg: DatabaseSettings) -> pd.DataFrame:
    sql = f"SELECT ID_VOYAGE, FCODE_VESSEL FROM {_src(cfg, cfg.source_voyage_table)}"
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def count_changes_since(engine: Engine, cfg: DatabaseSettings,
                        since: dt.datetime) -> tuple[int, dt.datetime | None]:
    """Cek ringan (tanpa menarik data): berapa baris noon report yang dibuat/diubah
    setelah `since`, dan kapan perubahan terakhirnya."""
    sql = (f"SELECT COUNT_BIG(*) AS n, MAX({CHANGE_TS_EXPR}) AS latest "
           f"FROM {_src(cfg, cfg.source_noon_table)} WHERE {CHANGE_TS_EXPR} > :since")
    with engine.connect() as conn:
        n, latest = conn.execute(text(sql), {"since": since}).one()
    return int(n or 0), latest


def extract_noon_reports(engine: Engine, cfg: DatabaseSettings,
                         since: dt.datetime | None = None,
                         chunksize: int = 50_000) -> pd.DataFrame:
    """Ambil noon report. `since`=None -> semua baris (full load);
    selain itu hanya baris yang dibuat/diubah setelah watermark (incremental)."""
    sql = f"SELECT *, {CHANGE_TS_EXPR} AS _CHANGE_TS FROM {_src(cfg, cfg.source_noon_table)}"
    params = {}
    if since is not None:
        sql += f" WHERE {CHANGE_TS_EXPR} > :since"
        params["since"] = since
    chunks = []
    with engine.connect() as conn:
        for chunk in pd.read_sql(text(sql), conn, params=params, chunksize=chunksize):
            chunks.append(chunk)
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)
