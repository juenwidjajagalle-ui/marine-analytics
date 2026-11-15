"""
Koneksi SQL Server (pyodbc + SQLAlchemy).

Connection string SSMS Anda (ADO.NET) diterjemahkan ke format ODBC:
    Data Source=localhost\\SQLEXPRESS;Integrated Security=True;Encrypt=True;
    TrustServerCertificate=True
  ->
    DRIVER={ODBC Driver 17/18 for SQL Server};SERVER=localhost\\SQLEXPRESS;
    DATABASE=COPY_DATA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes
"""
from __future__ import annotations

import urllib.parse
from typing import Iterable

import pandas as pd
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import URL, Engine

from config.settings import DatabaseSettings

PREFERRED_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 13 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
)


PYMSSQL = "pymssql"


def _pymssql_available() -> bool:
    try:
        import pymssql  # noqa: F401
        return True
    except ImportError:
        return False


def detect_driver(preferred: str = "auto") -> str:
    """Nama ODBC driver, atau "pymssql" bila tidak ada ODBC driver
    (mis. di Streamlit Community Cloud / Linux tanpa msodbcsql)."""
    if preferred and preferred.lower() != "auto":
        return PYMSSQL if preferred.lower() == PYMSSQL else preferred
    try:
        import pyodbc
        installed = set(pyodbc.drivers())
    except ImportError:  # libodbc tidak terpasang
        installed = set()
    for name in PREFERRED_DRIVERS:
        if name in installed:
            return name
    if _pymssql_available():
        return PYMSSQL
    raise RuntimeError(
        "Tidak ada ODBC driver SQL Server yang terpasang. Install "
        "'ODBC Driver 18 for SQL Server' dari situs Microsoft, atau `pip install pymssql`. "
        f"Driver terdeteksi: {sorted(installed) or 'tidak ada'}"
    )


def _odbc_quote(value: str) -> str:
    """Bungkus nilai dengan {} agar karakter spesial (; = + ! {}) aman di ODBC."""
    return "{" + str(value).replace("}", "}}") + "}"


def build_odbc_string(cfg: DatabaseSettings) -> str:
    driver = detect_driver(cfg.driver)
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={cfg.server}",
        f"DATABASE={cfg.database}",
        f"Connection Timeout={cfg.timeout}",
        "APP=Marine BI Analytics",
    ]
    if cfg.trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        parts += [f"UID={_odbc_quote(cfg.username)}", f"PWD={_odbc_quote(cfg.password)}"]
    # Driver lama "SQL Server" tidak mendukung opsi Encrypt modern
    if driver != "SQL Server":
        parts.append(f"Encrypt={'yes' if cfg.encrypt else 'no'}")
        parts.append(
            f"TrustServerCertificate={'yes' if cfg.trust_server_certificate else 'no'}"
        )
    return ";".join(parts) + ";"


def _make_pymssql_engine(cfg: DatabaseSettings) -> Engine:
    if cfg.trusted_connection:
        raise RuntimeError("pymssql tidak mendukung Windows Authentication; "
                           "set trusted_connection = false dan isi username/password.")
    host, _, port = cfg.server.partition(",")
    url = URL.create(
        "mssql+pymssql",
        username=cfg.username,
        password=cfg.password,
        host=host.strip(),
        port=int(port) if port.strip() else 1433,
        database=cfg.database,
        query={"charset": "utf8", "tds_version": "7.4"},
    )
    return create_engine(url, pool_pre_ping=True, future=True,
                         connect_args={"login_timeout": cfg.timeout, "appname": "Marine BI Analytics"})


def make_engine(cfg: DatabaseSettings) -> Engine:
    if detect_driver(cfg.driver) == PYMSSQL:
        return _make_pymssql_engine(cfg)
    odbc = build_odbc_string(cfg)
    url = "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(odbc)
    return create_engine(url, fast_executemany=True, pool_pre_ping=True, future=True)


def masked_connection_info(cfg: DatabaseSettings) -> dict:
    try:
        driver = detect_driver(cfg.driver)
    except Exception as exc:  # noqa: BLE001
        driver = f"(error: {exc})"
    return {
        "Server": cfg.server,
        "Database": cfg.database,
        "Driver": driver,
        "Authentication": "Windows (Integrated)" if cfg.trusted_connection else f"SQL ({cfg.username})",
        "Source": f"{cfg.source_schema}.{cfg.source_noon_table}, "
        f"{cfg.source_schema}.{cfg.source_voyage_table}, {cfg.source_schema}.{cfg.source_vessel_table}",
        "Warehouse schema": cfg.dw_schema,
    }


def test_connection(engine: Engine) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT @@SERVERNAME AS server_name, DB_NAME() AS db_name, "
                 "CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(50)) AS version, "
                 "CAST(SERVERPROPERTY('Edition') AS NVARCHAR(100)) AS edition")
        ).mappings().one()
    return dict(row)


def read_sql(engine: Engine, sql: str, params: dict | None = None,
             expanding: Iterable[str] = ()) -> pd.DataFrame:
    """Jalankan SELECT ber-parameter. `expanding` = nama parameter list untuk IN (...)."""
    stmt = text(sql)
    for name in expanding:
        stmt = stmt.bindparams(bindparam(name, expanding=True))
    with engine.connect() as conn:
        return pd.read_sql(stmt, conn, params=params or {})


def execute(engine: Engine, statements: str | list[str], params: dict | None = None) -> None:
    if isinstance(statements, str):
        statements = [statements]
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql), params or {})
