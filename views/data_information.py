"""Halaman: Data Information (statistik deskriptif & kelengkapan data)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from analytics.descriptive import completeness_all, describe
from config.settings import get_analytics_settings
from core import schema
from services import data
from ui import components as ui
from ui.filters import render_filter_bar
from ui.layout import dataset_chip, require_warehouse

PAGE = "Data Information"
UNITS = {
    "AVG_SPEED": "knots", "SPEED_OVER_GROUND": "knots", "RPM": "RPM", "SLIP": "%",
    "ME_MFO_CONS": "MT", "ME_MDO_CONS": "MT", "AE_MFO_CONS": "MT", "AE_MDO_CONS": "MT",
    "MFO_TOTAL_CONS": "MT", "BOILER_MFO_CONS": "MT", "BOILER_MDO_CONS": "MT",
    "AIR_TEMPERATURE": "°C", "SEA_TEMPERATURE": "°C", "MEDIAN_EGT": "°C",
    **{c: "°C" for c in schema.EGT_COLS},
    "ROB_MFO": "MT", "ROB_MDO": "MT", "ROB_FW": "MT", "DIST_OVER_GROUND": "nm", "DISTANCE_TO_GO": "nm",
}
DEFAULT_VARS = ["AVG_SPEED", "RPM", "ME_MFO_CONS", "ME_MDO_CONS"]
NUMERIC_CHOICES = schema.NUMERIC_COLS + schema.TEXT_NUMERIC_COLS + ["MEDIAN_EGT"]

ui.topbar(PAGE)
require_warehouse(PAGE)
ui.page_header("Data Information", "Descriptive overview of historical Noon Report data", dataset_chip())

flt = render_filter_bar("Apply Filters")
df = data.noon_reports(flt, all_columns=True)
period = ui.fmt_date_range(flt.start, flt.end)
ui.note(f"Data window · {period} · statistics from dw.FACT_NOON_REPORT after ETL cleaning")

if df.empty:
    ui.empty_state("No noon reports match the selected filters.")
    ui.page_footer(PAGE)
    st.stop()

# -------------------------------------------------------------- overview --
ui.section("Dataset Overview")
days_span = (flt.end - flt.start).days + 1 if flt.start and flt.end else 0
days_with = df["REPORT_DATE"].dt.normalize().nunique()
voy = df["Voyage_Label"].dropna().unique().tolist()
k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.kpi("Total Noon Report Records", f"{len(df):,} records", f"Selected window · {period}")
with k2:
    ui.kpi("Number of Voyages", f"{len(voy):,} voyages",
           ", ".join(voy[:2]) + (f" +{len(voy) - 2} more" if len(voy) > 2 else ""))
with k3:
    ui.kpi("Vessels", f"{df['Vessel_Key'].nunique():,} vessels",
           ", ".join(df["VESSEL_NAME"].dropna().unique()[:2]))
with k4:
    ui.kpi("Date Coverage", f"{days_with:,} / {days_span:,} days",
           f"{days_with / max(days_span, 1) * 100:.1f}% of days have ≥ 1 report")
st.write("")

# ------------------------------------------------------ descriptive stats --
with st.container(border=True):
    h1, h2, h3 = st.columns([2.2, 1.4, 0.9], vertical_alignment="center")
    with h1:
        ui.card_title("Descriptive Statistics", "Statistics from valid observations only")
    variables = h2.multiselect("Variables", NUMERIC_CHOICES, default=DEFAULT_VARS, key="di_vars",
                               label_visibility="collapsed", placeholder="Choose variables")
    zero_missing = h3.toggle("0 = missing", key="di_zero",
                             help="Treat zero values (e.g. ship in port / engine stopped) as missing.")
    stats = describe(df, variables, get_analytics_settings().valid_ranges, zero_missing)
    if stats.empty:
        st.caption("Choose at least one variable.")
    else:
        show = stats.assign(Variable=stats["Variable"].map(
            lambda v: f"{v} ({UNITS[v]})" if v in UNITS else v))
        st.dataframe(
            show[["Variable", "Mean", "Median", "Min", "Max", "Std", "N_Valid"]],
            hide_index=True, width="stretch",
            column_config={c: st.column_config.NumberColumn(c, format="%.2f")
                           for c in ["Mean", "Median", "Min", "Max", "Std"]}
            | {"N_Valid": st.column_config.NumberColumn("N valid", format="%d")})
        notes = []
        for r in stats.itertuples():
            if r.N_Missing or r.N_Invalid:
                notes.append(f"{r.Variable}: {r.N_Missing} missing, {r.N_Invalid} out of valid range")
        ranges = get_analytics_settings().valid_ranges
        ui.foot(("; ".join(notes) + ". " if notes else "No missing or invalid observations. ")
                + "Invalid = outside the configured plausible range ("
                + ", ".join(f"{k} {lo:g}–{hi:g}" for k, (lo, hi) in ranges.items() if k in variables)
                + "). MT unit should be confirmed against the source system.")
st.write("")

# ---------------------------------------------------------- completeness --
if not stats.empty:
    with st.container(border=True):
        ui.card_title("Data Completeness",
                      f"Valid counts and missing percentages out of {len(df):,} selected records")
        ui.completeness_grid(stats)
st.write("")

with st.expander("Completeness of every column in FACT_NOON_REPORT", icon=":material/table_view:"):
    cols = [c for c in schema.FACT_COLUMNS if c in df.columns and c not in ("ETL_LOADED_AT",)]
    comp = completeness_all(df, cols)
    comp["Filled_Pct"] = 100 - comp["Missing_Pct"]
    st.dataframe(comp[["Column", "Filled", "Missing", "Filled_Pct"]], hide_index=True, width="stretch",
                 height=420, column_config={"Filled_Pct": st.column_config.ProgressColumn(
                     "Filled %", format="%.1f%%", min_value=0, max_value=100)})

with st.expander("Star schema & lineage", icon=":material/schema:"):
    st.markdown("""
| Table | Grain | Source | Key |
|---|---|---|---|
| `dw.DIM_DATE` | 1 row / calendar day | generated from REPORT_DATE range | `Date_Key` (YYYYMMDD) |
| `dw.DIM_VESSEL` | 1 row / vessel | `dbo.vessels` | `Vessel_Key` = CODE_VESSEL |
| `dw.DIM_VOYAGE` | 1 row / voyage | `dbo.V_Voyages` | `Voyage_Key` = ID_VOYAGE |
| `dw.FACT_NOON_REPORT` | 1 row / noon report | `dbo.NOON_REPORT_COPY` | `Noon_Report_Key` = ID_NOON_REPORT |
| `dw.FACT_CYLINDER_ANOMALY` | 1 row / report × cylinder | computed from EXH_TEMP_CYL1–8 | (`Noon_Report_Key`, `Cylinder_No`) |

`FACT_NOON_REPORT.Vessel_Key` is resolved through `FID_VOYAGE → V_Voyages.FCODE_VESSEL`.
Reports whose voyage is not in `V_Voyages` are kept under `Vessel_Key = 'UNKNOWN'`.
""")

ui.page_footer(PAGE)
