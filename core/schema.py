"""
Definisi star schema (Data Warehouse) — satu sumber kebenaran untuk:
  * daftar kolom & tipe data FACT_NOON_REPORT
  * DDL (CREATE TABLE / INDEX) yang idempotent
  * DDL tabel staging

Star schema:
                 DIM_DATE
                    |
   DIM_VESSEL --- FACT_NOON_REPORT --- DIM_VOYAGE
                    |
          FACT_CYLINDER_ANOMALY  (grain: 1 laporan x 1 silinder)
"""
from __future__ import annotations

N_CYL = 8
EGT_COLS = [f"EXH_TEMP_CYL{i}" for i in range(1, N_CYL + 1)]

# ----------------------------------------------------------------------------
# Kolom FACT_NOON_REPORT
# ----------------------------------------------------------------------------
KEY_COLS = {
    "Noon_Report_Key": "NVARCHAR(36) NOT NULL",   # = ID_NOON_REPORT
    "Date_Key": "INT NOT NULL",                   # YYYYMMDD -> DIM_DATE
    "Voyage_Key": "NVARCHAR(36) NULL",            # = FID_VOYAGE -> DIM_VOYAGE
    "Vessel_Key": "NVARCHAR(20) NOT NULL",        # = V_Voyages.FCODE_VESSEL -> DIM_VESSEL
    "PMS_Noon_Report_ID": "NVARCHAR(100) NULL",
}

DATETIME_COLS = ["REPORT_DATE", "ETA_NEXT_PORT", "CREATED_DATE", "MODIFIED_DATE", "INACTIVE_DATE"]

TEXT_COLS = {
    "WIND_DIRECTION": 20, "SEA_COND": 50, "WEATHER_COND": 50, "CURRENT_DIRECTION": 20,
    "NEXT_PORT": 200, "VC_ENGINE_SPEED": 50, "TANK_CLEANING": 50, "CARGO_HEATING": 50,
    "CREATED_BY": 100, "MODIFIED_BY": 100, "REPORT_TYPE": 50, "TS": 40,
}

INT_COLS = ["IS_ACTIVE", "IS_ARCHIVED"]

# Kolom suhu yang di sumber berbentuk teks, mis. "31° C" -> 31.0
TEXT_NUMERIC_COLS = ["AIR_TEMPERATURE", "SEA_TEMPERATURE"]

NUMERIC_COLS = [
    # Navigasi & posisi
    "LONGITUDE", "LATITUDE", "COURSE_STEER", "AVG_SPEED", "SPEED_OVER_GROUND",
    "GEN_AVERAGE_SPEED", "DIST_OVER_GROUND", "DISTANCE_TO_GO", "TOTAL_MILES", "STEAM",
    # Mesin & operasional
    "RPM", "SLIP", "ENGINE_SPEED", "DISTANCE_ENGINE", "RUN_HOURS", "TOTAL_RUN_HOURS",
    "HOURS_UNDER_WEIGH", "HOURS_PROPELLING", "RUN_ME", "RUN_BOILER", "RUN_AE1", "RUN_AE2",
    "RUN_AE3", "TOTAL_RC", "DRAFT_AFT", "DRAFT_FWD",
    # Konsumsi
    "ME_MFO_CONS", "ME_MDO_CONS", "AE_MFO_CONS", "AE_MDO_CONS", "BOILER_MFO_CONS",
    "BOILER_MDO_CONS", "MESO_MFO_CONS", "MESO_MDO_CONS", "AESO_MFO_CONS", "AESO_MDO_CONS",
    "MECO_MFO_CONS", "MECO_MDO_CONS", "HO_MFO_CONS", "HO_MDO_CONS", "TC_CONS_FO", "TC_CONS_DO",
    "CH_CONS_FO", "CH_CONS_DO", "TANK_CLEANING_CONS", "CARGO_HEATING_CONS", "MFO_TOTAL_CONS",
    # ROB & fresh water
    "ROB_MFO", "ROB_MDO", "ROB_FW", "ROB_MECO", "ROB_MESO", "ROB_AESO", "ROB_MECO_LS",
    "FW_PROD", "FW_PROD_HR", "FW_CONS_HR", "FW_CONS_DAY",
    # Cuaca & lingkungan
    "FORCE", "CURRENT_SPEED", "SWELL_HEIGHT",
    # Aktivitas khusus
    "TANK_CLEANING_HR", "CARGO_HEATING_HR",
    # Suhu gas buang silinder (dibersihkan khusus di transform)
    *EGT_COLS,
]

