"""Design tokens & CSS global mengikuti desain Marine BI Analytics (Version 2)."""
from __future__ import annotations

import streamlit as st

NAVY = "#15284A"
NAVY_2 = "#1F3A63"
PRIMARY = "#3A6EA5"
PRIMARY_LIGHT = "#7FA6CF"
BG = "#F4F6F9"
CARD = "#FFFFFF"
BORDER = "#E3E8EF"
TEXT = "#1E2A3B"
MUTED = "#6B7A90"
GRID = "#E9EDF2"
OK_BG, OK_FG = "#E7F4EC", "#1E7A46"
BAD_BG, BAD_FG = "#FCEBE7", "#C2410C"
NA_BG, NA_FG = "#EEF1F4", "#5E6B7C"
HIGHLIGHT = "#EAF2FB"

# 8 warna silinder: biru/teal/abu (senada dengan desain), cukup terbedakan
CYL_COLORS = ["#2F5F98", "#3E7C78", "#7FA6CF", "#4F5B6E", "#8C7AA9", "#1F4E5F", "#9AA7B8", "#B07D62"]

FONT = "Inter, 'Segoe UI', system-ui, -apple-system, sans-serif"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, .stApp, .stMarkdown, .stText, label, input, textarea, button, select,
[data-testid="stMarkdownContainer"] p {{ font-family: {FONT}; }}
.stApp {{ background: {BG}; color: {TEXT}; }}
header[data-testid="stHeader"] {{ background: transparent; height: 2.5rem; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1480px; }}

