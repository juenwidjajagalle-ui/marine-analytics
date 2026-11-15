"""
TRANSFORM — membersihkan data mentah & membentuk tabel star schema.

Aturan pembersihan utama:
  * GUID dinormalisasi (UPPER, tanpa kurung kurawal)
  * Tanggal sentinel '1900-01-01' dianggap NULL
  * Kolom numerik: teks dikonversi ke angka; gagal konversi -> NULL (dicatat di DQ)
  * AIR/SEA_TEMPERATURE: '31° C' -> 31.0
  * EXH_TEMP_CYLx: 0/NULL = tidak dilaporkan; di luar [egt_valid_min, egt_valid_max] = invalid -> NULL
  * EXH_TEMP_CYLx terisi tetapi RPM = 0 -> invalid -> NULL (bila egt_requires_rpm=True)
  * Laporan tanpa REPORT_DATE dibuang (tidak bisa diberi Date_Key)
  * Duplikat ID_NOON_REPORT -> ambil versi perubahan terbaru
  * Laporan tidak aktif / diarsipkan tidak dimuat (bila only_active_reports=True)
  * Voyage yang tidak ada di V_Voyages -> Vessel_Key = 'UNKNOWN'
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from config.settings import AnalyticsSettings
from core import schema

UNKNOWN = "UNKNOWN"
SENTINEL_DATE = pd.Timestamp("1901-01-01")
_NUM_RE = r"(-?\d+(?:[.,]\d+)?)"


# ---------------------------------------------------------------- helpers ---
def normalize_guid(s: pd.Series) -> pd.Series:
    out = s.astype("string").str.strip().str.strip("{}").str.upper()
    return out.where(out.notna() & (out != "") & (out != "NONE") & (out != "NAN"), None).astype(object)


def to_text(s: pd.Series, max_len: int | None = None) -> pd.Series:
    def conv(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        if isinstance(v, (bytes, bytearray)):
            return "0x" + bytes(v).hex().upper()
        t = str(v).strip()
        if t == "" or t.upper() in {"NULL", "NAN", "NONE"}:
            return None
        return t[:max_len] if max_len else t
    return s.map(conv).astype(object)


def to_number(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce").astype(float)
    txt = s.astype("string").str.strip()
    direct = pd.to_numeric(txt, errors="coerce")
    extracted = pd.to_numeric(txt.str.extract(_NUM_RE, expand=False).str.replace(",", "."),
                              errors="coerce")
    return direct.fillna(extracted).astype(float)


def to_datetime_clean(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s, errors="coerce")
    return d.where(d >= SENTINEL_DATE)


def build_date_dim(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    days = pd.date_range(start.normalize(), end.normalize(), freq="D")
    return pd.DataFrame({
        "Date_Key": days.strftime("%Y%m%d").astype(int),
        "Full_Date": days.date,
        "Day": days.day.astype(int),
        "Month": days.month.astype(int),
        "Year": days.year.astype(int),
        "Month_Name": days.strftime("%B"),
        "Quarter": days.quarter.astype(int),
        "Day_Of_Week": days.strftime("%A"),
        "Year_Month": days.strftime("%Y-%m"),
    })


# ------------------------------------------------------------- dimensions ---
def transform_vessels(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({
        "Vessel_Key": to_text(raw["CODE_VESSEL"], 20).str.upper() if len(raw) else pd.Series(dtype=object),
        "NAME": to_text(raw["NAME"], 200) if len(raw) else pd.Series(dtype=object),
    })
    for c in ["SPEED", "MFO_AT_PORT", "MFO_AT_SEA", "MDO_AT_PORT", "MDO_AT_SEA", "FW"]:
        df[c] = to_number(raw[c]) if len(raw) else pd.Series(dtype=float)
    df = df[df["Vessel_Key"].notna()].drop_duplicates("Vessel_Key", keep="last")
    if UNKNOWN not in set(df["Vessel_Key"]):
        unk = {c: np.nan for c in df.columns}
        unk.update({"Vessel_Key": UNKNOWN, "NAME": "Unknown vessel"})
        df = pd.concat([df, pd.DataFrame([unk])], ignore_index=True)
    return df.reset_index(drop=True)


VOYAGE_NO_CANDIDATES = ("VOYAGE_NO", "VOYAGE_NUMBER", "NO_VOYAGE", "VOY_NO", "VOYAGE_CODE",
                        "CODE_VOYAGE", "VOYAGE_NAME", "VOYAGE", "NO_VOY", "NOMOR_VOYAGE")


def find_voyage_no_column(columns) -> str | None:
    """Cari kolom nomor voyage di V_Voyages (nama kolom tidak peka huruf besar/kecil)."""
    upper = {str(c).upper(): c for c in columns}
    for cand in VOYAGE_NO_CANDIDATES:
        if cand in upper:
            return upper[cand]
    return None


def transform_voyages(raw: pd.DataFrame) -> pd.DataFrame:
    """DIM_VOYAGE. Voyage_Key = ID_VOYAGE (GUID dari V_Voyages, sama dengan FID_VOYAGE di noon report).
    Vessel_Key = FCODE_VESSEL. Label yang dibaca manusia dibentuk saat finalize ETL."""
    cols = {str(c).upper(): c for c in raw.columns}
    df = pd.DataFrame({
        "Voyage_Key": normalize_guid(raw[cols["ID_VOYAGE"]]),
        "Vessel_Key": to_text(raw[cols["FCODE_VESSEL"]], 20).str.upper(),
    })
    vno_col = find_voyage_no_column(raw.columns)
    df["Voyage_No"] = to_text(raw[vno_col], 50) if vno_col else None
    df = df[df["Voyage_Key"].notna()].drop_duplicates("Voyage_Key", keep="last")
    df["Vessel_Key"] = df["Vessel_Key"].fillna(UNKNOWN)
    df["FID_VOYAGE"] = df["Voyage_Key"]
    df["Voyage_Label"] = df["Vessel_Key"] + " · " + df["Voyage_Key"].str[:8]  # sementara
    df["First_Report_Date"] = pd.NaT
    df["Last_Report_Date"] = pd.NaT
    df["Report_Count"] = 0
    return df[["Voyage_Key", "FID_VOYAGE", "Vessel_Key", "Voyage_No", "Voyage_Label",
               "First_Report_Date", "Last_Report_Date", "Report_Count"]].reset_index(drop=True)


# ------------------------------------------------------------------- fact ---
def transform_noon_reports(raw: pd.DataFrame, voyages: pd.DataFrame,
                           vessels: pd.DataFrame, a: AnalyticsSettings
                           ) -> tuple[pd.DataFrame, list[str], pd.DataFrame, dict]:
    """Return (fact_df, changed_keys, extra_voyages, dq_report).

    changed_keys  : semua ID yang berubah di sumber (termasuk yang kini non-aktif) —
                    dipakai untuk menghapus versi lama di fact sebelum insert.
    extra_voyages : voyage yang dirujuk laporan tetapi tidak ada di V_Voyages.
    """
    dq: dict = {"rows_extracted": int(len(raw))}
    if raw.empty:
        dq.update(rows_loaded=0)
        return pd.DataFrame(columns=schema.FACT_LOAD_COLUMNS), [], pd.DataFrame(), dq

    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    lookup = {c.upper(): c for c in df.columns}

    def col(name: str) -> pd.Series:
        src = lookup.get(name.upper())
        return df[src] if src is not None else pd.Series([None] * len(df), index=df.index)

    out = pd.DataFrame(index=df.index)
    out["Noon_Report_Key"] = normalize_guid(col("ID_NOON_REPORT"))
    out["Voyage_Key"] = normalize_guid(col("FID_VOYAGE"))
    out["PMS_Noon_Report_ID"] = to_text(col("PMS_Noon_Report_ID"), 100)
    change_ts = pd.to_datetime(col("_CHANGE_TS"), errors="coerce")

    for c in schema.DATETIME_COLS:
        out[c] = to_datetime_clean(col(c))

    bad_numeric = 0
    for c in schema.NUMERIC_COLS + schema.TEXT_NUMERIC_COLS:
        src = col(c)
        num = to_number(src)
        bad_numeric += int((src.notna() & num.isna() & (src.astype("string").str.strip() != "")).sum())
        out[c] = num
    dq["unparseable_numeric_values"] = bad_numeric

    for c, n in schema.TEXT_COLS.items():
        out[c] = to_text(col(c), n)
    for c in schema.INT_COLS:
        out[c] = to_number(col(c))

    # --- EGT: 0/NULL = tidak dilaporkan, di luar rentang = invalid ---
    egt_zero = egt_invalid = 0
    for c in schema.EGT_COLS:
        v = out[c]
        zero = v.notna() & (v <= 0)
        invalid = v.notna() & (v > 0) & ((v < a.egt_valid_min) | (v > a.egt_valid_max))
        egt_zero += int(zero.sum())
        egt_invalid += int(invalid.sum())
        out[c] = v.mask(zero | invalid)
    dq["egt_zero_or_not_reported"] = egt_zero
    dq["egt_out_of_range"] = egt_invalid

    # --- Validasi fisik: EGT terisi tetapi RPM = 0 -> pembacaan tidak valid ---
    if a.egt_requires_rpm:
        rpm_zero = out["RPM"].notna() & (out["RPM"] <= 0)
        has_egt = out[schema.EGT_COLS].notna().any(axis=1)
        dq["egt_with_rpm_zero"] = int((rpm_zero & has_egt).sum())
        out.loc[rpm_zero, schema.EGT_COLS] = np.nan

    # --- kunci ---
    no_key = out["Noon_Report_Key"].isna()
    dq["dropped_missing_id"] = int(no_key.sum())
    out, change_ts = out[~no_key], change_ts[~no_key]

    out["_CHANGE_TS"] = change_ts
    out = out.sort_values("_CHANGE_TS", na_position="first", kind="mergesort")
    dup = out.duplicated("Noon_Report_Key", keep="last")
    dq["duplicate_ids_resolved"] = int(dup.sum())
    out = out[~dup]
    changed_keys = out["Noon_Report_Key"].tolist()

    if a.only_active_reports:
        active = out["IS_ACTIVE"].fillna(1).eq(1) & out["IS_ARCHIVED"].fillna(0).ne(1)
        dq["excluded_inactive_or_archived"] = int((~active).sum())
        out = out[active]

    no_date = out["REPORT_DATE"].isna()
    dq["dropped_missing_report_date"] = int(no_date.sum())
    out = out[~no_date].copy()
    out["Date_Key"] = out["REPORT_DATE"].dt.strftime("%Y%m%d").astype(int)

    # --- relasi ke dimensi ---
    voy_map = dict(zip(voyages["Voyage_Key"], voyages["Vessel_Key"]))
    out["Vessel_Key"] = out["Voyage_Key"].map(voy_map)
    orphan = out["Vessel_Key"].isna()
    dq["reports_with_unknown_voyage"] = int(orphan.sum())
    out["Vessel_Key"] = out["Vessel_Key"].fillna(UNKNOWN)
    known_vessels = set(vessels["Vessel_Key"])
    unknown_vessel = ~out["Vessel_Key"].isin(known_vessels)
    dq["reports_with_vessel_not_in_master"] = int((unknown_vessel & ~orphan).sum())
    out.loc[unknown_vessel, "Vessel_Key"] = UNKNOWN

    extra_ids = sorted(set(out.loc[orphan & out["Voyage_Key"].notna(), "Voyage_Key"]))
    extra_voyages = pd.DataFrame({
        "Voyage_Key": extra_ids, "FID_VOYAGE": extra_ids, "Vessel_Key": UNKNOWN, "Voyage_No": None,
        "Voyage_Label": [f"{UNKNOWN} · {v[:8]}" for v in extra_ids],
        "First_Report_Date": pd.NaT, "Last_Report_Date": pd.NaT, "Report_Count": 0,
    })

    out["ETL_LOADED_AT"] = pd.Timestamp(dt.datetime.now().replace(microsecond=0))
    dq["rows_loaded"] = int(len(out))
    dq["max_change_ts"] = change_ts.max()
    fact = out[schema.FACT_LOAD_COLUMNS].reset_index(drop=True)
    return fact, changed_keys, extra_voyages, dq