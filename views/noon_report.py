"""Halaman: Noon Report Dashboard."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import get_app_settings
from core.schema import EGT_COLS
from services import data
from ui import charts, theme
from ui import components as ui
from ui.filters import render_filter_bar
from ui.layout import dataset_chip, require_warehouse

PAGE = "Noon Report"
ui.topbar(PAGE)
require_warehouse(PAGE)
ui.page_header("Noon Report Dashboard", "Historical operational performance overview", dataset_chip())

flt = render_filter_bar("Apply Filters")
df = data.noon_reports(flt)
period = ui.fmt_date_range(flt.start, flt.end)
ui.note(f"Data window · {period} · source: dw.FACT_NOON_REPORT (star schema, loaded by ETL)")

if df.empty:
    ui.empty_state("No noon reports match the selected filters.")
    ui.page_footer(PAGE)
    st.stop()

n_vessels = df["Vessel_Key"].nunique()
n_voyages = df["Voyage_Key"].nunique()
multi = n_vessels > 1

# ------------------------------------------------------------ summary strip --
voy_labels = df["Voyage_Label"].dropna().unique().tolist()
voy_txt = ", ".join(voy_labels[:2]) + (f" +{len(voy_labels) - 2} more" if len(voy_labels) > 2 else "")
ports = df.dropna(subset=["NEXT_PORT"]).sort_values("REPORT_DATE")
next_port = ports["NEXT_PORT"].iloc[-1] if len(ports) else "Unavailable"
vessel_names = df["VESSEL_NAME"].fillna(df["Vessel_Key"]).unique().tolist()
vessel_txt = vessel_names[0] if len(vessel_names) == 1 else f"{len(vessel_names)} vessels"
date_txt = ui.fmt_date_range(df["REPORT_DATE"].min(), df["REPORT_DATE"].max())

c_strip, c_kpi = st.columns([3.3, 1], vertical_alignment="center")
with c_strip:
    ui.info_strip([("Voyage", voy_txt or "—"), ("REPORT_DATE", date_txt),
                   ("NEXT_PORT (latest)", str(next_port)), ("Vessel", vessel_txt)])
with c_kpi:
    ui.kpi("Total Noon Reports", f"{len(df):,} reports", f"{date_txt} · {n_voyages} voyages")
st.write("")

# ------------------------------------------------------------------ charts --
if multi:
    series_df = (df.assign(_d=df["REPORT_DATE"].dt.normalize())
                 .groupby("_d", as_index=False)[["OPERATIONAL_SPEED", "RPM", "ME_MFO_CONS", "ME_MDO_CONS", "ME_TOTAL_CONS"]].mean()
                 .rename(columns={"_d": "REPORT_DATE"}))
    sub = f"Daily mean across {n_vessels} vessels"
else:
    series_df = df.sort_values("REPORT_DATE")
    sub = "Daily observations"

c1, c2, c3 = st.columns(3)
with c1, st.container(border=True):
    ui.card_title("Operational speed", sub)
    charts.show(charts.line_chart(series_df, "REPORT_DATE", [("OPERATIONAL_SPEED", data.speed_col(), theme.PRIMARY)],
                                  "knots"), key="nr_speed")
with c2, st.container(border=True):
    ui.card_title("Main engine RPM", sub)
    charts.show(charts.line_chart(series_df, "REPORT_DATE", [("RPM", "RPM", theme.PRIMARY)], "RPM"),
                key="nr_rpm")
with c3, st.container(border=True):
    ui.card_title("Main engine consumption", sub)
    charts.show(charts.line_chart(series_df, "REPORT_DATE",
                                  [("ME_MFO_CONS", "ME_MFO_CONS", theme.PRIMARY),
                                   ("ME_MDO_CONS", "ME_MDO_CONS", theme.PRIMARY_LIGHT)], "MT"),
                key="nr_cons")

tot_mfo, tot_mdo = df["ME_MFO_CONS"].sum(min_count=1), df["ME_MDO_CONS"].sum(min_count=1)
ui.foot(f"Total ME consumption = ΣME_MFO_CONS + ΣME_MDO_CONS over {len(df):,} selected records = "
        f"{ui.fmt_num(tot_mfo)} + {ui.fmt_num(tot_mdo)} MT. Missing values are not imputed.")
st.write("")

# --------------------------------------------- selected report: thermal & env --
ordered = df.sort_values("REPORT_DATE", ascending=False)
labels = {r.Noon_Report_Key: f"{r.REPORT_DATE:%Y-%m-%d %H:%M} · {r.Voyage_Label}"
          + (" · ⚠ ANOMALY" if r.Anomaly_Status == "ANOMALY" else "")
          for r in ordered.itertuples()}
if st.session_state.get("nr_selected") not in labels:
    st.session_state.pop("nr_selected", None)
sel_key = st.selectbox("Selected report", list(labels.keys()), format_func=labels.get, key="nr_selected")
rep = ordered[ordered["Noon_Report_Key"] == sel_key].iloc[0]
cyl = data.cylinder_for_report(sel_key)
statuses = (cyl.set_index("Cylinder_No")["ANOMALY_STATUS"].reindex(range(1, 9)).fillna("").tolist()
            if len(cyl) else None)

t1, t2 = st.columns([1.55, 1])
with t1, st.container(border=True):
    egt_vals = [rep[c] for c in EGT_COLS]
    n_ok = sum(pd.notna(v) for v in egt_vals)
    ui.card_title("Main engine thermal condition",
                  f"{rep['REPORT_DATE']:%d %b %Y} · {rep['Voyage_Label']}", badge="EXH_TEMP_CYL1–8 · °C")
    ui.cylinder_tiles(egt_vals, statuses)
    ui.foot(f"Reported exhaust gas temperatures · {n_ok} of 8 cylinders valid · median "
            f"{ui.fmt_num(rep['MEDIAN_EGT'], 1)} °C · report status: {ui.txt(rep['Anomaly_Status'])}")
with t2, st.container(border=True):
    ui.card_title("Environmental conditions", f"{rep['REPORT_DATE']:%d %b %Y} · selected report")
    env = pd.DataFrame([{
        "WIND_DIRECTION": ui.txt(rep["WIND_DIRECTION"]),
        "FORCE": ui.fmt_num(rep["FORCE"], 0),
        "AIR_TEMPERATURE": f"{ui.fmt_num(rep['AIR_TEMPERATURE'], 0)} °C",
        "SEA_TEMPERATURE": f"{ui.fmt_num(rep['SEA_TEMPERATURE'], 0)} °C",
        "SWELL_HEIGHT": ui.fmt_num(rep["SWELL_HEIGHT"], 1),
    }])
    st.dataframe(env, hide_index=True, width="stretch")
    ui.foot("Selected report context · temperatures parsed from text values such as '31° C'.")
st.write("")

# --------------------------------------------------------------- vessel map --
with st.container(border=True):
    n_pos = len(charts.valid_positions(df))
    ui.card_title("Vessel positions & track",
                  f"{'Track per vessel' if multi else 'Vessel track'} from noon report LATITUDE / LONGITUDE · "
                  "red = thermal anomaly · navy = selected report",
                  badge=f"{n_pos:,} POSITIONS")
    fig_map = charts.vessel_map(df, selected_key=sel_key, speed_col=data.speed_col())
    if fig_map is None:
        st.caption("No valid positions (LATITUDE / LONGITUDE) in the selected reports.")
    else:
        charts.show_map(fig_map, key="nr_map")
        ui.foot(f"{n_pos:,} of {len(df):,} reports have a valid position (empty, 0/0 or out-of-range "
                "coordinates are not drawn) · scroll to zoom · hover a point for details · "
                "label = latest position in the window")
st.write("")

# ------------------------------------------------------------ detail tables --
max_rows = get_app_settings().max_table_rows
view = df.sort_values("REPORT_DATE")
if len(view) > max_rows:
    st.caption(f"Showing the first {max_rows:,} of {len(view):,} rows. Download the CSV for all rows.")
view = view.head(max_rows)

with st.container(border=True):
    ui.card_title("Detailed Noon Reports", "Operational fields · paired with cylinder detail below",
                  badge=f"{len(df):,} RECORDS")
    cols = ["REPORT_DATE", "VESSEL_NAME", "Voyage_Label", "NEXT_PORT", "OPERATIONAL_SPEED", "AVG_SPEED", "RPM",
            "ME_MFO_CONS", "ME_MDO_CONS", "ME_TOTAL_CONS", "Anomaly_Status"]
    st.dataframe(
        view[cols], hide_index=True, width="stretch", height=380,
        column_config={
            "REPORT_DATE": st.column_config.DatetimeColumn("REPORT_DATE", format="YYYY-MM-DD HH:mm"),
            "VESSEL_NAME": "Vessel", "Voyage_Label": "Voyage",
            "NEXT_PORT": st.column_config.TextColumn("NEXT_PORT"),
            "OPERATIONAL_SPEED": st.column_config.NumberColumn(f"{data.speed_col()} (knots)", format="%.2f"),
            "AVG_SPEED": st.column_config.NumberColumn("AVG_SPEED (knots)", format="%.1f"),
            "ME_TOTAL_CONS": st.column_config.NumberColumn("ME_TOTAL_CONS (MT)", format="%.2f"),
            "RPM": st.column_config.NumberColumn("RPM", format="%.0f"),
            "ME_MFO_CONS": st.column_config.NumberColumn("ME_MFO_CONS (MT)", format="%.2f"),
            "ME_MDO_CONS": st.column_config.NumberColumn("ME_MDO_CONS (MT)", format="%.2f"),
            "Anomaly_Status": "Thermal status",
        })
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="noon_reports.csv", mime="text/csv", icon=":material/download:")

st.write("")
with st.container(border=True):
    ui.card_title("Noon Report continuation · Cylinder detail",
                  "Same reports, same order · EXH_TEMP_CYL1–8 (°C) · empty = not reported / invalid",
                  badge="TEMPERATURE · °C")
    st.dataframe(
        view[["REPORT_DATE", "Voyage_Label", *EGT_COLS, "MEDIAN_EGT"]], hide_index=True,
        width="stretch", height=380,
        column_config={
            "REPORT_DATE": st.column_config.DatetimeColumn("REPORT_DATE", format="YYYY-MM-DD HH:mm"),
            "Voyage_Label": "Voyage",
            **{c: st.column_config.NumberColumn(c, format="%.0f") for c in EGT_COLS},
            "MEDIAN_EGT": st.column_config.NumberColumn("MEDIAN_EGT", format="%.1f"),
        })

ui.page_footer(PAGE)    