# Kolom turunan hasil analisis thermal (ringkasan level laporan)
THERMAL_SUMMARY_COLS = {
    "MEDIAN_EGT": "FLOAT NULL",
    "VALID_CYLINDERS": "INT NULL",
    "MAX_ABS_MODIFIED_Z": "FLOAT NULL",
    "ANOMALY_CYLINDERS": "INT NULL",
    "Anomaly_Status": "NVARCHAR(20) NULL",
}

AUDIT_COLS = {"ETL_LOADED_AT": "DATETIME2(0) NULL"}


def fact_column_types() -> dict[str, str]:
    cols: dict[str, str] = dict(KEY_COLS)
    for c in DATETIME_COLS:
        cols[c] = "DATETIME2(3) NULL" if c != "REPORT_DATE" else "DATETIME2(3) NOT NULL"
    for c in NUMERIC_COLS + TEXT_NUMERIC_COLS:
        cols[c] = "FLOAT NULL"
    for c, n in TEXT_COLS.items():
        cols[c] = f"NVARCHAR({n}) NULL"
    for c in INT_COLS:
        cols[c] = "INT NULL"
    cols.update(THERMAL_SUMMARY_COLS)
    cols.update(AUDIT_COLS)
    return cols


FACT_COLUMNS = list(fact_column_types().keys())
FACT_LOAD_COLUMNS = [c for c in FACT_COLUMNS if c not in THERMAL_SUMMARY_COLS]

CYLINDER_FACT_COLS = {
    "Noon_Report_Key": "NVARCHAR(36) NOT NULL",
    "Cylinder_No": "TINYINT NOT NULL",
    "Date_Key": "INT NOT NULL",
    "Voyage_Key": "NVARCHAR(36) NULL",
    "Vessel_Key": "NVARCHAR(20) NOT NULL",
    "REPORT_DATE": "DATETIME2(3) NOT NULL",
    "RPM": "FLOAT NULL",
    "RPM_GROUP": "NVARCHAR(20) NULL",
    "EGT": "FLOAT NULL",
    "MEDIAN_EGT": "FLOAT NULL",
    "CYLINDER_DEVIATION": "FLOAT NULL",
    "BASELINE_N": "INT NULL",
    "BASELINE_MEDIAN_DEV": "FLOAT NULL",
    "MAD": "FLOAT NULL",
    "MODIFIED_Z_SCORE": "FLOAT NULL",
    "ANOMALY_STATUS": "NVARCHAR(20) NOT NULL",
    "STATUS_REASON": "NVARCHAR(40) NOT NULL",
}


# ----------------------------------------------------------------------------
# DDL
# ----------------------------------------------------------------------------
def _create_table(schema: str, name: str, cols: dict[str, str], pk: str) -> str:
    body = ",\n    ".join(f"[{c}] {t}" for c, t in cols.items())
    return (
        f"IF OBJECT_ID(N'[{schema}].[{name}]', N'U') IS NULL\n"
        f"CREATE TABLE [{schema}].[{name}] (\n    {body},\n"
        f"    CONSTRAINT [PK_{name}] PRIMARY KEY ({pk})\n);"
    )


def _create_index(schema: str, table: str, name: str, cols: str, include: str = "") -> str:
    inc = f" INCLUDE ({include})" if include else ""
    return (
        f"IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'{name}' "
        f"AND object_id = OBJECT_ID(N'[{schema}].[{table}]'))\n"
        f"CREATE NONCLUSTERED INDEX [{name}] ON [{schema}].[{table}] ({cols}){inc};"
    )


