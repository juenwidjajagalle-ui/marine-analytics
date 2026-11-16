"""
Helper kondisi lingkungan (angin, skala Beaufort, suhu) untuk halaman Noon Report.

Murni pandas/numpy, tanpa Streamlit & database, sehingga bisa diuji di tests/test_core.py.
Tidak mengubah data di warehouse - hanya normalisasi untuk tampilan.

  WIND_DIRECTION  : trim + uppercase, harus salah satu dari 16 arah kompas (N, NNE, ... NNW);
                    selain itu -> "Unknown" (tidak masuk wind rose).
  Sudut arah      : N = 0°, NNE = 22,5°, NE = 45°, ... (kelipatan 22,5°, searah jarum jam).
  Kelas Beaufort  : wind rose  0–3 · 4–5 · 6–7 · ≥8
                    stat tile  hijau 0–4 · kuning 5–7 · merah 8–12
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

COMPASS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
DIRECTION_DEG = {d: i * 22.5 for i, d in enumerate(COMPASS_16)}
UNKNOWN = "Unknown"

# Penulisan lain yang jelas maknanya (mis. "NORTH EAST", "N-E") dipetakan ke kode kompas
_ALIASES = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
}

BEAUFORT_DESC = [
    "Calm", "Light air", "Light breeze", "Gentle breeze", "Moderate breeze", "Fresh breeze",
    "Strong breeze", "Near gale", "Gale", "Strong gale", "Storm", "Violent storm", "Hurricane force",
]

# Kelas wind rose: (label, batas bawah, batas atas inklusif)
ROSE_CLASSES = [("Bft 0–3", 0, 3), ("Bft 4–5", 4, 5), ("Bft 6–7", 6, 7), ("Bft ≥8", 8, 12)]


def normalize_one(v) -> str | None:
    """Satu nilai WIND_DIRECTION -> kode kompas, "Unknown", atau None (kosong)."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    s = str(v).strip().upper()
    if not s:
        return None
    compact = re.sub(r"[\s\-_/.]", "", s)
    return compact if compact in DIRECTION_DEG else _ALIASES.get(compact, UNKNOWN)


def normalize_direction(s: pd.Series) -> pd.Series:
    """Trim + uppercase; arah di luar 16 titik kompas -> "Unknown", NULL / kosong -> None."""
    return pd.Series([normalize_one(v) for v in s], index=s.index, dtype=object)


def direction_deg(direction) -> float | None:
    """Sudut kompas (derajat) untuk satu nilai arah; None bila tidak dikenali."""
    d = normalize_one(direction)
    return DIRECTION_DEG.get(d) if d else None


def beaufort_level(force) -> int | None:
    """FORCE dibulatkan ke skala 0–12; None bila kosong atau di luar skala."""
    if force is None or pd.isna(force):
        return None
    b = int(round(float(force)))
    return b if 0 <= b <= 12 else None


def beaufort_desc(force) -> str:
    if force is None or pd.isna(force):
        return "—"
    b = beaufort_level(force)
    return BEAUFORT_DESC[b] if b is not None else "Outside Beaufort 0–12"


def beaufort_severity(force) -> str:
    """'ok' (0–4), 'warn' (5–7), 'bad' (8–12), '' bila tidak ada nilai."""
    b = beaufort_level(force)
    if b is None:
        return ""
    return "ok" if b <= 4 else ("warn" if b <= 7 else "bad")


def rose_class(force: pd.Series) -> pd.Series:
    """Label kelas wind rose untuk setiap nilai FORCE (NULL / di luar 0–12 -> NaN)."""
    f = pd.to_numeric(force, errors="coerce").round()
    out = pd.Series(np.nan, index=force.index, dtype=object)
    for label, lo, hi in ROSE_CLASSES:
        out[(f >= lo) & (f <= hi)] = label
    return out


def wind_rose_table(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Jumlah laporan per (arah kompas x kelas Beaufort) untuk wind rose.

    Return (tabel lengkap 16 arah x 4 kelas, ringkasan baris yang dikeluarkan)."""
    direction = normalize_direction(df["WIND_DIRECTION"]) if len(df) else pd.Series(dtype=object)
    cls = rose_class(df["FORCE"]) if len(df) else pd.Series(dtype=object)
    excl = {
        "missing_direction": int(direction.isna().sum()),
        "unknown_direction": int((direction == UNKNOWN).sum()),
        "missing_force": int((direction.isin(COMPASS_16) & cls.isna()).sum()),
    }
    ok = direction.isin(COMPASS_16) & cls.notna()
    counts = (pd.DataFrame({"direction": direction[ok], "beaufort": cls[ok]})
              .value_counts().rename("reports").reset_index())
    grid = pd.MultiIndex.from_product([COMPASS_16, [c[0] for c in ROSE_CLASSES]],
                                      names=["direction", "beaufort"]).to_frame(index=False)
    table = grid.merge(counts, on=["direction", "beaufort"], how="left").fillna({"reports": 0})
    table["reports"] = table["reports"].astype(int)
    excl["used"] = int(ok.sum())
    return table, excl


def daily_environment(df: pd.DataFrame, anomaly_value: str, multi: bool) -> pd.DataFrame:
    """Deret per REPORT_DATE untuk chart tren (suhu, FORCE, penanda anomali).

    multi=True (lebih dari 1 kapal): rata-rata per hari, hari ditandai anomali bila ada
    minimal satu laporan anomali. multi=False: setiap laporan apa adanya."""
    cols = ["AIR_TEMPERATURE", "SEA_TEMPERATURE", "FORCE"]
    base = df[["REPORT_DATE", *cols, "Anomaly_Status", "ANOMALY_CYLINDERS"]].copy()
    base["_anom"] = (base["Anomaly_Status"] == anomaly_value).astype(int)
    base["ANOMALY_CYLINDERS"] = pd.to_numeric(base["ANOMALY_CYLINDERS"], errors="coerce").fillna(0)
    if not multi:
        out = base.sort_values("REPORT_DATE")
        return out.assign(is_anomaly=out["_anom"].astype(bool), anomaly_reports=out["_anom"]).drop(columns="_anom")
    g = base.assign(REPORT_DATE=base["REPORT_DATE"].dt.normalize()).groupby("REPORT_DATE", as_index=False)
    out = g[cols].mean().merge(
        g.agg(anomaly_reports=("_anom", "sum"), ANOMALY_CYLINDERS=("ANOMALY_CYLINDERS", "sum")), on="REPORT_DATE")
    out["is_anomaly"] = out["anomaly_reports"] > 0
    return out.sort_values("REPORT_DATE").reset_index(drop=True)
