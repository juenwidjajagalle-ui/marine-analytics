"""
Analisis anomali termal (Exhaust Gas Temperature / EGT) per silinder.

Rumus (lihat docs/RUMUS.md untuk penjelasan lengkap):

  1. Validasi                 laporan valid jika jumlah silinder EGT valid >= 4 DAN RPM > 0
  2. Median EGT laporan       M_r   = Median(EGT_1..EGT_8 yang valid pada laporan r)
  3. Cylinder Deviation       D_i   = EGT_i - M_r
  4. Historical baseline      B_i   = deviasi valid historis dari kapal yang sama, silinder yang sama,
                                      dan KELOMPOK RENTANG RPM yang sama (kondisi operasi sebanding),
                                      hanya laporan SEBELUM laporan r (maks. N data terakhir)
  5. MAD                      MAD_i = Median(|B - Median(B)|)
  6. Modified Z-Score         MZ_i  = 0.6745 * (D_i - Median(B)) / MAD_i
  7. Status                   ANOMALY jika |MZ_i| > 3.5, NORMAL jika |MZ_i| <= 3.5,
                              DATA_NOT_VALID jika data tidak memenuhi kriteria perhitungan
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.settings import AnalyticsSettings

ANOMALY = "ANOMALY"
NORMAL = "NORMAL"
NOT_VALID = "DATA_NOT_VALID"
CANNOT = NOT_VALID  # nama lama, tetap disediakan agar kode lain tidak rusak
STATUSES = (NORMAL, ANOMALY, NOT_VALID)

REASON_OK = "OK"
REASON_MISSING_EGT = "MISSING_OR_INVALID_EGT"
REASON_NO_RPM = "RPM_NOT_AVAILABLE"
REASON_FEW_CYL = "INSUFFICIENT_CYLINDERS"
REASON_FEW_BASE = "INSUFFICIENT_BASELINE"
REASON_MAD_ZERO = "MAD_ZERO"

MAD_EPS = 1e-9


@dataclass(frozen=True)
class ThermalParams:
    n_cylinders: int = 8
    min_valid_cylinders: int = 4
    baseline_window: int = 60
    min_baseline_obs: int = 10
    z_constant: float = 0.6745
    z_threshold: float = 3.5
    drop_uninstalled_cylinders: bool = True
    baseline_mode: str = "rpm_bin"   # "rpm_bin" (sesuai proposal) atau "rolling"
    rpm_bin_width: float = 10.0

    @classmethod
    def from_settings(cls, s: AnalyticsSettings) -> "ThermalParams":
        return cls(s.n_cylinders, s.min_valid_cylinders, s.baseline_window,
                   s.min_baseline_obs, s.z_constant, s.z_threshold, s.drop_uninstalled_cylinders,
                   s.baseline_mode, s.rpm_bin_width)


def rpm_group(rpm: np.ndarray, width: float) -> tuple[np.ndarray, np.ndarray]:
    """Kelompok rentang RPM. Contoh width=10: RPM 98,4 -> 90–100; RPM 105 -> 100–110.

    Return (batas_bawah, label). RPM <= 0 / kosong -> NaN dan label kosong."""
    rpm = np.asarray(rpm, dtype=float)
    ok = np.isfinite(rpm) & (rpm > 0)
    lo = np.where(ok, np.floor(np.where(ok, rpm, 0) / width) * width, np.nan)
    label = np.array([f"{a:g}–{a + width:g}" if np.isfinite(a) else "" for a in lo], dtype=object)
    return lo, label


def report_median_and_deviation(egt: np.ndarray, min_valid: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """egt: array (n_laporan x n_silinder), NaN = tidak valid.

    Return (median_egt, deviasi, jumlah_silinder_valid)."""
    valid = np.isfinite(egt)
    n_valid = valid.sum(axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        med = np.nanmedian(egt, axis=1)
    med = np.where(n_valid >= min_valid, med, np.nan)
    dev = egt - med[:, None]  # NaN otomatis bila EGT atau median NaN
    return med, dev, n_valid


def rolling_baseline(dev_valid: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Untuk deretan deviasi valid berurutan waktu (1 kelompok baseline), hitung untuk
    setiap titik i baseline = dev_valid[i-window : i]  (titik i TIDAK ikut).

    Return (n_baseline, median_baseline, MAD_baseline)."""
    n = len(dev_valid)
    if n == 0:
        empty = np.array([], dtype=float)
        return empty.astype(int), empty, empty
    padded = np.concatenate([np.full(window, np.nan), dev_valid.astype(float)])
    windows = np.lib.stride_tricks.sliding_window_view(padded, window)[:n]
    n_base = np.isfinite(windows).sum(axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        med = np.nanmedian(windows, axis=1)
        mad = np.nanmedian(np.abs(windows - med[:, None]), axis=1)
    return n_base, med, mad


def compute_thermal(df: pd.DataFrame, params: ThermalParams) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hitung anomali termal.

    df wajib berisi: Noon_Report_Key, Vessel_Key, Voyage_Key, Date_Key, REPORT_DATE, RPM,
    EXH_TEMP_CYL1..N (sudah dibersihkan: nilai tidak valid = NaN).

    Return:
      cylinder_df : 1 baris per laporan x silinder (FACT_CYLINDER_ANOMALY)
      summary_df  : 1 baris per laporan (ringkasan untuk FACT_NOON_REPORT)
    """
    egt_cols = [f"EXH_TEMP_CYL{i}" for i in range(1, params.n_cylinders + 1)]
    cyl_out_cols = ["Noon_Report_Key", "Cylinder_No", "Date_Key", "Voyage_Key", "Vessel_Key",
                    "REPORT_DATE", "RPM", "RPM_GROUP", "EGT", "MEDIAN_EGT", "CYLINDER_DEVIATION",
                    "BASELINE_N", "BASELINE_MEDIAN_DEV", "MAD", "MODIFIED_Z_SCORE", "ANOMALY_STATUS",
                    "STATUS_REASON"]
    sum_cols = ["Noon_Report_Key", "MEDIAN_EGT", "VALID_CYLINDERS", "MAX_ABS_MODIFIED_Z",
                "ANOMALY_CYLINDERS", "Anomaly_Status"]
    if df.empty:
        return pd.DataFrame(columns=cyl_out_cols), pd.DataFrame(columns=sum_cols)

    src = df.copy()
    if "RPM" not in src.columns:
        src["RPM"] = np.nan
    base = (src[["Noon_Report_Key", "Vessel_Key", "Voyage_Key", "Date_Key", "REPORT_DATE", "RPM", *egt_cols]]
            .sort_values(["Vessel_Key", "REPORT_DATE", "Noon_Report_Key"], kind="mergesort")
            .reset_index(drop=True))
    egt = base[egt_cols].to_numpy(dtype=float)
    rpm = pd.to_numeric(base["RPM"], errors="coerce").to_numpy(dtype=float)
    med, dev, n_valid = report_median_and_deviation(egt, params.min_valid_cylinders)

    use_rpm = params.baseline_mode == "rpm_bin"
    rpm_ok_rep = (np.isfinite(rpm) & (rpm > 0)) if use_rpm else np.ones(len(rpm), dtype=bool)
    # Laporan tanpa RPM valid tidak diteruskan ke analisis (kriteria validasi proposal)
    dev = np.where(rpm_ok_rep[:, None], dev, np.nan)
    rpm_lo, rpm_label = rpm_group(rpm, params.rpm_bin_width)

    # ----- ke format panjang: 1 baris per laporan x silinder -----
    n_rep, n_cyl = egt.shape
    long = pd.DataFrame({
        "Noon_Report_Key": np.repeat(base["Noon_Report_Key"].to_numpy(), n_cyl),
        "Vessel_Key": np.repeat(base["Vessel_Key"].to_numpy(), n_cyl),
        "Voyage_Key": np.repeat(base["Voyage_Key"].to_numpy(), n_cyl),
        "Date_Key": np.repeat(base["Date_Key"].to_numpy(), n_cyl),
        "REPORT_DATE": np.repeat(base["REPORT_DATE"].to_numpy(), n_cyl),
        "RPM": np.repeat(rpm, n_cyl),
        "RPM_GROUP": np.repeat(rpm_label, n_cyl),
        "_rpm_lo": np.repeat(np.nan_to_num(rpm_lo, nan=-1.0) if use_rpm else np.zeros(n_rep), n_cyl),
        "_rpm_ok": np.repeat(rpm_ok_rep, n_cyl),
        "Cylinder_No": np.tile(np.arange(1, n_cyl + 1), n_rep),
        "EGT": egt.ravel(),
        "MEDIAN_EGT": np.repeat(med, n_cyl),
        "CYLINDER_DEVIATION": dev.ravel(),
        "_order": np.repeat(np.arange(n_rep), n_cyl),
    })
    long["BASELINE_N"] = 0
    long["BASELINE_MEDIAN_DEV"] = np.nan
    long["MAD"] = np.nan

    # ----- historical baseline per (kapal, silinder[, rentang RPM]), hanya deviasi valid -----
    group_keys = ["Vessel_Key", "Cylinder_No", "_rpm_lo"]
    long = long.sort_values([*group_keys, "_order"], kind="mergesort")
    valid_mask = np.isfinite(long["CYLINDER_DEVIATION"].to_numpy())
    valid_rows = long[valid_mask]
    n_base_all = np.zeros(len(valid_rows), dtype=int)
    med_all = np.full(len(valid_rows), np.nan)
    mad_all = np.full(len(valid_rows), np.nan)
    pos = 0
    for _, grp in valid_rows.groupby(group_keys, sort=False):
        n_b, m_b, mad_b = rolling_baseline(grp["CYLINDER_DEVIATION"].to_numpy(), params.baseline_window)
        k = len(grp)
        n_base_all[pos:pos + k], med_all[pos:pos + k], mad_all[pos:pos + k] = n_b, m_b, mad_b
        pos += k
    idx = valid_rows.index
    long.loc[idx, "BASELINE_N"] = n_base_all
    long.loc[idx, "BASELINE_MEDIAN_DEV"] = med_all
    long.loc[idx, "MAD"] = mad_all

    # ----- Modified Z-Score & status -----
    d = long["CYLINDER_DEVIATION"].to_numpy()
    bmed = long["BASELINE_MEDIAN_DEV"].to_numpy()
    mad = long["MAD"].to_numpy()
    nb = long["BASELINE_N"].to_numpy()
    egt_ok = np.isfinite(long["EGT"].to_numpy())
    rpm_ok = long["_rpm_ok"].to_numpy(dtype=bool)
    med_ok = np.isfinite(long["MEDIAN_EGT"].to_numpy())
    base_ok = nb >= params.min_baseline_obs
    mad_ok = np.isfinite(mad) & (mad > MAD_EPS)
    can = egt_ok & rpm_ok & med_ok & base_ok & mad_ok

    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(can, params.z_constant * (d - bmed) / mad, np.nan)

    status = np.where(~can, NOT_VALID, np.where(np.abs(z) > params.z_threshold, ANOMALY, NORMAL))
    reason = np.select(
        [~egt_ok, ~rpm_ok, ~med_ok, ~base_ok, ~mad_ok],
        [REASON_MISSING_EGT, REASON_NO_RPM, REASON_FEW_CYL, REASON_FEW_BASE, REASON_MAD_ZERO],
        default=REASON_OK,
    )
    long["MODIFIED_Z_SCORE"] = z
    long["ANOMALY_STATUS"] = status
    long["STATUS_REASON"] = reason

    # ----- silinder yang tidak terpasang tidak ikut dilaporkan -----
    # Silinder dianggap "tidak terpasang" pada sebuah kapal jika di SELURUH histori kapal itu
    # tidak pernah punya satu pun EGT valid (mis. CYL7-8 selalu 0 pada mesin 6 silinder).
    if params.drop_uninstalled_cylinders:
        installed = (long.assign(_v=np.isfinite(long["EGT"].to_numpy()))
                     .groupby(["Vessel_Key", "Cylinder_No"])["_v"].transform("any"))
        long = long[installed.to_numpy()]

    cylinder_df = (long.sort_values(["_order", "Cylinder_No"])[cyl_out_cols].reset_index(drop=True))
    cylinder_df["BASELINE_N"] = cylinder_df["BASELINE_N"].astype(int)
    cylinder_df["RPM_GROUP"] = cylinder_df["RPM_GROUP"].replace("", None)

    # ----- ringkasan per laporan -----
    g = cylinder_df.assign(
        _abs_z=cylinder_df["MODIFIED_Z_SCORE"].abs(),
        _is_anom=(cylinder_df["ANOMALY_STATUS"] == ANOMALY).astype(int),
        _is_calc=(cylinder_df["ANOMALY_STATUS"] != NOT_VALID).astype(int),
    ).groupby("Noon_Report_Key", sort=False)
    summary = pd.DataFrame({
        "MAX_ABS_MODIFIED_Z": g["_abs_z"].max(),
        "ANOMALY_CYLINDERS": g["_is_anom"].sum(),
        "_calc": g["_is_calc"].sum(),
    }).reset_index()
    rep = pd.DataFrame({"Noon_Report_Key": base["Noon_Report_Key"], "MEDIAN_EGT": med,
                        "VALID_CYLINDERS": n_valid})
    summary = rep.merge(summary, on="Noon_Report_Key", how="left")
    summary["ANOMALY_CYLINDERS"] = summary["ANOMALY_CYLINDERS"].fillna(0).astype(int)
    summary["_calc"] = summary["_calc"].fillna(0)
    summary["Anomaly_Status"] = np.where(
        summary["ANOMALY_CYLINDERS"] > 0, ANOMALY,
        np.where(summary["_calc"] > 0, NORMAL, NOT_VALID))
    summary = summary.drop(columns="_calc")[sum_cols]
    return cylinder_df, summary