DIM_VOYAGE_COLS = {
    "Voyage_Key": "NVARCHAR(36) NOT NULL", "FID_VOYAGE": "NVARCHAR(36) NULL",
    "Vessel_Key": "NVARCHAR(20) NOT NULL", "Voyage_No": "NVARCHAR(50) NULL",
    "Voyage_Label": "NVARCHAR(100) NULL",
    "First_Report_Date": "DATETIME2(3) NULL", "Last_Report_Date": "DATETIME2(3) NULL",
    "Report_Count": "INT NULL",
}


def _add_missing_columns(schema: str, table: str, cols: dict[str, str]) -> list[str]:
    """Migrasi ringan: tambahkan kolom baru ke tabel yang sudah ada (versi lama)."""
    out = []
    for c, t in cols.items():
        t_null = t.replace("NOT NULL", "NULL")
        out.append(f"IF OBJECT_ID(N'[{schema}].[{table}]', N'U') IS NOT NULL "
                   f"AND COL_LENGTH(N'[{schema}].[{table}]', N'{c}') IS NULL "
                   f"ALTER TABLE [{schema}].[{table}] ADD [{c}] {t_null};")
    return out


def warehouse_ddl(schema: str = "dw") -> list[str]:
    s = schema
    stmts = [
        f"IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'{s}') EXEC(N'CREATE SCHEMA [{s}]');",
        _create_table(s, "DIM_DATE", {
            "Date_Key": "INT NOT NULL", "Full_Date": "DATE NOT NULL", "Day": "TINYINT NOT NULL",
            "Month": "TINYINT NOT NULL", "Year": "SMALLINT NOT NULL", "Month_Name": "NVARCHAR(12) NULL",
            "Quarter": "TINYINT NULL", "Day_Of_Week": "NVARCHAR(12) NULL", "Year_Month": "CHAR(7) NULL",
        }, "[Date_Key]"),
        _create_table(s, "DIM_VESSEL", {
            "Vessel_Key": "NVARCHAR(20) NOT NULL", "NAME": "NVARCHAR(200) NULL", "SPEED": "FLOAT NULL",
            "MFO_AT_PORT": "FLOAT NULL", "MFO_AT_SEA": "FLOAT NULL", "MDO_AT_PORT": "FLOAT NULL",
            "MDO_AT_SEA": "FLOAT NULL", "FW": "FLOAT NULL",
        }, "[Vessel_Key]"),
        _create_table(s, "DIM_VOYAGE", DIM_VOYAGE_COLS, "[Voyage_Key]"),
        _create_table(s, "FACT_NOON_REPORT", fact_column_types(), "[Noon_Report_Key]"),
        _create_table(s, "FACT_CYLINDER_ANOMALY", CYLINDER_FACT_COLS, "[Noon_Report_Key], [Cylinder_No]"),
        _create_table(s, "ETL_RUN_LOG", {
            "Run_Id": "INT IDENTITY(1,1) NOT NULL", "Started_At": "DATETIME2(0) NOT NULL",
            "Finished_At": "DATETIME2(0) NULL", "Mode": "NVARCHAR(20) NOT NULL",
            "Status": "NVARCHAR(20) NOT NULL", "Rows_Extracted": "INT NULL", "Rows_Loaded": "INT NULL",
            "Rows_Removed": "INT NULL", "Cylinder_Rows": "INT NULL", "Anomalies": "INT NULL",
            "Watermark_From": "DATETIME2(3) NULL", "Watermark_To": "DATETIME2(3) NULL",
            "Message": "NVARCHAR(MAX) NULL",
        }, "[Run_Id]"),
        _create_table(s, "ETL_WATERMARK", {
            "Source_Name": "NVARCHAR(100) NOT NULL", "Last_Change_TS": "DATETIME2(3) NULL",
            "Updated_At": "DATETIME2(0) NULL",
        }, "[Source_Name]"),
    ]
    # migrasi kolom untuk tabel yang dibuat oleh versi program sebelumnya
    stmts += _add_missing_columns(s, "DIM_VOYAGE", DIM_VOYAGE_COLS)
    stmts += _add_missing_columns(s, "FACT_CYLINDER_ANOMALY", CYLINDER_FACT_COLS)
    stmts += _add_missing_columns(s, "FACT_NOON_REPORT", fact_column_types())
    # index - dibuat otomatis, sesuai pola query dashboard (filter tanggal / kapal / voyage)
    stmts += [
        _create_index(s, "FACT_NOON_REPORT", "IX_FNR_Vessel_Date", "[Vessel_Key], [REPORT_DATE]",
                      "[Voyage_Key], [AVG_SPEED], [RPM], [ME_MFO_CONS], [ME_MDO_CONS], [Anomaly_Status]"),
        _create_index(s, "FACT_NOON_REPORT", "IX_FNR_Date", "[REPORT_DATE]",
                      "[Vessel_Key], [Voyage_Key], [Date_Key], [RPM], [SPEED_OVER_GROUND], [ME_MFO_CONS], "
                      "[ME_MDO_CONS], [VALID_CYLINDERS], [Anomaly_Status]"),
        _create_index(s, "FACT_NOON_REPORT", "IX_FNR_Voyage", "[Voyage_Key], [REPORT_DATE]"),
        _create_index(s, "FACT_NOON_REPORT", "IX_FNR_DateKey_Fuel", "[Date_Key]",
                      "[Vessel_Key], [RPM], [ME_MFO_CONS], [ME_MDO_CONS]"),
        _create_index(s, "FACT_CYLINDER_ANOMALY", "IX_FCA_Vessel_Cyl_Date",
                      "[Vessel_Key], [Cylinder_No], [REPORT_DATE]"),
        _create_index(s, "FACT_CYLINDER_ANOMALY", "IX_FCA_Date_Status", "[REPORT_DATE], [ANOMALY_STATUS]",
                      "[Vessel_Key], [Voyage_Key], [Cylinder_No], [STATUS_REASON]"),
        _create_index(s, "DIM_VOYAGE", "IX_DVOY_Vessel", "[Vessel_Key], [First_Report_Date]",
                      "[Voyage_Label], [Report_Count]"),
    ]
    return stmts


