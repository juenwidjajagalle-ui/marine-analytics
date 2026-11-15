"""Halaman: Thermal Anomaly Analysis (Median EGT → Deviation → MAD → Modified Z-Score)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from analytics.thermal import ANOMALY, NORMAL, NOT_VALID
from config.settings import get_analytics_settings, get_app_settings
from core.schema import EGT_COLS
from services import data
from ui import charts
from ui import components as ui
from ui.filters import render_filter_bar
from ui.layout import dataset_chip, require_warehouse

PAGE = "Thermal Anomaly"
P = get_analytics_settings()
BASELINE_TXT = (f"same vessel, cylinder and RPM range ({P.rpm_bin_width:g} RPM), last {P.baseline_window} values"
                if P.baseline_mode == "rpm_bin" else
                f"same vessel and cylinder, last {P.baseline_window} values")
REASON_TEXT = {
    "OK": "Calculated",
    "MISSING_OR_INVALID_EGT": "EGT missing, 0 or outside valid range",
    "RPM_NOT_AVAILABLE": "RPM missing or 0 (engine not running)",
    "INSUFFICIENT_CYLINDERS": f"Fewer than {P.min_valid_cylinders} valid cylinders in the report",
    "INSUFFICIENT_BASELINE": f"Fewer than {P.min_baseline_obs} historical deviations in the baseline",
    "MAD_ZERO": "MAD = 0 (no spread in baseline)",
}

ui.topbar(PAGE)
require_warehouse(PAGE)
ui.page_header("Thermal Anomaly Analysis",
               "Historical exhaust gas temperature deviation analysis across main engine cylinders",
               dataset_chip())

flt = render_filter_bar("Run Analysis")
noon = data.noon_reports(flt)
cyl = data.cylinder_anomalies(flt)
ui.note(f"Data window · {ui.fmt_date_range(flt.start, flt.end)} · source: dw.FACT_CYLINDER_ANOMALY "
        f"· baseline = {BASELINE_TXT}")

if noon.empty or cyl.empty:
    ui.empty_state("No cylinder observations match the selected filters.")
    ui.page_footer(PAGE)
    st.stop()

# ------------------------------------------------------------------- KPIs --
n_obs = len(cyl)
n_anom = int((cyl["ANOMALY_STATUS"] == ANOMALY).sum())
n_norm = int((cyl["ANOMALY_STATUS"] == NORMAL).sum())
n_na = int((cyl["ANOMALY_STATUS"] == NOT_VALID).sum())
n_rep_anom = int((noon["Anomaly_Status"] == ANOMALY).sum())
k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.kpi("Cylinder observations", f"{n_obs:,}", f"{len(noon):,} reports × installed cylinders")
with k2:
    ui.kpi("Anomalies", f"{n_anom:,}", f"{n_anom / max(n_anom + n_norm, 1) * 100:.2f}% of calculable · "
           f"{n_rep_anom:,} reports flagged")
with k3:
    ui.kpi("Normal", f"{n_norm:,}", "|Modified Z| ≤ 3.5")
with k4:
    ui.kpi("Data not valid", f"{n_na:,}", "criteria not met (EGT/RPM, baseline, MAD = 0)")
st.write("")

# ------------------------------------------------- default selected report --
ordered = noon.sort_values("REPORT_DATE", ascending=False)
anom_reports = ordered[ordered["Anomaly_Status"] == ANOMALY]
default_key = (anom_reports if len(anom_reports) else ordered)["Noon_Report_Key"].iloc[0]
labels = {r.Noon_Report_Key: f"{r.REPORT_DATE:%Y-%m-%d %H:%M} · {r.Voyage_Label}"
          + (f" · ⚠ {int(r.ANOMALY_CYLINDERS)} anomaly" if r.Anomaly_Status == ANOMALY else "")
          for r in ordered.itertuples()}
if st.session_state.get("ta_selected") not in labels:
    st.session_state["ta_selected"] = default_key

# ---------------------------------------------------------------- charts --
c_left, c_right = st.columns([1.55, 1])
with c_left, st.container(border=True):
    multi = noon["Vessel_Key"].nunique() > 1
    if multi:
        egt_df = (noon.assign(_d=noon["REPORT_DATE"].dt.normalize())
                  .groupby("_d", as_index=False)[EGT_COLS].mean().rename(columns={"_d": "REPORT_DATE"}))
        sub = f"EXH_TEMP_CYL1–CYL8 · daily mean across {noon['Vessel_Key'].nunique()} vessels"
    else:
        egt_df, sub = noon.sort_values("REPORT_DATE"), "EXH_TEMP_CYL1–CYL8 · daily observations"
    # penanda anomali: posisi = suhu silinder yang anomali pada tanggal laporannya
    anom = cyl[cyl["ANOMALY_STATUS"] == ANOMALY].copy()
    if multi:
        anom["REPORT_DATE"] = anom["REPORT_DATE"].dt.normalize()
        sub += " · red circles = anomalous cylinder readings (actual EGT of that vessel)"
    else:
        sub += " · red circles = ANOMALY"
    sel_rep = ordered[ordered["Noon_Report_Key"] == st.session_state["ta_selected"]]
    sel_date = None
    if len(sel_rep):
        sel_date = sel_rep["REPORT_DATE"].iloc[0]
        sel_date = sel_date.normalize() if multi else sel_date
    ui.card_title("Historical exhaust gas temperature", sub)
    charts.show(charts.egt_chart(egt_df, "REPORT_DATE", EGT_COLS, height=330, anomalies=anom,
                                 selected_date=sel_date), key="ta_egt")
    ui.foot(f"{len(anom):,} anomalous cylinder reading(s) in this window · dotted line = selected report "
            "(shown on the right) · hover a red circle for vessel, cylinder and Modified Z-Score")

with c_right, st.container(border=True):
    sel_key = st.selectbox("Report", list(labels.keys()), format_func=labels.get, key="ta_selected",
                           label_visibility="collapsed")
    sel = cyl[cyl["Noon_Report_Key"] == sel_key].sort_values("Cylinder_No")
    rep = ordered[ordered["Noon_Report_Key"] == sel_key].iloc[0]
    ui.card_title("Cylinder Deviation",
                  f"{rep['REPORT_DATE']:%d %b %Y} · {rep['Voyage_Label']} · "
                  f"cylinder EGT minus same-report median: {ui.fmt_num(rep['MEDIAN_EGT'], 1)} °C")
    charts.show(charts.deviation_bar([f"CYL{n}" for n in sel["Cylinder_No"]],
                                     sel["CYLINDER_DEVIATION"].tolist(), sel["ANOMALY_STATUS"].tolist(),
                                     height=270), key="ta_dev")
    ui.foot("Zero reference · positive = warmer than report median · red = ANOMALY · grey = cannot calculate")

# --------------------------------------------------------------- callout --
flag = sel[sel["ANOMALY_STATUS"] == ANOMALY]
n_valid_norm = int((sel["ANOMALY_STATUS"] == NORMAL).sum())
if len(flag):
    names = ", ".join(f"CYL{n}" for n in flag["Cylinder_No"])
    detail = "; ".join(f"CYL{r.Cylinder_No}: deviation {r.CYLINDER_DEVIATION:+.1f} °C → Modified Z-Score "
                       f"{r.MODIFIED_Z_SCORE:.2f}" for r in flag.itertuples())
    ui.callout(f"Selected report · {names} {'is' if len(flag) == 1 else 'are'} flagged under the historical baseline.",
               f"{detail}. The other {n_valid_norm} calculable observations are NORMAL. "
               "A statistical flag does not by itself establish engine damage — verify with engine data.",
               bad=True)
elif n_valid_norm:
    ui.callout("Selected report · no cylinder exceeds the threshold.",
               f"All {n_valid_norm} calculable observations have |Modified Z| ≤ {P.z_threshold}.")
else:
    ui.callout("Selected report · anomaly score unavailable.",
               "None of the cylinders could be scored (insufficient data or MAD = 0). "
               "No status is fabricated.")

# ---------------------------------------------------------- results table --
with st.container(border=True):
    ui.card_title("Thermal Anomaly Results Table",
                  "One row per report × cylinder · sorted by report date")
    f1, f2 = st.columns([2.2, 1])
    q = f1.text_input("Search", placeholder="Search date, vessel, voyage or cylinder",
                      label_visibility="collapsed", key="ta_search")
    status_f = f2.selectbox("Status", ["All statuses", ANOMALY, NORMAL, NOT_VALID],
                            label_visibility="collapsed", key="ta_status")
    tbl = cyl.assign(
        Cylinder="CYL" + cyl["Cylinder_No"].astype(str),
        Reason=cyl["STATUS_REASON"].map(REASON_TEXT).fillna(cyl["STATUS_REASON"]),
    )
    if status_f != "All statuses":
        tbl = tbl[tbl["ANOMALY_STATUS"] == status_f]
    if q:
        hay = (tbl["REPORT_DATE"].dt.strftime("%Y-%m-%d") + " " + tbl["Voyage_Label"].astype(str) + " "
               + tbl["VESSEL_NAME"].astype(str) + " " + tbl["Vessel_Key"].astype(str) + " " + tbl["Cylinder"])
        tbl = tbl[hay.str.contains(q, case=False, regex=False, na=False)]

    cols = ["REPORT_DATE", "VESSEL_NAME", "Voyage_Label", "Cylinder", "RPM", "RPM_GROUP", "EGT", "MEDIAN_EGT",
            "CYLINDER_DEVIATION", "BASELINE_N", "BASELINE_MEDIAN_DEV", "MAD", "MODIFIED_Z_SCORE",
            "ANOMALY_STATUS", "Reason"]
    for c in ("RPM", "RPM_GROUP"):          # data ETL versi lama belum punya kolom ini
        if c not in tbl.columns:
            tbl[c] = None
    tbl = tbl[cols]
    max_rows = get_app_settings().max_table_rows
    shown = tbl.head(max_rows)
    cfg = {
        "REPORT_DATE": st.column_config.DatetimeColumn("REPORT_DATE", format="YYYY-MM-DD"),
        "VESSEL_NAME": "Vessel", "Voyage_Label": "Voyage",
        "RPM": st.column_config.NumberColumn("RPM", format="%.1f"),
        "RPM_GROUP": "RPM range",
        "EGT": st.column_config.NumberColumn("EXHAUST_TEMP (°C)", format="%.1f"),
        "MEDIAN_EGT": st.column_config.NumberColumn("MEDIAN_EGT (°C)", format="%.1f"),
        "CYLINDER_DEVIATION": st.column_config.NumberColumn("CYLINDER_DEVIATION (°C)", format="%+.1f"),
        "BASELINE_N": st.column_config.NumberColumn("BASELINE_N", format="%d"),
        "BASELINE_MEDIAN_DEV": st.column_config.NumberColumn("BASELINE_MEDIAN_DEV (°C)", format="%+.2f"),
        "MAD": st.column_config.NumberColumn("MAD (°C)", format="%.2f"),
        "MODIFIED_Z_SCORE": st.column_config.NumberColumn("MODIFIED_Z_SCORE", format="%.2f"),
        "ANOMALY_STATUS": "ANOMALY_STATUS",
    }
    # Styler (badge warna) hanya untuk tabel berukuran wajar agar tetap cepat
    if len(shown) <= 3000:
        body = (shown.style
                .map(ui.status_style, subset=["ANOMALY_STATUS"])
                .format({"REPORT_DATE": lambda d: d.strftime("%Y-%m-%d") if pd.notna(d) else "—",
                         "RPM": "{:.1f}", "EGT": "{:.1f}", "MEDIAN_EGT": "{:.1f}", "CYLINDER_DEVIATION": "{:+.1f}",
                         "BASELINE_N": "{:.0f}", "BASELINE_MEDIAN_DEV": "{:+.2f}", "MAD": "{:.2f}",
                         "MODIFIED_Z_SCORE": "{:.2f}"}, na_rep="—"))
    else:
        body = shown
    st.dataframe(body, hide_index=True, width="stretch", height=430, column_config=cfg)
    ui.foot(f"{len(shown):,} of {len(tbl):,} rows displayed"
            + (f" (first {max_rows:,}; download CSV for all)" if len(tbl) > max_rows else ""))
    st.download_button("Download results (CSV)", tbl.to_csv(index=False).encode("utf-8"),
                       file_name="thermal_anomaly_results.csv", mime="text/csv",
                       icon=":material/download:")

# ------------------------------------------------------ calculation context --
st.write("")
with st.container(border=True):
    ui.card_title("Calculation context", "How every status in this page is produced")
    a, b = st.columns(2)
    with a:
        st.markdown(
            "**Pipeline** · Historical EGT → Data Validation → Median EGT → Cylinder Deviation → "
            "Historical Baseline → MAD → Modified Z-Score → NORMAL / ANOMALY")
        st.latex(r"D_i = EGT_i - \operatorname{Median}(EGT_1,\ldots,EGT_8)")
        st.latex(r"MAD = \operatorname{Median}\left(|B - \operatorname{Median}(B)|\right)")
        st.latex(r"MZ_i = \frac{0.6745\,(D_i - \operatorname{Median}(B))}{MAD}")
        st.latex(r"Status_i = \begin{cases}\text{ANOMALY}, & |MZ_i| > 3.5\\ "
                 r"\text{NORMAL}, & |MZ_i| \le 3.5\end{cases}")
    with b:
        st.markdown(
            f"""
