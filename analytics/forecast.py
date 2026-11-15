"""
Forecasting konsumsi bahan bakar main engine dengan Double Exponential Smoothing (Holt).

Data yang diramal (per bulan):
    y_t = rata-rata konsumsi BBM main engine per laporan pada bulan t
        = Σ (ME_MFO_CONS + ME_MDO_CONS) / jumlah laporan valid
    Laporan valid: RPM > 0 (mesin beroperasi), konsumsi > 0 dan <= batas wajar (salah input dibuang).
    Bulan dengan laporan valid < batas minimum, dan bulan terakhir yang belum lengkap, tidak dipakai.

Rumus Holt (Double Exponential Smoothing):
    Level   : L_t = α · y_t + (1 − α) · (L_{t−1} + T_{t−1})
    Trend   : T_t = β · (L_t − L_{t−1}) + (1 − β) · T_{t−1}
    Ramalan : F_{t+m} = L_t + m · T_t
    Inisialisasi: L_1 = y_1, T_1 = y_2 − y_1
    α dan β dipilih dengan grid search (0,05 – 0,95) yang meminimalkan SSE pada data latih.

Evaluasi (k bulan terakhir sebagai data uji):
    MAE  = (1/n) Σ |y_t − F_t|
    MAPE = (100%/n) Σ |(y_t − F_t) / y_t|
    Interpretasi MAPE (Lewis, 1982): <10% sangat baik, 10–20% baik, 20–50% layak, >50% buruk.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

GRID = np.round(np.arange(0.05, 0.951, 0.05), 2)


@dataclass
class HoltModel:
    alpha: float
    beta: float
    level: float
    trend: float
    fitted: np.ndarray            # ramalan 1-langkah untuk t = 2..n
    sse: float


@dataclass
class ForecastResult:
    history: pd.DataFrame          # kolom: period (Timestamp awal bulan), value, reports
    fitted: pd.Series              # ramalan 1-langkah pada data historis
    test: pd.DataFrame             # period, actual, forecast (evaluasi)
    forecast: pd.DataFrame         # period, forecast
    alpha: float
    beta: float
    mae: float
    mape: float
    rating: str
    notes: list[str] = field(default_factory=list)


def holt_fit(y: np.ndarray, alpha: float, beta: float) -> HoltModel:
    y = np.asarray(y, dtype=float)
    level, trend = y[0], y[1] - y[0]
    fitted = []
    for v in y[1:]:
        fitted.append(level + trend)
        new_level = alpha * v + (1 - alpha) * (level + trend)
        trend = beta * (new_level - level) + (1 - beta) * trend
        level = new_level
    fitted = np.array(fitted)
    sse = float(np.sum((y[1:] - fitted) ** 2))
    return HoltModel(alpha, beta, level, trend, fitted, sse)


def holt_optimize(y: np.ndarray) -> HoltModel:
    best = None
    for a in GRID:
        for b in GRID:
            m = holt_fit(y, float(a), float(b))
            if best is None or m.sse < best.sse:
                best = m
    return best


def holt_forecast(model: HoltModel, horizon: int) -> np.ndarray:
    return np.array([model.level + (k + 1) * model.trend for k in range(horizon)])


def mae(actual, pred) -> float:
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    return float(np.mean(np.abs(a - p)))


def mape(actual, pred) -> float:
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    ok = a != 0
    return float(np.mean(np.abs((a[ok] - p[ok]) / a[ok])) * 100) if ok.any() else float("nan")


def mape_rating(v: float) -> str:
    if not np.isfinite(v):
        return "—"
    if v < 10:
        return "Sangat baik"
    if v < 20:
        return "Baik"
    if v <= 50:
        return "Layak"
    return "Buruk"


def run_forecast(monthly: pd.DataFrame, horizon: int = 3, test_months: int = 3,
                 min_reports: int = 15) -> ForecastResult | None:
    """monthly: kolom Year_Month ('YYYY-MM'), Avg_Cons, Valid_Reports.
    Return None jika data terlalu sedikit (< test_months + 6 bulan)."""
    notes: list[str] = []
    df = monthly.copy()
    df["period"] = pd.to_datetime(df["Year_Month"] + "-01")
    df = df.sort_values("period")
    # bulan terakhir yang belum lengkap (data terpotong di tengah bulan) tidak dipakai
    if "Last_Report" in df.columns and len(df):
        last_dt = pd.to_datetime(df["Last_Report"].iloc[-1])
        month_end = df["period"].iloc[-1] + pd.offsets.MonthEnd(0)
        if pd.notna(last_dt) and last_dt.normalize() < month_end.normalize() - pd.Timedelta(days=2):
            notes.append(f"Incomplete last month {df['Year_Month'].iloc[-1]} (data until {last_dt:%d %b %Y}) "
                         "excluded")
            df = df.iloc[:-1]
    dropped = df[df["Valid_Reports"] < min_reports]
    if len(dropped):
        notes.append(f"{len(dropped)} month(s) with fewer than {min_reports} valid reports excluded: "
                     + ", ".join(dropped["Year_Month"].tolist()))
    df = df[df["Valid_Reports"] >= min_reports]
    df = df[df["Avg_Cons"].notna() & (df["Avg_Cons"] > 0)]
    if len(df) < test_months + 6:
        return None

    # bulan yang hilang di tengah deret (mis. kapal docking) ditandai, deret tetap berurutan
    full = pd.date_range(df["period"].min(), df["period"].max(), freq="MS")
    missing = sorted(set(full) - set(df["period"]))
    if missing:
        notes.append(f"{len(missing)} month(s) without data were skipped: "
                     + ", ".join(m.strftime("%Y-%m") for m in missing))

    y = df["Avg_Cons"].to_numpy(dtype=float)
    periods = df["period"].reset_index(drop=True)

    # 1) evaluasi: latih tanpa k bulan terakhir, ramal k bulan, bandingkan dengan aktual
    train, test = y[:-test_months], y[-test_months:]
    m_train = holt_optimize(train)
    test_pred = holt_forecast(m_train, test_months)
    err_mae, err_mape = mae(test, test_pred), mape(test, test_pred)

    # 2) model akhir: latih dengan seluruh data, ramal `horizon` bulan ke depan
    m_full = holt_optimize(y)
    fc = holt_forecast(m_full, horizon)
    last = periods.iloc[-1]
    fc_periods = [last + pd.DateOffset(months=k + 1) for k in range(horizon)]

    return ForecastResult(
        history=pd.DataFrame({"period": periods, "value": y,
                              "reports": df["Valid_Reports"].to_numpy()}),
        fitted=pd.Series(m_full.fitted, index=periods.iloc[1:].to_numpy()),
        test=pd.DataFrame({"period": periods.iloc[-test_months:].to_numpy(), "actual": test,
                           "forecast": test_pred}),
        forecast=pd.DataFrame({"period": fc_periods, "forecast": np.maximum(fc, 0)}),
        alpha=m_full.alpha, beta=m_full.beta, mae=err_mae, mape=err_mape,
        rating=mape_rating(err_mape), notes=notes,
    )