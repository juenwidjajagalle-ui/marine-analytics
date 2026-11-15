"""
Cek kecepatan koneksi ke SQL Server.

    python -m scripts.cek_koneksi
"""
from __future__ import annotations

import time
from dataclasses import replace

from sqlalchemy import text

from config.settings import get_db_settings
from core.database import build_odbc_string, make_engine


def test(server: str) -> None:
    cfg = replace(get_db_settings(), server=server, timeout=15)
    print(f"\n=== SERVER = {server}")
    try:
        t0 = time.perf_counter()
        eng = make_engine(cfg)
        with eng.connect() as conn:
            t1 = time.perf_counter()
            row = conn.execute(text("SELECT @@SERVERNAME, DB_NAME()")).one()
            t2 = time.perf_counter()
        eng.dispose()
        print(f"  connect : {t1 - t0:6.2f} s")
        print(f"  query   : {t2 - t1:6.2f} s   -> {row[0]} / {row[1]}")
    except Exception as exc:  # noqa: BLE001
        print(f"  GAGAL   : {str(exc)[:200]}")


def main() -> None:
    cfg = get_db_settings()
    print("Driver/ODBC:", build_odbc_string(cfg).split(";")[0])
    candidates = [cfg.server]
    inst = cfg.server.split("\\", 1)[1] if "\\" in cfg.server else None
    if inst:
        candidates += [f"(local)\\{inst}", f".\\{inst}", f"lpc:(local)\\{inst}"]
    for s in dict.fromkeys(candidates):
        test(s)
    print("\nPilih SERVER yang 'connect'-nya paling cepat, lalu tulis di .streamlit/secrets.toml "
          "bagian [database] server = '...'.")


if __name__ == "__main__":
    main()
    
# PS C:\skripsi_bi>    cd C:\skripsi_bi
# PS C:\skripsi_bi>    Set-ExecutionPolicy -Scope Process Bypass
# PS C:\skripsi_bi>    .\venv312\Scripts\Activate.ps1
# (venv312) PS C:\skripsi_bi>    streamlit run app.py                