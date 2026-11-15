"""
Marine BI Analytics — entry point Streamlit.

Jalankan:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from config.settings import get_app_settings
from services import data
from ui.theme import inject_css

st.set_page_config(
    page_title=get_app_settings().app_name,
    page_icon=":material/directions_boat:",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

PAGES = {
    "noon": st.Page("views/noon_report.py", title="Noon Report", icon=":material/description:", default=True),
    "thermal": st.Page("views/thermal_anomaly.py", title="Thermal Anomaly", icon=":material/monitor_heart:"),
    "forecast": st.Page("views/forecasting.py", title="Forecasting", icon=":material/trending_up:"),
    "etl": st.Page("views/etl_pipeline.py", title="ETL Pipeline", icon=":material/sync:"),
}

pg = st.navigation(list(PAGES.values()), position="hidden")


def _sidebar() -> None:
    """Sidebar statis - TIDAK memanggil database, supaya menu & halaman langsung tampil."""
    with st.sidebar:
        st.markdown(
            """<div style="display:flex;gap:.75rem;align-items:center;margin:.2rem 0 1.6rem .1rem">
                 <div style="width:38px;height:38px;border-radius:8px;background:#24406B;display:flex;
                      align-items:center;justify-content:center;font-size:20px">⚓</div>
                 <div style="color:#fff !important;font-size:1.12rem;line-height:1.2">Marine BI<br>Analytics</div>
               </div>
               <div style="font-size:.68rem;font-weight:600;letter-spacing:.06em;margin:0 0 .4rem .2rem">
               ANALYTICS WORKSPACE</div>""",
            unsafe_allow_html=True,
        )
        for key in ("noon", "thermal", "forecast"):
            st.page_link(PAGES[key])
        st.markdown('<div style="font-size:.68rem;font-weight:600;letter-spacing:.06em;'
                    'margin:1.2rem 0 .4rem .2rem">DATA PIPELINE</div>', unsafe_allow_html=True)
        st.page_link(PAGES["etl"])
        st.markdown(
            """<div class="mbi-side-foot"><div style="font-size:1.1rem">🗄️</div>
                <div class="t">Historical Noon Report</div>
                <div class="d">Historical Analytics</div></div>""",
            unsafe_allow_html=True,
        )


def _auto_etl_status() -> None:
    """Indikator Auto ETL di sidebar. Fragment ini berjalan ulang sendiri secara berkala
    (tanpa query DB - hanya membaca status watcher di memori). Jika watcher baru saja
    memuat data baru, cache dibersihkan dan seluruh halaman di-refresh otomatis."""
    watcher = data.get_auto_etl()
    if watcher is None:
        return

    @st.fragment(run_every=max(10, watcher.interval // 2))
    def _status() -> None:
        seen = st.session_state.setdefault("_auto_etl_seen", watcher.data_version)
        if watcher.data_version != seen:
            st.session_state["_auto_etl_seen"] = watcher.data_version
            data.clear_caches()
            run = watcher.last_run
            st.session_state["_auto_etl_toast"] = (
                f"Auto ETL: {run.rows_loaded:,} new/changed noon report(s) loaded" if run else "Auto ETL: data updated")
            st.rerun(scope="app")
        dot = "🔴" if watcher.last_error else "🟢"
        last = f"{watcher.last_check:%H:%M:%S}" if watcher.last_check else "—"
        st.markdown(f'<div style="font-size:.72rem;margin:.9rem 0 0 .2rem;opacity:.85">{dot} Auto ETL on · '
                    f'checked {last}</div>', unsafe_allow_html=True)

    with st.sidebar:
        _status()
    msg = st.session_state.pop("_auto_etl_toast", None)
    if msg:
        st.toast(msg, icon=":material/sync:")


_sidebar()
_auto_etl_status()
pg.run()