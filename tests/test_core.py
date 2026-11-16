"""Unit test logika inti (tanpa database).  Jalankan:  python -m pytest tests -q
atau tanpa pytest:  python tests/test_core.py"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.descriptive import describe  # noqa: E402
from analytics.thermal import ANOMALY, CANNOT, NORMAL, NOT_VALID, ThermalParams, compute_thermal, rolling_baseline  # noqa: E402
from config.settings import AnalyticsSettings  # noqa: E402
from core import schema  # noqa: E402
from etl import transform  # noqa: E402

EGT = schema.EGT_COLS


def _reports(egt_rows, vessel="GANU", start="2025-05-01", rpm=98.0):
    dates = pd.date_range(start, periods=len(egt_rows), freq="D") + pd.Timedelta(hours=12)
    df = pd.DataFrame(egt_rows, columns=EGT, dtype=float)
    df.insert(0, "Noon_Report_Key", [f"K{vessel}{i:04d}" for i in range(len(df))])
    df["Vessel_Key"], df["Voyage_Key"] = vessel, "V1"
    df["REPORT_DATE"] = dates
    df["Date_Key"] = dates.strftime("%Y%m%d").astype(int)
    df["RPM"] = rpm
    return df


def test_design_example_cyl6_anomaly():
    rng = np.random.default_rng(0)
    # 30 hari histori "normal": setiap silinder sedikit bergeser di sekitar median laporan
    hist = []
    for _ in range(30):
        base = 344 + rng.normal(0, 1)
        hist.append([base + rng.choice([-2, -1, 0, 1, 2]) for _ in range(8)])
    target = [340, 345, 348, 342, 346, 360, 343, 344]           # 01 Jun 2025 dari desain
    df = _reports(hist + [target])
    cyl, summ = compute_thermal(df, ThermalParams())
    last = cyl[cyl["Noon_Report_Key"] == df["Noon_Report_Key"].iloc[-1]].set_index("Cylinder_No")
    assert last["MEDIAN_EGT"].iloc[0] == 344.5
    assert last.loc[6, "CYLINDER_DEVIATION"] == 15.5
    assert last.loc[6, "ANOMALY_STATUS"] == ANOMALY
    assert last.loc[6, "BASELINE_N"] == 30
    z = 0.6745 * (15.5 - last.loc[6, "BASELINE_MEDIAN_DEV"]) / last.loc[6, "MAD"]
    assert abs(z - last.loc[6, "MODIFIED_Z_SCORE"]) < 1e-9
    s = summ.set_index("Noon_Report_Key").loc[df["Noon_Report_Key"].iloc[-1]]
    assert s["Anomaly_Status"] == ANOMALY and s["ANOMALY_CYLINDERS"] >= 1


def test_exact_design_numbers_with_mad_2():
    # baseline deviasi CYL6 = [-2, 0, 2] x 10 -> median 0, MAD 2  =>  MZ = 0.6745*15.5/2 = 5.23
    n_hist = 30
    devs = np.tile([-2.0, 0.0, 2.0], n_hist // 3)
    hist = []
    for d in devs:
        row = [344.0] * 8
        row[5] = 344.0 + d
        hist.append(row)
    df = _reports(hist + [[340, 345, 348, 342, 346, 360, 343, 344]])
    cyl, _ = compute_thermal(df, ThermalParams())
    r = cyl[(cyl["Noon_Report_Key"] == df["Noon_Report_Key"].iloc[-1]) & (cyl["Cylinder_No"] == 6)].iloc[0]
    assert r["BASELINE_MEDIAN_DEV"] == 0.0 and r["MAD"] == 2.0
    assert round(r["MODIFIED_Z_SCORE"], 2) == 5.23 and r["ANOMALY_STATUS"] == ANOMALY
    # silinder lain baseline konstan -> MAD = 0 -> CANNOT_CALCULATE (tidak dikarang)
    r1 = cyl[(cyl["Noon_Report_Key"] == df["Noon_Report_Key"].iloc[-1]) & (cyl["Cylinder_No"] == 1)].iloc[0]
    assert r1["ANOMALY_STATUS"] == CANNOT and r1["STATUS_REASON"] == "MAD_ZERO"


def test_no_lookahead_and_min_baseline():
    df = _reports([[340 + i % 3, 345, 348, 342, 346, 350, 343, 344] for i in range(12)])
    cyl, _ = compute_thermal(df, ThermalParams(min_baseline_obs=10))
    c1 = cyl[cyl["Cylinder_No"] == 1].reset_index(drop=True)
    assert list(c1["BASELINE_N"][:3]) == [0, 1, 2]          # titik sendiri tidak ikut baseline
    assert (c1["ANOMALY_STATUS"][:10] == CANNOT).all()
    assert set(c1["STATUS_REASON"][:10]) == {"INSUFFICIENT_BASELINE"}


def test_six_cylinder_engine_zero_is_missing():
    a = AnalyticsSettings()
    raw = pd.DataFrame([{
        "ID_NOON_REPORT": "ef6e1a7d-1fa9-4dc2-a337-0002870e5c29",
        "FID_VOYAGE": "{f654738d-d4b2-4642-a258-932a29ddc10a}",
        "REPORT_DATE": pd.Timestamp("2024-11-15 05:00"), "AVG_SPEED": 0.0, "RPM": 98.0,
        "ETA_NEXT_PORT": pd.Timestamp("1900-01-01"), "MODIFIED_DATE": pd.Timestamp("1900-01-01"),
        "CREATED_DATE": pd.Timestamp("2024-11-15 13:18:12.267"),
        "AIR_TEMPERATURE": "31° C", "SEA_TEMPERATURE": "31° C", "IS_ACTIVE": True, "IS_ARCHIVED": False,
        "TS": b"\x00\x00\x00\x00\x00\x39\x2b\x1a", "NEXT_PORT": "KARIMUN, INDONESIA",
        "EXH_TEMP_CYL1": 345, "EXH_TEMP_CYL2": 350, "EXH_TEMP_CYL3": 330, "EXH_TEMP_CYL4": 355,
        "EXH_TEMP_CYL5": 375, "EXH_TEMP_CYL6": 370, "EXH_TEMP_CYL7": 0, "EXH_TEMP_CYL8": 0,
        "SWELL_HEIGHT": "1", "MFO_TOTAL_CONS": 5.47, "_CHANGE_TS": pd.Timestamp("2024-11-15 13:18:12.267"),
    }])
    voy = transform.transform_voyages(pd.DataFrame({"ID_VOYAGE": ["F654738D-D4B2-4642-A258-932A29DDC10A"],
                                                    "FCODE_VESSEL": ["bani"]}))
    ves = transform.transform_vessels(pd.DataFrame([{"CODE_VESSEL": "BANI", "NAME": "SAVIR LION", "SPEED": 12,
                                                     "MFO_AT_PORT": 0, "MFO_AT_SEA": 0, "MDO_AT_PORT": 0,
                                                     "MDO_AT_SEA": 0, "FW": 0}]))
    fact, keys, extra, dq = transform.transform_noon_reports(raw, voy, ves, a)
    r = fact.iloc[0]
    assert r["Noon_Report_Key"] == "EF6E1A7D-1FA9-4DC2-A337-0002870E5C29"
    assert r["Vessel_Key"] == "BANI" and r["Date_Key"] == 20241115
    assert r["AIR_TEMPERATURE"] == 31.0 and pd.isna(r["ETA_NEXT_PORT"])
    assert pd.isna(r["EXH_TEMP_CYL7"]) and pd.isna(r["EXH_TEMP_CYL8"])
    assert dq["egt_zero_or_not_reported"] == 2 and r["TS"] == "0x000000000039 2B1A".replace(" ", "")
    assert list(fact.columns) == schema.FACT_LOAD_COLUMNS
    # median dari 6 silinder valid
    _, summ = compute_thermal(fact.assign(REPORT_DATE=pd.to_datetime(fact["REPORT_DATE"])), ThermalParams())
    assert summ.iloc[0]["MEDIAN_EGT"] == 352.5 and summ.iloc[0]["VALID_CYLINDERS"] == 6


def test_egt_invalid_when_rpm_zero():
    a = AnalyticsSettings()
    base = {"FID_VOYAGE": "V1", "REPORT_DATE": pd.Timestamp("2026-07-01 10:00"), "IS_ACTIVE": 1,
            "IS_ARCHIVED": 0, "_CHANGE_TS": pd.Timestamp("2026-07-01"),
            **{f"EXH_TEMP_CYL{i}": 360 for i in range(1, 7)}, "EXH_TEMP_CYL7": 0, "EXH_TEMP_CYL8": 0}
    raw = pd.DataFrame([{**base, "ID_NOON_REPORT": "A", "RPM": 0.0},
                        {**base, "ID_NOON_REPORT": "B", "RPM": 105.0}])
    voy = transform.transform_voyages(pd.DataFrame({"ID_VOYAGE": ["V1"], "FCODE_VESSEL": ["X"]}))
    ves = transform.transform_vessels(pd.DataFrame([{"CODE_VESSEL": "X", "NAME": "X", "SPEED": 0,
                                                     "MFO_AT_PORT": 0, "MFO_AT_SEA": 0, "MDO_AT_PORT": 0,
                                                     "MDO_AT_SEA": 0, "FW": 0}]))
    fact, _, _, dq = transform.transform_noon_reports(raw, voy, ves, a)
    f = fact.set_index("Noon_Report_Key")
    assert f.loc["A", schema.EGT_COLS].isna().all()
    assert f.loc["B", "EXH_TEMP_CYL1"] == 360 and dq["egt_with_rpm_zero"] == 1


def test_uninstalled_cylinders_hidden():
    rows = [[340 + i % 3, 345, 348, 342, 346, 350, np.nan, np.nan] for i in range(15)]
    cyl, summ = compute_thermal(_reports(rows), ThermalParams())
    assert set(cyl["Cylinder_No"]) == {1, 2, 3, 4, 5, 6}
    cyl2, _ = compute_thermal(_reports(rows), ThermalParams(drop_uninstalled_cylinders=False))
    assert set(cyl2["Cylinder_No"]) == set(range(1, 9))


def test_descriptive_matches_design():
    df = pd.DataFrame({"AVG_SPEED": [12, 12.5, 13, 11.5, 12, 12.5, 13, None],
                       "RPM": [76, 78, 80, 74, 76, 78, 80, 82]})
    st = describe(df, ["AVG_SPEED", "RPM"], AnalyticsSettings().valid_ranges).set_index("Variable")
    assert round(st.loc["AVG_SPEED", "Mean"], 2) == 12.36 and st.loc["AVG_SPEED", "Median"] == 12.5
    assert st.loc["AVG_SPEED", "N_Valid"] == 7 and st.loc["AVG_SPEED", "Missing_Pct"] == 12.5
    assert st.loc["RPM", "Mean"] == 78.0 and st.loc["RPM", "Max"] == 82


def test_rolling_baseline_window():
    n, med, mad = rolling_baseline(np.arange(10, dtype=float), 3)
    assert list(n) == [0, 1, 2, 3, 3, 3, 3, 3, 3, 3]
    assert med[5] == 3.0 and mad[5] == 1.0     # window [2,3,4]


def test_rpm_range_baseline_is_separate():
    # 30 laporan di RPM ~95 (rentang 90-100) lalu 1 laporan di RPM 105 (rentang 100-110):
    # laporan RPM 105 tidak punya baseline di rentangnya -> DATA_NOT_VALID (INSUFFICIENT_BASELINE)
    rows = [[340 + i % 3, 345, 348, 342, 346, 350, np.nan, np.nan] for i in range(31)]
    df = _reports(rows)
    df.loc[df.index[-1], "RPM"] = 105.0
    cyl, _ = compute_thermal(df, ThermalParams())
    last = cyl[cyl["Noon_Report_Key"] == df["Noon_Report_Key"].iloc[-1]]
    assert (last["RPM_GROUP"] == "100–110").all()
    assert (last["STATUS_REASON"] == "INSUFFICIENT_BASELINE").all() and (last["BASELINE_N"] == 0).all()
    prev = cyl[cyl["Noon_Report_Key"] == df["Noon_Report_Key"].iloc[-2]]
    assert (prev["RPM_GROUP"] == "90–100").all() and (prev["BASELINE_N"] == 29).all()
    # mode rolling: tanpa pengelompokan RPM
    cyl2, _ = compute_thermal(df, ThermalParams(baseline_mode="rolling"))
    assert (cyl2[cyl2["Noon_Report_Key"] == df["Noon_Report_Key"].iloc[-1]]["BASELINE_N"] == 30).all()


def test_missing_rpm_is_not_valid():
    df = _reports([[340, 345, 348, 342, 346, 350, np.nan, np.nan]] * 15)
    df.loc[df.index[-1], "RPM"] = np.nan
    cyl, summ = compute_thermal(df, ThermalParams())
    last = cyl[cyl["Noon_Report_Key"] == df["Noon_Report_Key"].iloc[-1]]
    assert (last["ANOMALY_STATUS"] == NOT_VALID).all() and (last["STATUS_REASON"] == "RPM_NOT_AVAILABLE").all()


def test_holt_forecast_and_metrics():
    from analytics.forecast import holt_fit, holt_forecast, mape, run_forecast
    y = np.array([10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32], dtype=float)
    m = holt_fit(y, 0.5, 0.5)
    assert np.allclose(holt_forecast(m, 2), [34, 36])          # tren linear sempurna
    assert mape([100, 200], [110, 180]) == 10.0
    monthly = pd.DataFrame({"Year_Month": pd.period_range("2024-01", periods=12, freq="M").astype(str),
                            "Avg_Cons": y, "Valid_Reports": 25})
    res = run_forecast(monthly, horizon=3, test_months=3)
    assert res.mape < 1 and len(res.forecast) == 3
    assert res.forecast["period"].iloc[0] == pd.Timestamp("2025-01-01")


def test_voyage_number_column_detection():
    raw = pd.DataFrame({"ID_VOYAGE": ["{abc}"], "FCODE_VESSEL": ["bani"], "Voyage_No": ["2401"]})
    v = transform.transform_voyages(raw)
    assert v.loc[0, "Voyage_Key"] == "ABC" and v.loc[0, "Vessel_Key"] == "BANI" and v.loc[0, "Voyage_No"] == "2401"
    v2 = transform.transform_voyages(raw.drop(columns="Voyage_No"))
    assert v2.loc[0, "Voyage_No"] is None


def test_environment_helpers():
    from analytics import environment as env
    s = pd.Series([" nne ", "N", "sw", "North East", "xyz", None, "", "NNW"])
    assert env.normalize_direction(s).tolist() == ["NNE", "N", "SW", "NE", env.UNKNOWN, None, None, "NNW"]
    assert env.direction_deg("NNE") == 22.5 and env.direction_deg("w") == 270 and env.direction_deg("?") is None
    assert env.beaufort_desc(3) == "Gentle breeze" and env.beaufort_desc(None) == "—"
    assert [env.beaufort_severity(v) for v in (0, 4, 5, 7, 8, 12, None)] == ["ok", "ok", "warn", "warn",
                                                                            "bad", "bad", ""]
    df = pd.DataFrame({"WIND_DIRECTION": ["N", "n ", "NE", "BAD", None, "E"],
                       "FORCE": [2, 9, 5, 4, 3, None]})
    table, excl = env.wind_rose_table(df)
    assert len(table) == 16 * 4 and table["reports"].sum() == 3
    get = table.set_index(["direction", "beaufort"])["reports"]
    assert get[("N", "Bft 0–3")] == 1 and get[("N", "Bft ≥8")] == 1 and get[("NE", "Bft 4–5")] == 1
    assert excl == {"missing_direction": 1, "unknown_direction": 1, "missing_force": 1, "used": 3}
    rep = pd.DataFrame({"REPORT_DATE": pd.to_datetime(["2026-01-01 12:00", "2026-01-01 13:00", "2026-01-02 12:00"]),
                        "AIR_TEMPERATURE": [30.0, 32.0, None], "SEA_TEMPERATURE": [28.0, 28.0, 27.0],
                        "FORCE": [3.0, 5.0, None], "Anomaly_Status": ["NORMAL", ANOMALY, NOT_VALID],
                        "ANOMALY_CYLINDERS": [0, 2, None]})
    daily = env.daily_environment(rep, ANOMALY, multi=True)
    assert len(daily) == 2 and daily.loc[0, "AIR_TEMPERATURE"] == 31.0 and daily.loc[0, "FORCE"] == 4.0
    assert daily["is_anomaly"].tolist() == [True, False] and daily.loc[0, "ANOMALY_CYLINDERS"] == 2
    assert env.daily_environment(rep, ANOMALY, multi=False)["is_anomaly"].tolist() == [False, True, False]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)