"""Kerangka halaman: topbar + pengecekan kesiapan data warehouse."""
from __future__ import annotations

import streamlit as st

from services.data import filter_options, warehouse_ready
from ui import components as ui


def dataset_chip() -> str:
    try:
        o = filter_options()
        return f"Historical Dataset | {o['min_date'].year}–{o['max_date'].year}"
    except Exception:  # noqa: BLE001
        return "Historical Dataset"


def require_warehouse(page_name: str) -> None:
    """Hentikan halaman dengan pesan ramah jika star schema belum siap."""
    ok, msg = warehouse_ready()
    if ok:
        return
    ui.empty_state(msg)
    st.page_link("views/etl_pipeline.py", label="Open the ETL Pipeline page", icon=":material/sync:")
    ui.page_footer(page_name)
    st.stop()