def staging_ddl(schema: str = "dw") -> list[str]:
    s = schema
    return [
        f"IF OBJECT_ID(N'[{s}].[STG_NOON_REPORT]', N'U') IS NOT NULL DROP TABLE [{s}].[STG_NOON_REPORT];",
        f"SELECT TOP 0 * INTO [{s}].[STG_NOON_REPORT] FROM [{s}].[FACT_NOON_REPORT];",
        f"IF OBJECT_ID(N'[{s}].[STG_CHANGED_KEYS]', N'U') IS NOT NULL DROP TABLE [{s}].[STG_CHANGED_KEYS];",
        f"CREATE TABLE [{s}].[STG_CHANGED_KEYS] ([Noon_Report_Key] NVARCHAR(36) NOT NULL PRIMARY KEY);",
        f"IF OBJECT_ID(N'[{s}].[STG_THERMAL_SUMMARY]', N'U') IS NOT NULL DROP TABLE [{s}].[STG_THERMAL_SUMMARY];",
        f"CREATE TABLE [{s}].[STG_THERMAL_SUMMARY] ([Noon_Report_Key] NVARCHAR(36) NOT NULL PRIMARY KEY, "
        + ", ".join(f"[{c}] {t}" for c, t in THERMAL_SUMMARY_COLS.items()) + ");",
    ]


def ddl_script(schema: str = "dw", database: str = "COPY_DATA") -> str:
    """Script .sql siap dijalankan di SSMS."""
    header = (
        "-- =====================================================================\n"
        "-- Marine BI Analytics - Star Schema Data Warehouse\n"
        "-- Jalankan di SSMS. Aman dijalankan berulang (idempotent).\n"
        "-- =====================================================================\n"
        f"USE [{database}];\nGO\n\n"
    )
    return header + "\nGO\n\n".join(warehouse_ddl(schema)) + "\nGO\n"