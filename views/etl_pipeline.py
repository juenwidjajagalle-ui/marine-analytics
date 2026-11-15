"""Halaman: ETL Pipeline — menjalankan Extract → Transform → Load → Analyze dari web."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import get_analytics_settings, get_db_settings
from core import schema
from core.database import masked_connection_info, test_connection
from etl import load
from etl.pipeline import run_etl
from services import data
from ui import components as ui

PAGE = "ETL Pipeline"
DB = get_db_settings()
AN = get_analytics_settings()

ui.topbar(PAGE)
ui.page_header("ETL Pipeline", "Extract noon reports from SQL Server, build the star schema and score thermal anomalies",
               f"{DB.database} · schema {DB.dw_schema}")

st.markdown("""
<div class="mbi-formula">
<b>EXTRACT</b> dbo.NOON_REPORT_COPY · dbo.V_Voyages · dbo.vessels &nbsp;→&nbsp;
<b>TRANSFORM</b> clean types, sentinel dates, '31° C' → 31, EGT validation, keys &nbsp;→&nbsp;
<b>LOAD</b> dw.DIM_DATE · DIM_VESSEL · DIM_VOYAGE · FACT_NOON_REPORT &nbsp;→&nbsp;
<b>ANALYZE</b> Median EGT → Deviation → MAD → Modified Z → dw.FACT_CYLINDER_ANOMALY
</div>""", unsafe_allow_html=True)
st.write("")

# ------------------------------------------------------------ connection --
c1, c2 = st.columns([1.3, 1])
with c1, st.container(border=True):
    ui.card_title("Connection", "From .streamlit/secrets.toml or environment variables")
    info = masked_connection_info(DB)
    st.dataframe(pd.DataFrame(info.items(), columns=["Setting", "Value"]), hide_index=True, width="stretch")
    b1, b2, b3 = st.columns(3)
    if b1.button("Test connection", icon=":material/lan:", width="stretch"):
        try:
            res = test_connection(data.get_engine())
            st.success(f"Connected to {res['server_name']} / {res['db_name']} · SQL Server "
                       f"{res['version']} ({res['edition']})")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Connection failed: {exc}")
    if b2.button("Create / verify schema", icon=":material/schema:", width="stretch"):
        try:
            load.ensure_warehouse(data.get_engine(), DB.dw_schema)
            data.clear_caches()
            st.success(f"Star schema [{DB.dw_schema}] is ready.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed: {exc}")
    b3.download_button("DDL (.sql)", schema.ddl_script(DB.dw_schema, DB.database).encode("utf-8"),
                       file_name="create_warehouse.sql", mime="text/plain", icon=":material/download:",
                       width="stretch")

with c2, st.container(border=True):
    ui.card_title("Analysis parameters", "config/settings.py · override in secrets.toml [analytics]")
    params = pd.DataFrame([
        ("Valid EGT range", f"{AN.egt_valid_min:g}–{AN.egt_valid_max:g} °C"),
        ("Min valid cylinders / report", AN.min_valid_cylinders),
        ("Baseline grouping", f"vessel + cylinder + RPM range ({AN.rpm_bin_width:g} RPM)"
         if AN.baseline_mode == "rpm_bin" else "vessel + cylinder"),
        ("Baseline window", f"last {AN.baseline_window} valid deviations"),
        ("Min baseline observations", AN.min_baseline_obs),
        ("Modified Z constant", AN.z_constant),
        ("Anomaly threshold", f"|MZ| > {AN.z_threshold}"),
        ("Hide cylinders never reported on a vessel", AN.drop_uninstalled_cylinders),
        ("EGT invalid when RPM = 0", AN.egt_requires_rpm),
        ("Operational speed column (dashboard)", AN.speed_column),
        ("Load only active, non-archived reports", AN.only_active_reports),
    ], columns=["Parameter", "Value"])
    params["Value"] = params["Value"].astype(str)
    st.dataframe(params, hide_index=True, width="stretch")

# ------------------------------------------------------------------- run --
st.write("")
with st.container(border=True):
    ui.card_title("Run ETL", "Incremental loads only rows created/modified after the last watermark")
    m1, m2 = st.columns([2, 1], vertical_alignment="bottom")
    mode = m1.radio("Mode", ["incremental", "full"], horizontal=True, key="etl_mode",
                    format_func=lambda m: "Incremental (recommended daily)" if m == "incremental"
                    else "Full reload (rebuild everything)")
    try:
        wm = load.get_watermark(data.get_engine(), DB.dw_schema)
    except Exception:  # noqa: BLE001
        wm = None
    m1.caption(f"Current watermark: **{wm or 'none — first run will be a full load'}**")
    confirm = True
    if mode == "full":
        confirm = m1.checkbox("I understand a full reload truncates and rebuilds the fact tables.",
                              key="etl_confirm")
    run = m2.button("Run ETL", type="primary", icon=":material/play_arrow:", width="stretch",
                    disabled=not confirm)

    if run:
        bar = st.progress(0.0, text="Starting…")
        with st.status("Running ETL…", expanded=True) as status:
            def progress(msg: str, pct: float) -> None:
                bar.progress(min(max(pct, 0.0), 1.0), text=msg)
                st.write(msg)
            result = run_etl(data.get_engine(), DB, AN, mode=mode, progress=progress)
            state = {"SUCCESS": "complete", "SKIPPED": "complete"}.get(result.status, "error")
            status.update(label=f"ETL {result.status} · {result.duration_s}s", state=state, expanded=False)
        data.clear_caches()
        st.session_state["last_etl"] = result

    result = st.session_state.get("last_etl")
    if result is not None:
        if result.status == "SUCCESS":
            st.success(result.message, icon=":material/check_circle:")
        elif result.status == "SKIPPED":
            st.warning(result.message)
        else:
            st.error(result.message)
        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric("Rows extracted", f"{result.rows_extracted:,}")
        r2.metric("Reports loaded", f"{result.rows_loaded:,}")
        r3.metric("Old versions replaced", f"{result.rows_removed:,}")
        r4.metric("Cylinder rows scored", f"{result.cylinder_rows:,}")
        r5.metric("Anomalies", f"{result.anomalies:,}")
        if result.dq:
            dq = {k: v for k, v in result.dq.items() if k != "max_change_ts"}
            labels = {
                "rows_extracted": "Rows extracted from source",
                "unparseable_numeric_values": "Numeric values that could not be parsed → NULL",
                "egt_zero_or_not_reported": "EGT values = 0 / not reported → NULL",
                "egt_out_of_range": f"EGT outside {AN.egt_valid_min:g}–{AN.egt_valid_max:g} °C → NULL",
                "egt_with_rpm_zero": "Reports with EGT but RPM = 0 → EGT set to NULL",
                "dropped_missing_id": "Rows dropped: missing ID_NOON_REPORT",
                "duplicate_ids_resolved": "Duplicate IDs resolved (latest kept)",
                "excluded_inactive_or_archived": "Inactive / archived reports excluded",
                "dropped_missing_report_date": "Rows dropped: missing REPORT_DATE",
                "reports_with_unknown_voyage": "Reports whose FID_VOYAGE is not in V_Voyages",
                "reports_with_vessel_not_in_master": "Reports whose vessel is not in vessels",
                "rows_loaded": "Rows loaded into FACT_NOON_REPORT",
            }
            st.markdown("**Data quality report**")
            st.dataframe(pd.DataFrame([(labels.get(k, k), v) for k, v in dq.items()],
                                      columns=["Check", "Count"]), hide_index=True, width="stretch")

# -------------------------------------------------------------- auto ETL --
st.write("")
with st.container(border=True):
    watcher = data.get_auto_etl()
    ui.card_title("Auto ETL", f"Watches [{DB.source_schema}].[{DB.source_noon_table}] and runs an incremental "
                              "ETL automatically when new or modified rows appear")
    if watcher is None:
        st.info("Auto ETL is disabled. Enable it in .streamlit/secrets.toml → `[auto_etl] enabled = true`, "
                "then restart Streamlit.")
    else:
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Status", "Error" if watcher.last_error else ("Running" if watcher.running else "Stopped"))
        a2.metric("Check interval", f"{watcher.interval} s")
        a3.metric("Last check", f"{watcher.last_check:%H:%M:%S}" if watcher.last_check else "—")
        a4.metric("Auto runs (this session)", f"{watcher.total_runs:,}")
        if watcher.last_run is not None:
            r = watcher.last_run
            st.caption(f"Last auto run · {watcher.last_run_at:%Y-%m-%d %H:%M:%S} · **{r.status}** · "
                       f"{r.rows_loaded:,} reports loaded · {r.anomalies:,} anomalies · {r.duration_s}s")
        if watcher.last_error:
            st.error(f"Last error: {watcher.last_error}")
        if st.button("Check for new data now", icon=":material/refresh:"):
            with st.spinner("Checking NOON_REPORT_COPY…"):
                before = watcher.data_version
                chk = watcher.tick()
            if chk is None:
                st.error(f"Check failed: {watcher.last_error}")
            elif chk.watermark is None:
                st.warning("No watermark yet — run a **Full reload** once first.")
            elif watcher.data_version != before:
                data.clear_caches()
                st.session_state["_auto_etl_seen"] = watcher.data_version
                st.success(f"{chk.new_rows:,} new/changed row(s) found and loaded "
                           f"(latest change {chk.latest_change}).")
            elif chk.new_rows == 0:
                st.success(f"No new data since the last ETL (watermark {chk.watermark}).")
            else:
                st.warning(f"{chk.new_rows:,} new row(s) found but the ETL did not succeed: "
                           f"{watcher.last_run.message.splitlines()[0] if watcher.last_run else '—'}")
        st.caption("Detection rule: a row is new when MAX(CREATED_DATE, MODIFIED_DATE) > watermark. "
                   "Dashboards refresh automatically after an auto run.")

# --------------------------------------------------------------- history --
st.write("")
with st.container(border=True):
    ui.card_title("Run history", f"[{DB.dw_schema}].[ETL_RUN_LOG] · latest 20")
    runs = data.etl_runs(20)
    if runs.empty:
        st.caption("No runs recorded yet.")
    else:
        st.dataframe(runs.drop(columns=["Message"], errors="ignore"), hide_index=True, width="stretch",
                     column_config={
                         "Started_At": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm:ss"),
                         "Finished_At": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm:ss"),
                     })

st.caption("Schedule it daily without the browser: `python -m scripts.run_etl --mode incremental` "
           "(Windows Task Scheduler). See README.md.")
ui.page_footer(PAGE)