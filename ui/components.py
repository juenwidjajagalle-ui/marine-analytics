"""Komponen UI reusable (HTML ringan + elemen Streamlit)."""
from __future__ import annotations

import html
from typing import Iterable

import pandas as pd
import streamlit as st

from config.settings import get_app_settings
from ui import theme


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def md(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def topbar(page: str) -> None:
    md(f"""<div class="mbi-topbar">
      <div class="mbi-crumb">Analytics<span class="sep">›</span><b>{_e(page)}</b></div>
      <div class="mbi-top-right"><span>HISTORICAL WORKSPACE</span>
        <span class="mbi-version">{_e(get_app_settings().version_label)}</span></div></div>""")


def page_header(title: str, subtitle: str, chip: str | None = None) -> None:
    chip_html = f'<div class="mbi-chip">{_e(chip)}</div>' if chip else ""
    md(f"""<div class="mbi-head"><div><h1>{_e(title)}</h1><p>{_e(subtitle)}</p></div>{chip_html}</div>""")


def note(text: str) -> None:
    md(f'<div class="mbi-note">{_e(text)}</div>')


def section(text: str) -> None:
    md(f'<div class="mbi-section">{_e(text)}</div>')


def kpi(label: str, value: str, caption: str = "") -> None:
    md(f"""<div class="mbi-kpi"><div class="l">{_e(label)}</div>
        <div class="v">{_e(value)}</div><div class="c">{_e(caption)}</div></div>""")


def info_strip(items: Iterable[tuple[str, str]]) -> None:
    cells = "".join(f'<div><div class="l">{_e(k)}</div><div class="v" title="{_e(v)}">{_e(v)}</div></div>'
                    for k, v in items)
    md(f'<div class="mbi-strip">{cells}</div>')


def card_title(title: str, subtitle: str = "", badge: str | None = None) -> None:
    b = f'<span class="mbi-badge blue" style="float:right">{_e(badge)}</span>' if badge else ""
    md(f'{b}<div class="mbi-card-title">{_e(title)}</div><div class="mbi-card-sub">{_e(subtitle)}</div>')


def foot(text: str) -> None:
    md(f'<div class="mbi-foot">{_e(text)}</div>')


def callout(title: str, body: str, bad: bool = False) -> None:
    md(f"""<div class="mbi-callout{' bad' if bad else ''}"><div class="t">{_e(title)}</div>
        <div class="b">{_e(body)}</div></div>""")


def cylinder_tiles(values: list, statuses: list[str] | None = None) -> None:
    statuses = statuses or [""] * len(values)
    cells = []
    for i, (v, s) in enumerate(zip(values, statuses), start=1):
        cls = "bad" if s == "ANOMALY" else ("na" if v is None or pd.isna(v) else "")
        txt = "—" if v is None or pd.isna(v) else f"{v:.0f}"
        cells.append(f'<div class="{cls}"><div class="n">CYL{i}</div><div class="t">{txt}</div></div>')
    md(f'<div class="mbi-cyl">{"".join(cells)}</div>')


def completeness_grid(rows: pd.DataFrame) -> None:
    cells = []
    for _, r in rows.iterrows():
        pct_valid = (r["N_Valid"] / r["N_Total"] * 100) if r["N_Total"] else 0
        extra = f" · {int(r['N_Invalid'])} invalid" if r["N_Invalid"] else ""
        cells.append(
            f'<div><div class="l">{_e(r["Variable"])}</div>'
            f'<div class="v">{int(r["N_Valid"]):,} / {int(r["N_Total"]):,} valid'
            f'<span>{r["Missing_Pct"]:.1f}% missing{_e(extra)}</span></div>'
            f'<div class="mbi-bar"><i style="width:{pct_valid:.1f}%"></i></div></div>')
    md(f'<div class="mbi-comp">{"".join(cells)}</div>')


def page_footer(page: str) -> None:
    md(f"""<div class="mbi-pagefoot"><span>{_e(get_app_settings().app_name)} · Historical analysis</span>
        <span>{_e(get_app_settings().version_label.title())} / {_e(page)}</span></div>""")


def empty_state(message: str) -> None:
    st.info(message, icon=":material/info:")


# ------------------------------------------------------------ formatting ---
def fmt_num(v, d: int = 2) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.{d}f}"


def txt(v) -> str:
    return "—" if v is None or (not isinstance(v, str) and pd.isna(v)) or str(v).strip() == "" else str(v)


def fmt_date_range(start, end) -> str:
    if start is None or end is None:
        return "—"
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if s.year == e.year and s.month == e.month:
        return f"{s:%d}–{e:%d %b %Y}"
    if s.year == e.year:
        return f"{s:%d %b}–{e:%d %b %Y}"
    return f"{s:%d %b %Y}–{e:%d %b %Y}"


def status_style(v: str) -> str:
    return {
        "ANOMALY": f"background-color:{theme.BAD_BG};color:{theme.BAD_FG};font-weight:700",
        "NORMAL": f"background-color:{theme.OK_BG};color:{theme.OK_FG};font-weight:700",
        "DATA_NOT_VALID": f"background-color:{theme.NA_BG};color:{theme.NA_FG};font-weight:700",
    }.get(v, "")