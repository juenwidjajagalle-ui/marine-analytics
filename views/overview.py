"""Halaman: Overview (ringkasan armada, anomali, status ETL)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services import data
from ui import charts, theme
from ui import components as ui
from ui.filters import render_filter_bar
from ui.layout import dataset_chip, require_warehouse

PAGE = "Overview"


def _i(v) -> int:
    return int(v) if pd.notna(v) else 0


ui.topbar(PAGE)
require_warehouse(PAGE)
ui.page_header("Fleet Overview", "Historical noon report activity and thermal anomaly summary", dataset_chip())

flt = render_filter_bar("Apply Filters")
monthly = data.monthly_summary(flt)
by_vessel = data.vessel_summary(flt)
ui.note(f"Data window · {ui.fmt_date_range(flt.start, flt.end)} · source: dw star schema")

if monthly.empty:
    ui.empty_state("No noon reports match the selected filters.")
    ui.page_footer(PAGE)
    st.stop()

n_reports = int(monthly["Reports"].sum())
n_anom = int(by_vessel["Anomalies"].sum()) if len(by_vessel) else 0
n_calc = int(by_vessel["Calculable"].sum()) if len(by_vessel) else 0
n_rep_anom = int(monthly["Anomaly_Reports"].sum())
opts = data.filter_options()
voy = opts["voyages"]
if flt.vessel != data.ALL:
    voy = voy[voy["Vessel_Key"] == flt.vessel]
k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.kpi("Noon reports", f"{n_reports:,}", f"{len(monthly)} months in window")
with k2:
    ui.kpi("Vessels reporting", f"{len(by_vessel):,}", f"{len(voy):,} voyages in master data")
with k3:
    ui.kpi("Cylinder anomalies", f"{n_anom:,}", f"{n_anom / max(n_calc, 1) * 100:.2f}% of {n_calc:,} scored cylinders")
with k4:
    ui.kpi("Reports flagged", f"{n_rep_anom:,}", f"{n_rep_anom / max(n_reports, 1) * 100:.1f}% of reports")
st.write("")

c1, c2 = st.columns([1.5, 1])
with c1, st.container(border=True):
    ui.card_title("Noon reports per month", "Bar = reports · used as data volume / reporting discipline check")
    charts.show(charts.bar_chart(monthly, "Year_Month", "Reports", "Reports", height=290), key="ov_month")
with c2, st.container(border=True):
    ui.card_title("Anomaly rate by vessel", "Anomalous cylinders / scored cylinders (%)")
    if len(by_vessel):
        bv = by_vessel.assign(
            Rate=by_vessel["Anomalies"] / by_vessel["Calculable"].where(by_vessel["Calculable"] > 0) * 100,
            Label=by_vessel["NAME"].fillna(by_vessel["Vessel_Key"]),
        ).sort_values("Rate", ascending=False).head(15)
        charts.show(charts.bar_chart(bv, "Label", "Rate", "Rate %", color=theme.BAD_FG, height=290,
                                     horizontal=True, y_title="%"), key="ov_vessel")
    else:
        st.caption("No anomaly results yet.")

c3, c4 = st.columns([1.5, 1])
with c3, st.container(border=True):
    ui.card_title("Average speed at sea per month", "Mean AVG_SPEED excluding 0 (in port)")
    charts.show(charts.line_chart(monthly.assign(Year_Month=pd.to_datetime(monthly["Year_Month"])),
                                  "Year_Month", [("Avg_Speed", "AVG_SPEED", theme.PRIMARY)], "knots",
                                  height=250, tickformat="%b %Y"), key="ov_speed")
with c4, st.container(border=True):
    ui.card_title("Last ETL run", "dw.ETL_RUN_LOG")
    runs = data.etl_runs(1)
    if runs.empty:
        st.caption("No ETL run recorded yet.")
    else:
        r = runs.iloc[0]
        st.markdown(
            f"**Status:** {r['Status']} · **Mode:** {r['Mode']}  \n"
            f"**Started:** {pd.Timestamp(r['Started_At']):%Y-%m-%d %H:%M}  \n"
            f"**Rows loaded:** {_i(r['Rows_Loaded']):,} · **Anomalies:** {_i(r['Anomalies']):,}  \n"
            f"**Watermark:** {r['Watermark_To'] if pd.notna(r['Watermark_To']) else '—'}")
    st.page_link("views/etl_pipeline.py", label="Open ETL Pipeline", icon=":material/sync:")

ui.page_footer(PAGE)
