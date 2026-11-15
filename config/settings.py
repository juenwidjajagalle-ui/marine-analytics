"""
Konfigurasi terpusat aplikasi Marine BI Analytics.

Urutan sumber konfigurasi (yang pertama ditemukan dipakai):
  1. Environment variable, mis. DATABASE_SERVER, DATABASE_DATABASE
  2. File .streamlit/secrets.toml  ([database] dan [analytics])
  3. Nilai default di file ini

Modul ini sengaja TIDAK bergantung pada Streamlit, supaya bisa dipakai juga
oleh script ETL terjadwal (scripts/run_etl.py) di Windows Task Scheduler.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_FILE = PROJECT_ROOT / ".streamlit" / "secrets.toml"


def _load_toml() -> dict:
    if not SECRETS_FILE.exists():
        return {}
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover
        try:
            import tomli as tomllib  # type: ignore
        except ModuleNotFoundError:
            return {}
    with open(SECRETS_FILE, "rb") as fh:
        return tomllib.load(fh)


_TOML = _load_toml()


def _get(section: str, key: str, default):
    env_val = os.getenv(f"{section}_{key}".upper())
    if env_val is not None:
        raw = env_val
    else:
        raw = _TOML.get(section, {}).get(key, default)
    # konversi tipe mengikuti tipe default
    if isinstance(default, bool) and isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(default, int) and not isinstance(default, bool) and isinstance(raw, str):
        return int(raw)
    if isinstance(default, float) and isinstance(raw, str):
        return float(raw)
    return raw


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DatabaseSettings:
    server: str = _get("database", "server", r"localhost\SQLEXPRESS")
    database: str = _get("database", "database", "COPY_DATA")
    driver: str = _get("database", "driver", "auto")  # "auto" = deteksi otomatis
    trusted_connection: bool = _get("database", "trusted_connection", True)
    username: str = _get("database", "username", "")
    password: str = _get("database", "password", "")
    encrypt: bool = _get("database", "encrypt", True)
    trust_server_certificate: bool = _get("database", "trust_server_certificate", True)
    timeout: int = _get("database", "timeout", 30)

    # --- tabel sumber (OLTP / copy) ---
    source_schema: str = _get("database", "source_schema", "dbo")
    source_noon_table: str = _get("database", "source_noon_table", "NOON_REPORT_COPY")
    source_voyage_table: str = _get("database", "source_voyage_table", "V_Voyages")
    source_vessel_table: str = _get("database", "source_vessel_table", "vessels")
    use_nolock: bool = _get("database", "use_nolock", True)

    # --- schema data warehouse (star schema hasil ETL) ---
    dw_schema: str = _get("database", "dw_schema", "dw")


# --------------------------------------------------------------------------- #
# Aturan analitik & validasi data
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AnalyticsSettings:
    n_cylinders: int = 8

    # Validasi EGT: 0 / NULL = tidak dilaporkan; di luar rentang = tidak valid
    egt_valid_min: float = _get("analytics", "egt_valid_min", 100.0)
    egt_valid_max: float = _get("analytics", "egt_valid_max", 600.0)

    # Minimal jumlah silinder valid dalam 1 laporan agar median EGT bermakna
    min_valid_cylinders: int = _get("analytics", "min_valid_cylinders", 4)

    # Historical baseline (sesuai proposal): deviasi valid historis dari kapal yang sama,
    # silinder yang sama, dan KELOMPOK RENTANG RPM yang sama, hanya laporan SEBELUM laporan
    # yang dinilai (no look-ahead), maksimal `baseline_window` data terakhir.
    #   baseline_mode = "rpm_bin"  -> dikelompokkan per rentang RPM (default, sesuai proposal)
    #   baseline_mode = "rolling"  -> tanpa pengelompokan RPM
    baseline_mode: str = _get("analytics", "baseline_mode", "rpm_bin")
    rpm_bin_width: float = _get("analytics", "rpm_bin_width", 10.0)
    baseline_window: int = _get("analytics", "baseline_window", 60)
    min_baseline_obs: int = _get("analytics", "min_baseline_obs", 10)

    z_constant: float = 0.6745
    z_threshold: float = _get("analytics", "z_threshold", 3.5)

    # Silinder yang tidak pernah punya EGT valid pada sebuah kapal (mis. CYL7-8 di mesin
    # 6 silinder) tidak dimasukkan ke hasil anomali — bukan perubahan rumus.
    drop_uninstalled_cylinders: bool = _get("analytics", "drop_uninstalled_cylinders", True)

    # Hanya muat laporan aktif & tidak diarsipkan ke fact table
    only_active_reports: bool = _get("analytics", "only_active_reports", True)

    # Validasi fisik: EGT tidak valid bila RPM mesin induk = 0 (mesin mati tidak punya suhu gas buang)
    egt_requires_rpm: bool = _get("analytics", "egt_requires_rpm", True)

    # Kolom kecepatan operasional untuk dashboard. AVG_SPEED di data sumber hampir selalu 0,
    # sehingga default memakai SPEED_OVER_GROUND. Pilihan: SPEED_OVER_GROUND, GEN_AVERAGE_SPEED, AVG_SPEED
    speed_column: str = _get("analytics", "speed_column", "SPEED_OVER_GROUND")

    # Forecasting konsumsi BBM main engine (ME_MFO_CONS + ME_MDO_CONS)
    forecast_horizon: int = _get("forecast", "horizon", 3)            # bulan ke depan
    forecast_test_months: int = _get("forecast", "test_months", 3)    # bulan terakhir untuk uji MAPE
    forecast_min_reports: int = _get("forecast", "min_reports_per_month", 15)
    fuel_valid_max: float = _get("forecast", "fuel_valid_max", 100.0)  # MT per laporan; di atasnya = salah input

    # Rentang nilai valid (di luar rentang = invalid)
    valid_ranges: dict = field(
        default_factory=lambda: {
            "AVG_SPEED": (0.0, 30.0),
            "SPEED_OVER_GROUND": (0.0, 30.0),
            "RPM": (0.0, 250.0),
            "SLIP": (-100.0, 100.0),
            "ME_MFO_CONS": (0.0, 200.0),
            "ME_MDO_CONS": (0.0, 200.0),
            "ME_TOTAL_CONS": (0.0, 400.0),
            "GEN_AVERAGE_SPEED": (0.0, 30.0),
            "AE_MFO_CONS": (0.0, 100.0),
            "AE_MDO_CONS": (0.0, 100.0),
            "MFO_TOTAL_CONS": (0.0, 300.0),
            "AIR_TEMPERATURE": (-40.0, 60.0),
            "SEA_TEMPERATURE": (-5.0, 40.0),
        }
    )


@dataclass(frozen=True)
class AppSettings:
    app_name: str = "Marine BI Analytics"
    version_label: str = "VERSION 2"
    default_window_days: int = _get("app", "default_window_days", 30)
    cache_ttl_seconds: int = _get("app", "cache_ttl_seconds", 600)
    max_table_rows: int = _get("app", "max_table_rows", 5000)


@dataclass(frozen=True)
class AutoETLSettings:
    """ETL otomatis: pantau NOON_REPORT_COPY, jalankan incremental bila ada data baru."""
    enabled: bool = _get("auto_etl", "enabled", True)
    interval_seconds: int = _get("auto_etl", "interval_seconds", 60)   # jeda antar pengecekan


@lru_cache(maxsize=1)
def get_auto_etl_settings() -> AutoETLSettings:
    return AutoETLSettings()


@lru_cache(maxsize=1)
def get_db_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache(maxsize=1)
def get_analytics_settings() -> AnalyticsSettings:
    return AnalyticsSettings()


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    return AppSettings()