/* ------------------------------ sidebar ------------------------------ */
section[data-testid="stSidebar"] {{ background: {NAVY}; }}
section[data-testid="stSidebar"] * {{ color: #C9D4E5; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {{
    background: {NAVY_2}; border-radius: 8px;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] span {{
    color: #FFFFFF; font-weight: 600;
}}
section[data-testid="stSidebar"] [data-testid="stPageLink"] a {{ padding:.55rem .75rem; border-radius:8px; }}
section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{ background:{NAVY_2}; }}
section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {{
    background:{NAVY_2}; box-shadow: inset 3px 0 0 {PRIMARY_LIGHT};
}}
section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.12); }}
.mbi-side-foot {{ border-top: 1px solid rgba(255,255,255,.14); margin-top: 1.5rem; padding-top: 1rem; }}
.mbi-side-foot .t {{ color: #FFFFFF !important; font-weight: 600; font-size: .9rem; }}
.mbi-side-foot .s {{ color: #9FB0C9 !important; font-size: .82rem; margin-top: .25rem; }}
.mbi-side-foot .d {{ color: #9FB0C9 !important; font-size: .76rem; margin-top: .45rem; }}
.mbi-side-foot .d::before {{ content: "●"; color: {PRIMARY_LIGHT}; margin-right: .4rem; font-size: .6rem; }}

/* ------------------------------ topbar ------------------------------ */
.mbi-topbar {{ display:flex; justify-content:space-between; align-items:center;
    border-bottom:1px solid {BORDER}; padding: .2rem 0 .8rem 0; margin-bottom: 1.4rem; }}
.mbi-crumb {{ font-size:.85rem; color:{MUTED}; }}
.mbi-crumb b {{ color:{TEXT}; font-weight:500; }}
.mbi-crumb .sep {{ margin: 0 .6rem; color:#A8B3C2; }}
.mbi-top-right {{ font-size:.72rem; letter-spacing:.04em; color:{MUTED}; display:flex; gap:.9rem; align-items:center; }}
.mbi-version {{ background:#E4EEF9; color:{PRIMARY}; font-weight:700; padding:.25rem .55rem; border-radius:5px; }}

/* ------------------------------ header ------------------------------ */
.mbi-head {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 1.1rem; }}
.mbi-head h1 {{ font-size:1.95rem; font-weight:500; color:{TEXT}; margin:0; padding:0; letter-spacing:-.01em; }}
.mbi-head p {{ color:{MUTED}; margin:.35rem 0 0 0; font-size:.92rem; }}
.mbi-chip {{ background:#EAEEF3; color:{MUTED}; font-size:.72rem; padding:.3rem .55rem;
    border-radius:5px; white-space:nowrap; margin-top:.6rem; }}

/* ------------------------------ cards ------------------------------ */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background:{CARD}; border-color:{BORDER} !important; border-radius:10px;
}}
.mbi-card-title {{ font-weight:600; font-size:1rem; color:{TEXT}; margin:0; }}
.mbi-card-sub {{ color:{MUTED}; font-size:.78rem; margin:.15rem 0 .6rem 0; }}
.mbi-kpi {{ background:{CARD}; border:1px solid {BORDER}; border-radius:10px; padding:1.05rem 1.15rem; height:100%; }}
.mbi-kpi .l {{ color:{MUTED}; font-size:.82rem; }}
.mbi-kpi .v {{ color:{TEXT}; font-size:1.75rem; font-weight:700; margin:.35rem 0 .3rem 0; line-height:1.15; }}
.mbi-kpi .c {{ color:{MUTED}; font-size:.75rem; }}
.mbi-strip {{ background:{CARD}; border:1px solid {BORDER}; border-radius:8px; padding:.85rem 1rem;
    display:grid; grid-template-columns: repeat(4, 1fr); gap:1rem; }}
.mbi-strip .l {{ font-size:.68rem; font-weight:600; color:{MUTED}; letter-spacing:.03em; text-transform:uppercase; }}
.mbi-strip .v {{ font-size:.86rem; color:{TEXT}; margin-top:.25rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.mbi-note {{ color:{MUTED}; font-size:.82rem; margin:.2rem 0 1rem 0; display:flex; gap:.45rem; align-items:center; }}
.mbi-note::before {{ content:"i"; display:inline-flex; width:15px; height:15px; border:1.4px solid {PRIMARY};
    color:{PRIMARY}; border-radius:50%; font-size:.6rem; font-weight:700; align-items:center; justify-content:center; }}
.mbi-foot {{ color:{MUTED}; font-size:.74rem; margin-top:.3rem; }}
.mbi-section {{ font-weight:600; font-size:1rem; color:{TEXT}; margin:.6rem 0 .7rem 0; }}

.mbi-callout {{ background:{HIGHLIGHT}; border:1px solid #D3E2F3; border-radius:8px; padding:.85rem 1rem;
    margin: .4rem 0 1rem 0; }}
.mbi-callout.bad {{ background:#FDF3EF; border-color:#F3D5C8; }}
.mbi-callout .t {{ font-weight:600; font-size:.9rem; color:{TEXT}; }}
.mbi-callout .b {{ color:{MUTED}; font-size:.85rem; margin-top:.25rem; }}

.mbi-cyl {{ display:grid; grid-template-columns: repeat(8, 1fr); gap:.5rem; }}
.mbi-cyl div {{ background:#F1F4F8; border-radius:7px; text-align:center; padding:.55rem .2rem; }}
.mbi-cyl .n {{ font-size:.68rem; color:{MUTED}; }}
.mbi-cyl .t {{ font-size:1.35rem; font-weight:700; color:{TEXT}; }}
.mbi-cyl div.bad {{ background:{BAD_BG}; }} .mbi-cyl div.bad .t {{ color:{BAD_FG}; }}
.mbi-cyl div.na .t {{ color:#A6B0BE; }}

.mbi-badge {{ display:inline-block; padding:.18rem .5rem; border-radius:4px; font-size:.68rem; font-weight:700;
    letter-spacing:.03em; }}
.mbi-badge.blue {{ background:#E4EEF9; color:{PRIMARY}; }}
.mbi-badge.gray {{ background:#ECEFF3; color:{MUTED}; }}

.mbi-comp {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:1rem; }}
.mbi-comp .l {{ font-size:.7rem; font-weight:600; color:{MUTED}; }}
.mbi-comp .v {{ font-size:1.2rem; font-weight:600; color:{TEXT}; margin-top:.3rem; }}
.mbi-comp .v span {{ font-size:.75rem; font-weight:400; color:{MUTED}; margin-left:.3rem; }}
.mbi-bar {{ height:4px; background:#EDF1F5; border-radius:3px; margin-top:.5rem; overflow:hidden; }}
.mbi-bar i {{ display:block; height:100%; background:{PRIMARY}; }}

.mbi-formula {{ background:#F7F9FB; border:1px solid {BORDER}; border-radius:8px; padding:.7rem .9rem;
    font-size:.85rem; color:{TEXT}; }}
.mbi-pagefoot {{ display:flex; justify-content:space-between; color:{MUTED}; font-size:.76rem; margin-top:1.8rem; }}

/* tombol & input */
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
    background:{PRIMARY}; border-color:{PRIMARY}; }}
div[data-baseweb="select"] > div, .stDateInput input {{ border-radius:6px; }}
[data-testid="stDataFrame"] {{ border-radius: 6px; }}
@media (max-width: 900px) {{
  .mbi-strip, .mbi-comp {{ grid-template-columns: repeat(2, 1fr); }}
  .mbi-cyl {{ grid-template-columns: repeat(4, 1fr); }}
}}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
