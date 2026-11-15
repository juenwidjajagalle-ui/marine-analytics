"""Chart Plotly dengan gaya konsisten sesuai desain (bersih, garis tipis, grid halus)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import theme

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


def _base(fig: go.Figure, height: int, y_title: str = "", legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=28 if legend else 8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=theme.FONT, size=11, color=theme.MUTED),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified", hoverlabel=dict(font_size=11, font_family=theme.FONT),
    )
    fig.update_xaxes(showgrid=False, linecolor=theme.BORDER, tickformat="%d %b", ticks="")
    fig.update_yaxes(gridcolor=theme.GRID, zeroline=False, title=dict(text=y_title, font=dict(size=10)))
    return fig


def show(fig: go.Figure, key: str | None = None) -> None:
    st.plotly_chart(fig, config=PLOTLY_CONFIG, width="stretch", key=key)


def line_chart(df: pd.DataFrame, x: str, series: list[tuple[str, str, str]],
               y_title: str = "", height: int = 250, tickformat: str = "%d %b") -> go.Figure:
    """series: list (kolom, label, warna)."""
    fig = go.Figure()
    for col, label, color in series:
        if col not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=df[x], y=df[col], name=label, mode="lines+markers" if len(df) <= 45 else "lines",
            line=dict(color=color, width=2), marker=dict(size=4), connectgaps=False,
            hovertemplate="%{y:,.2f}<extra>" + label + "</extra>"))
    fig = _base(fig, height, y_title, legend=len(series) > 1)
    fig.update_xaxes(tickformat=tickformat)
    return fig


def egt_chart(df: pd.DataFrame, x: str, cyl_cols: list[str], height: int = 300,
              anomalies: pd.DataFrame | None = None, selected_date=None) -> go.Figure:
    """Garis EGT per silinder + penanda ANOMALY (merah) + garis tanggal laporan terpilih.

    anomalies: kolom x, EGT, Cylinder_No, VESSEL_NAME, CYLINDER_DEVIATION, MODIFIED_Z_SCORE."""
    fig = go.Figure()
    for i, col in enumerate(cyl_cols):
        if col not in df.columns or df[col].notna().sum() == 0:
            continue  # silinder tidak terpasang / tanpa data tidak ditampilkan di legenda
        fig.add_trace(go.Scatter(
            x=df[x], y=df[col], name=f"CYL{i + 1}", mode="lines",
            line=dict(color=theme.CYL_COLORS[i % len(theme.CYL_COLORS)], width=1.8),
            hovertemplate="%{y:.1f} °C<extra>CYL" + str(i + 1) + "</extra>"))
    if anomalies is not None and len(anomalies):
        a = anomalies
        fig.add_trace(go.Scatter(
            x=a[x], y=a["EGT"], name=f"Anomaly ({len(a)})", mode="markers",
            marker=dict(color=theme.BAD_FG, size=11, symbol="circle-open", line=dict(width=2.5)),
            customdata=[[int(c), str(v or ""), float(dv), float(z)] for c, v, dv, z in zip(
                a["Cylinder_No"], a["VESSEL_NAME"].fillna(""), a["CYLINDER_DEVIATION"], a["MODIFIED_Z_SCORE"])],
            hovertemplate=("<b>ANOMALY</b> · %{customdata[1]} CYL%{customdata[0]}<br>"
                           "EGT %{y:.1f} °C · deviation %{customdata[2]:+.1f} °C<br>"
                           "Modified Z %{customdata[3]:.2f}<extra></extra>")))
    if selected_date is not None:
        fig.add_vline(x=pd.Timestamp(selected_date).to_pydatetime(), line=dict(color="#9AA7B8", width=1.2, dash="dot"))
    return _base(fig, height, "°C")


def deviation_bar(labels: list[str], dev: list, status: list[str], height: int = 300) -> go.Figure:
    colors = [theme.BAD_FG if s == "ANOMALY" else ("#B8C2CF" if s == "DATA_NOT_VALID" else theme.PRIMARY)
              for s in status]
    text = ["—" if pd.isna(v) else f"{v:+.1f}" for v in dev]
    fig = go.Figure(go.Bar(
        x=labels, y=[0 if pd.isna(v) else v for v in dev], marker_color=colors, text=text,
        textposition="outside", cliponaxis=False, width=0.45,
        customdata=status, hovertemplate="%{x}: %{y:+.1f} °C<br>%{customdata}<extra></extra>"))
    fig = _base(fig, height, "°C", legend=False)
    fig.update_yaxes(zeroline=True, zerolinecolor="#9AA7B8", zerolinewidth=1)
    fig.update_xaxes(tickformat=None, type="category")
    fig.update_layout(hovermode="closest")
    return fig


def valid_positions(df: pd.DataFrame) -> pd.DataFrame:
    """Baris dengan koordinat yang masuk akal (bukan NULL, bukan 0/0, dalam rentang bumi)."""
    lat, lon = df["LATITUDE"], df["LONGITUDE"]
    ok = (lat.notna() & lon.notna() & lat.between(-90, 90) & lon.between(-180, 180)
          & ~((lat == 0) & (lon == 0)))
    return df[ok]


def _auto_view(lat: pd.Series, lon: pd.Series) -> tuple[dict, float]:
    """Titik tengah & zoom agar semua posisi terlihat."""
    import math
    span = max(lon.max() - lon.min(), (lat.max() - lat.min()) * 1.6, 0.05)
    zoom = max(0.6, min(9.0, math.log2(360 / span) - 0.6))
    return dict(lat=float((lat.max() + lat.min()) / 2), lon=float((lon.max() + lon.min()) / 2)), zoom


def vessel_map(df: pd.DataFrame, selected_key=None, height: int = 430,
               speed_col: str = "SPEED_OVER_GROUND") -> go.Figure | None:
    """Peta posisi noon report: 1 garis lintasan per kapal (urut REPORT_DATE),
    lingkaran merah = laporan ANOMALY, bintang = laporan terpilih, label = posisi terakhir."""
    pos = valid_positions(df).sort_values("REPORT_DATE")
    if pos.empty:
        return None
    fig = go.Figure()
    for i, (vk, g) in enumerate(pos.groupby("Vessel_Key", sort=False)):
        color = theme.CYL_COLORS[i % len(theme.CYL_COLORS)]
        name = str(g["VESSEL_NAME"].dropna().iloc[0]) if g["VESSEL_NAME"].notna().any() else str(vk)
        speed = g[speed_col] if speed_col in g.columns else pd.Series(index=g.index, dtype=float)
        fig.add_trace(go.Scattermap(
            lat=g["LATITUDE"], lon=g["LONGITUDE"], mode="lines+markers", name=name,
            line=dict(width=2, color=color), marker=dict(size=6, color=color),
            customdata=list(zip(g["REPORT_DATE"].dt.strftime("%d %b %Y %H:%M"),
                                speed.map(lambda v: f"{v:.1f}" if pd.notna(v) else "—"),
                                g["NEXT_PORT"].fillna("—"), g["Anomaly_Status"].fillna("—"))),
            hovertemplate=(f"<b>{name}</b><br>%{{customdata[0]}}<br>"
                           "Lat %{lat:.3f} · Lon %{lon:.3f}<br>Speed %{customdata[1]} kn · "
                           "Next port: %{customdata[2]}<br>Thermal status: %{customdata[3]}<extra></extra>")))
        last = g.iloc[-1]
        fig.add_trace(go.Scattermap(
            lat=[last["LATITUDE"]], lon=[last["LONGITUDE"]], mode="markers+text", showlegend=False,
            marker=dict(size=12, color=color), text=[name], textposition="top right",
            textfont=dict(size=11, color=theme.TEXT), hoverinfo="skip"))
    anom = pos[pos["Anomaly_Status"] == "ANOMALY"]
    if len(anom):
        fig.add_trace(go.Scattermap(
            lat=anom["LATITUDE"], lon=anom["LONGITUDE"], mode="markers", name=f"Thermal anomaly ({len(anom)})",
            marker=dict(size=13, color=theme.BAD_FG, opacity=0.55),
            customdata=list(zip(anom["VESSEL_NAME"].fillna(anom["Vessel_Key"]),
                                anom["REPORT_DATE"].dt.strftime("%d %b %Y"))),
            hovertemplate="<b>ANOMALY</b> · %{customdata[0]}<br>%{customdata[1]}<extra></extra>"))
    sel = pos[pos["Noon_Report_Key"] == selected_key] if selected_key is not None else pos.iloc[0:0]
    if len(sel):
        fig.add_trace(go.Scattermap(
            lat=sel["LATITUDE"], lon=sel["LONGITUDE"], mode="markers", name="Selected report",
            marker=dict(size=20, color=theme.NAVY, symbol="circle"),
            hovertemplate="<b>Selected report</b><extra></extra>"))
    center, zoom = _auto_view(pos["LATITUDE"], pos["LONGITUDE"])
    fig.update_layout(
        map=dict(style="carto-positron", center=center, zoom=zoom),
        height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=theme.FONT, size=11, color=theme.MUTED),
        legend=dict(orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.01,
                    bgcolor="rgba(255,255,255,0.85)", font=dict(size=10)),
        hoverlabel=dict(font_size=11, font_family=theme.FONT))
    return fig


MAP_CONFIG = {"displayModeBar": True, "displaylogo": False, "scrollZoom": True,
              "modeBarButtonsToRemove": ["select2d", "lasso2d", "toImage"], "responsive": True}


def show_map(fig: go.Figure, key: str | None = None) -> None:
    st.plotly_chart(fig, config=MAP_CONFIG, width="stretch", key=key)


def bar_chart(df: pd.DataFrame, x: str, y: str, label: str, color: str = theme.PRIMARY,
              height: int = 260, horizontal: bool = False, y_title: str = "") -> go.Figure:
    if horizontal:
        fig = go.Figure(go.Bar(x=df[y], y=df[x], orientation="h", marker_color=color, name=label,
                               hovertemplate="%{y}: %{x:,.2f}<extra></extra>"))
        fig = _base(fig, height, "", legend=False)
        fig.update_yaxes(autorange="reversed", showgrid=False, type="category")
        fig.update_xaxes(showgrid=True, gridcolor=theme.GRID, tickformat=None, title=y_title)
    else:
        fig = go.Figure(go.Bar(x=df[x], y=df[y], marker_color=color, name=label,
                               hovertemplate="%{x}: %{y:,.0f}<extra></extra>"))
        fig = _base(fig, height, y_title, legend=False)
        fig.update_xaxes(tickformat=None, type="category")
    fig.update_layout(hovermode="closest")
    return fig