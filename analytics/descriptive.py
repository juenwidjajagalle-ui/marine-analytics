"""
Statistik deskriptif & kelengkapan data (halaman Data Information).

Definisi:
  n_total    = jumlah record terpilih
  n_missing  = nilai NULL (atau 0 bila opsi "0 dianggap missing" aktif)
  n_invalid  = nilai terisi tetapi di luar rentang valid (config.valid_ranges)
  n_valid    = n_total - n_missing - n_invalid
  Mean/Median/Min/Max/Std dihitung HANYA dari observasi valid.
  Missing %  = n_missing / n_total x 100
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def classify(series: pd.Series, valid_range: tuple[float, float] | None,
             zero_as_missing: bool = False) -> tuple[pd.Series, pd.Series, pd.Series]:
    s = pd.to_numeric(series, errors="coerce")
    missing = s.isna()
    if zero_as_missing:
        missing = missing | (s == 0)
    if valid_range is not None:
        lo, hi = valid_range
        invalid = ~missing & ((s < lo) | (s > hi))
    else:
        invalid = pd.Series(False, index=s.index)
    valid = ~missing & ~invalid
    return valid, missing, invalid


def describe(df: pd.DataFrame, columns: list[str], valid_ranges: dict,
             zero_as_missing: bool = False) -> pd.DataFrame:
    rows = []
    n_total = len(df)
    for col in columns:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        valid, missing, invalid = classify(s, valid_ranges.get(col), zero_as_missing)
        v = s[valid]
        rows.append({
            "Variable": col,
            "N_Total": n_total,
            "N_Valid": int(valid.sum()),
            "N_Missing": int(missing.sum()),
            "N_Invalid": int(invalid.sum()),
            "Missing_Pct": (missing.sum() / n_total * 100) if n_total else np.nan,
            "Mean": v.mean() if len(v) else np.nan,
            "Median": v.median() if len(v) else np.nan,
            "Min": v.min() if len(v) else np.nan,
            "Max": v.max() if len(v) else np.nan,
            "Std": v.std(ddof=1) if len(v) > 1 else np.nan,
        })
    return pd.DataFrame(rows)


def completeness_all(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    n = len(df)
    out = []
    for c in columns:
        if c not in df.columns:
            continue
        miss = int(df[c].isna().sum())
        out.append({"Column": c, "Filled": n - miss, "Missing": miss,
                    "Missing_Pct": miss / n * 100 if n else np.nan})
    return pd.DataFrame(out).sort_values("Missing_Pct", ascending=False, ignore_index=True)
