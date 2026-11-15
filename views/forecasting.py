"""Halaman: Forecasting konsumsi bahan bakar main engine (Double Exponential Smoothing / Holt)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics.forecast import run_forecast
from config.settings import get_analytics_settings
from services import data
from services.data import ALL
from ui import charts, theme
from ui import components as ui
from ui.layout import dataset_chip, require_warehouse

PAGE = "Forecasting"
A = get_analytics_settings()

ui.topbar(PAGE)
require_warehouse(PAGE)
ui.page_header("Fuel Consumption Forecasting",
               "Monthly main engine fuel consumption (ME_MFO_CONS + ME_MDO_CONS) forecast with "
               "Double Exponential Smoothing (Holt)", dataset_chip())

# ------------------------------------------------------------------ filter --
opts = data.filter_options()
vessels = opts["vessels"]
names = dict(zip(vessels["Vessel_Key"], vessels["NAME"].fillna("")))
with st.container(border=True):
    c1, c2, c3 = st.columns([1.6, 1, 1], vertical_alignment="bottom")
    vessel = c1.selectbox("Scope", [ALL, *vessels["Vessel_Key"].tolist()], key="fc_vessel",
                          format_func=lambda k: "All Vessels (fleet)" if k == ALL else f"{names.get(k, '')} ({k})")
    horizon = c2.number_input("Forecast horizon (months)", 1, 12, int(A.forecast_horizon), key="fc_h")
    test_m = c3.number_input("Test months (MAPE)", 2, 6, int(A.forecast_test_months), key="fc_test")

ui.note("Value per month = average ME fuel consumption per valid noon report (≈ MT per day) · valid = RPM > 0, "
        f"consumption > 0 and ≤ {A.fuel_valid_max:g} MT · source: dw.FACT_NOON_REPORT")

monthly = data.fuel_monthly(vessel)
res = run_forecast(monthly, horizon=int(horizon), test_months=int(test_m),
                   min_reports=int(A.forecast_min_reports)) if not monthly.empty else None
if res is None:
    ui.empty_state("Not enough monthly data to build a forecast for this scope "
                   f"(need at least {int(test_m) + 6} months with ≥ {A.forecast_min_reports} valid reports).")
    ui.page_footer(PAGE)
    st.stop()

if vessel != ALL:
    st.caption(":orange[Per-vessel consumption follows each vessel's voyage schedule and is much more "
               "volatile than the fleet series, so the forecast error is usually higher. "
               "The fleet scope is the main forecast used in this study.]")

# -------------------------------------------------------------------- KPIs --
next_fc = res.forecast.iloc[0]
last = res.history.iloc[-1]
k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.kpi(f"Forecast {next_fc['period']:%b %Y}", f"{next_fc['forecast']:.2f} MT",
           "average ME consumption per report")
with k2:
    chg = (next_fc["forecast"] - last["value"]) / last["value"] * 100 if last["value"] else 0
    ui.kpi(f"Last actual ({last['period']:%b %Y})", f"{last['value']:.2f} MT", f"{chg:+.1f}% to next forecast")
with k3:
    ui.kpi("MAPE (test)", f"{res.mape:.2f}%", f"{res.rating} · last {int(test_m)} months")
with k4:
    ui.kpi("MAE (test)", f"{res.mae:.2f} MT", f"α = {res.alpha:.2f} · β = {res.beta:.2f}")
st.write("")

# ------------------------------------------------------------------- chart --
with st.container(border=True):
    ui.card_title("Main engine fuel consumption · history and forecast",
                  "Monthly average per valid noon report · dashed = forecast · dotted = model fit")
    fig = go.Figure()
    h = res.history
    fig.add_trace(go.Scatter(x=h["period"], y=h["value"], name="Actual", mode="lines+markers",
                             line=dict(color=theme.PRIMARY, width=2), marker=dict(size=5),
                             customdata=h["reports"],
                             hovertemplate="%{x|%b %Y}: %{y:.2f} MT<br>%{customdata} reports<extra>Actual</extra>"))
    fig.add_trace(go.Scatter(x=list(res.fitted.index), y=res.fitted.values, name="Holt fit", mode="lines",
                             line=dict(color=theme.PRIMARY_LIGHT, width=1.5, dash="dot"),
                             hovertemplate="%{x|%b %Y}: %{y:.2f} MT<extra>Fit</extra>"))
    fx = [h["period"].iloc[-1], *res.forecast["period"]]
    fy = [h["value"].iloc[-1], *res.forecast["forecast"]]
    fig.add_trace(go.Scatter(x=fx, y=fy, name="Forecast", mode="lines+markers",
                             line=dict(color=theme.BAD_FG, width=2, dash="dash"), marker=dict(size=6),
                             hovertemplate="%{x|%b %Y}: %{y:.2f} MT<extra>Forecast</extra>"))
    fig.add_trace(go.Scatter(x=res.test["period"], y=res.test["forecast"], name="Test forecast",
                             mode="markers", marker=dict(color="#8C7AA9", size=8, symbol="x"),
                             hovertemplate="%{x|%b %Y}: %{y:.2f} MT<extra>Test forecast</extra>"))
    fig = charts._base(fig, 380, "MT per report")
    fig.update_xaxes(tickformat="%b %Y")
    charts.show(fig, key="fc_chart")
    for n in res.notes:
        ui.foot(n)

# ------------------------------------------------------------------ tables --
c1, c2 = st.columns(2)
with c1, st.container(border=True):
    ui.card_title("Forecast", f"Next {int(horizon)} month(s)")
    st.dataframe(res.forecast.assign(Month=res.forecast["period"].dt.strftime("%b %Y"))[["Month", "forecast"]],
                 hide_index=True, width="stretch",
                 column_config={"forecast": st.column_config.NumberColumn("Forecast (MT / report)", format="%.2f")})
with c2, st.container(border=True):
    ui.card_title("Model evaluation", f"Trained without the last {int(test_m)} months, then compared")
    t = res.test.assign(Month=res.test["period"].dt.strftime("%b %Y"),
                        error_pct=lambda d: (d["actual"] - d["forecast"]).abs() / d["actual"] * 100)
    st.dataframe(t[["Month", "actual", "forecast", "error_pct"]], hide_index=True, width="stretch",
                 column_config={"actual": st.column_config.NumberColumn("Actual", format="%.2f"),
                                "forecast": st.column_config.NumberColumn("Forecast", format="%.2f"),
                                "error_pct": st.column_config.NumberColumn("|Error| %", format="%.2f")})

with st.expander("Monthly data used", icon=":material/table_view:"):
    st.dataframe(monthly, hide_index=True, width="stretch",
                 column_config={"Avg_Cons": st.column_config.NumberColumn("Avg ME cons / report", format="%.2f"),
                                "Total_Cons": st.column_config.NumberColumn("Total ME cons (MT)", format="%.2f")})

# ------------------------------------------------------ calculation context --
st.write("")
with st.container(border=True):
    ui.card_title("Calculation context", "Double Exponential Smoothing (Holt) and error metrics")
    a, b = st.columns(2)
    with a:
        st.latex(r"y_t = \frac{\sum (ME\_MFO\_CONS + ME\_MDO\_CONS)}{n_{\text{valid reports}}}")
        st.latex(r"L_t = \alpha\,y_t + (1-\alpha)(L_{t-1} + T_{t-1})")
        st.latex(r"T_t = \beta\,(L_t - L_{t-1}) + (1-\beta)\,T_{t-1}")
        st.latex(r"F_{t+m} = L_t + m\,T_t")
    with b:
        st.latex(r"MAE = \frac{1}{n}\sum |y_t - F_t|")
        st.latex(r"MAPE = \frac{100\%}{n}\sum \left|\frac{y_t - F_t}{y_t}\right|")
        st.markdown(
            f"""
- Initial values: L₁ = y₁, T₁ = y₂ − y₁. α and β are chosen by grid search (0.05–0.95) minimising SSE.
- Selected: **α = {res.alpha:.2f}**, **β = {res.beta:.2f}**.
- MAPE scale (Lewis, 1982): < 10% very good · 10–20% good · 20–50% reasonable · > 50% poor.
- Reports with RPM = 0, zero consumption or consumption > {A.fuel_valid_max:g} MT (input error) are excluded.
- MFO and MDO are added because vessels switch between the two fuels.
""")

ui.page_footer(PAGE)