- **Valid EGT**: {P.egt_valid_min:.0f}–{P.egt_valid_max:.0f} °C. Value 0 / NULL = not reported (e.g. a
  6-cylinder engine reports CYL7–8 as 0) and is excluded, never treated as a temperature.
- EGT is also treated as invalid when the report's **RPM = 0** (an engine that is stopped has no exhaust gas).
- **Validation**: a report is analysed only if it has ≥ **{P.min_valid_cylinders} valid cylinders** and **RPM > 0**.
- **Historical baseline B** = valid deviations of the **{BASELINE_TXT}**, strictly *before* the report being
  scored (comparable operating condition, no look-ahead, no mixing of cylinders or vessels).
- At least **{P.min_baseline_obs}** baseline values are required.
- **DATA_NOT_VALID** when the data does not meet the calculation criteria (EGT/RPM missing, < 4 valid cylinders, baseline too small or MAD = 0) — a status is never fabricated.
- A report is ANOMALY when ≥ 1 cylinder is ANOMALY.
- Cylinders that never report a valid EGT on a vessel (e.g. CYL7–8 on a 6-cylinder engine) are
  treated as not installed and are not listed.
""")
        if len(flag):
            r = flag.iloc[0]
            st.markdown(
                f"**Worked example – CYL{int(r['Cylinder_No'])}, {rep['REPORT_DATE']:%d %b %Y}**  \n"
                f"D = {r['EGT']:.1f} − {r['MEDIAN_EGT']:.1f} = **{r['CYLINDER_DEVIATION']:+.2f} °C** · "
                f"Median(B) = {r['BASELINE_MEDIAN_DEV']:+.2f} · MAD = {r['MAD']:.2f} "
                f"(n = {int(r['BASELINE_N'])})  \n"
                f"MZ = 0.6745 × ({r['CYLINDER_DEVIATION']:+.2f} − {r['BASELINE_MEDIAN_DEV']:+.2f}) / "
                f"{r['MAD']:.2f} = **{r['MODIFIED_Z_SCORE']:.2f}** → |MZ| > {P.z_threshold} → **ANOMALY**")

ui.page_footer(PAGE)