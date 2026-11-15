"""Filter bar global (Vessel, Voyage, Start Date, End Date + Apply/Reset).

Nilai yang *diterapkan* disimpan di st.session_state["applied_filters"] sehingga
tetap sama ketika berpindah halaman. Widget hanya mengubah pilihan; data baru
dimuat ulang setelah tombol Apply ditekan.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from config.settings import get_app_settings
from services import data
from services.data import ALL, Filters

W_VESSEL, W_VOYAGE, W_START, W_END = "w_vessel", "w_voyage", "w_start", "w_end"
APPLIED = "applied_filters"


def _defaults(opts: dict) -> Filters:
    end = opts["max_date"]
    start = max(opts["min_date"], end - dt.timedelta(days=get_app_settings().default_window_days))
    return Filters(ALL, ALL, start, end)


def _seed_widgets(f: Filters) -> None:
    st.session_state[W_VESSEL] = f.vessel
    st.session_state[W_VOYAGE] = f.voyage
    st.session_state[W_START] = f.start
    st.session_state[W_END] = f.end


def _apply() -> None:
    s, e = st.session_state[W_START], st.session_state[W_END]
    if s and e and s > e:
        s, e = e, s
        st.session_state[W_START], st.session_state[W_END] = s, e
    st.session_state[APPLIED] = Filters(st.session_state[W_VESSEL], st.session_state[W_VOYAGE], s, e)


def _reset(defaults: Filters) -> None:
    st.session_state[APPLIED] = defaults
    _seed_widgets(defaults)


def render_filter_bar(apply_label: str = "Apply Filters") -> Filters:
    opts = data.filter_options()
    defaults = _defaults(opts)
    applied: Filters = st.session_state.setdefault(APPLIED, defaults)
    mn, mx = opts["min_date"], opts["max_date"]

    # Pulihkan state widget (mis. setelah pindah halaman) dari filter yang diterapkan
    for key, val in ((W_VESSEL, applied.vessel), (W_VOYAGE, applied.voyage),
                     (W_START, applied.start), (W_END, applied.end)):
        if key not in st.session_state:
            st.session_state[key] = val
    for key in (W_START, W_END):
        v = st.session_state.get(key)
        if not isinstance(v, dt.date) or v < mn or v > mx:
            st.session_state[key] = defaults.start if key == W_START else defaults.end

    vessels: pd.DataFrame = opts["vessels"]
    voyages: pd.DataFrame = opts["voyages"]
    vessel_names = dict(zip(vessels["Vessel_Key"], vessels["NAME"].fillna("")))
    vessel_opts = [ALL, *vessels["Vessel_Key"].tolist()]
    if st.session_state[W_VESSEL] not in vessel_opts:
        st.session_state[W_VESSEL] = ALL

    with st.container(border=True):
        c1, c2, c3, c4, c5, c6 = st.columns([1.25, 1.25, 1, 1, 0.62, 0.42], vertical_alignment="bottom")
        c1.selectbox(
            "Vessel", vessel_opts, key=W_VESSEL,
            format_func=lambda k: "All Vessels" if k == ALL else f"{vessel_names.get(k, '')} ({k})".strip())

        sel_vessel = st.session_state[W_VESSEL]
        voy = voyages if sel_vessel == ALL else voyages[voyages["Vessel_Key"] == sel_vessel]
        voy_labels = {
            r.Voyage_Key: f"{r.Voyage_Label}  ({int(r.Report_Count)} reports)"
            for r in voy.itertuples()
        }
        voyage_opts = [ALL, *voy["Voyage_Key"].tolist()]
        if st.session_state[W_VOYAGE] not in voyage_opts:
            st.session_state[W_VOYAGE] = ALL
        c2.selectbox("Voyage / FID_VOYAGE", voyage_opts, key=W_VOYAGE,
                     format_func=lambda k: "All Voyages" if k == ALL else voy_labels.get(k, k))

        c3.date_input("Start Date", key=W_START, min_value=mn, max_value=mx, format="DD/MM/YYYY")
        c4.date_input("End Date", key=W_END, min_value=mn, max_value=mx, format="DD/MM/YYYY")
        c5.button(apply_label, type="primary", on_click=_apply, width="stretch")
        c6.button("Reset", on_click=_reset, args=(defaults,), width="stretch")

    pending = Filters(st.session_state[W_VESSEL], st.session_state[W_VOYAGE],
                      st.session_state[W_START], st.session_state[W_END])
    if pending != st.session_state[APPLIED]:
        st.caption(f":orange[Filter changes are not applied yet — click **{apply_label}**.]")
    return st.session_state[APPLIED]


def describe_filters(f: Filters) -> str:
    from ui.components import fmt_date_range
    return fmt_date_range(f.start, f.end)