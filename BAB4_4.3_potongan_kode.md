# 4.3 Pembahasan dan Evaluasi Hasil Implementasi Kode

> Catatan penyusunan: nomor gambar di bawah ini (Gambar 4.1, 4.2, dst.) masih nomor urut sementara.
> Sesuaikan dengan nomor gambar terakhir di Bab 4. Semua nomor baris merujuk ke kode saat dokumen ini dibuat.
> Server, username, password, dan connection string asli sudah diganti placeholder (`SERVER_NAME`, `USERNAME`, `PASSWORD`).

---

### 4.3.1 Struktur Kode Program

**Paragraf pengantar**
Aplikasi Marine BI Analytics disusun secara modular. Setiap folder menangani satu tanggung jawab: konfigurasi, koneksi basis data, proses ETL, analitik, akses data, komponen antarmuka, dan halaman web. Pemisahan ini membuat logika perhitungan (ETL, anomali termal, peramalan) bisa diuji tanpa antarmuka web, dan membuat halaman web cukup membaca hasil yang sudah tersimpan di data mart.

**Gambar 4.1 Struktur Folder Program**
```text
skripsi_bi/
├── app.py
├── requirements.txt
├── .streamlit/
│   ├── config.toml
│   ├── secrets.toml            (tidak dilampirkan, berisi kredensial)
│   └── secrets.toml.example
├── config/
│   └── settings.py
├── core/
│   ├── database.py
│   └── schema.py
├── etl/
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   ├── pipeline.py
│   └── auto.py
├── analytics/
│   ├── thermal.py
│   ├── forecast.py
│   └── descriptive.py
├── services/
│   └── data.py
├── ui/
│   ├── theme.py
│   ├── components.py
│   ├── charts.py
│   ├── filters.py
│   └── layout.py
├── views/
│   ├── noon_report.py
│   ├── thermal_anomaly.py
│   ├── forecasting.py
│   ├── etl_pipeline.py
│   ├── overview.py             (tidak terdaftar di menu)
│   └── data_information.py     (tidak terdaftar di menu)
├── scripts/
│   ├── run_etl.py
│   ├── auto_etl.py
│   └── cek_koneksi.py
├── sql/
│   └── create_warehouse.sql
├── docs/
│   ├── RUMUS.md
│   └── UAT.md
└── tests/
    └── test_core.py
```

**Penjelasan fungsi tiap file**

| File | Fungsi |
|---|---|
| `app.py` | Titik masuk aplikasi Streamlit yang mengatur konfigurasi halaman, sidebar, navigasi empat halaman, dan indikator Auto ETL. |
| `requirements.txt` | Daftar pustaka Python yang dibutuhkan (Streamlit, pandas, NumPy, Plotly, SQLAlchemy, pyodbc). |
| `.streamlit/config.toml` | Pengaturan tema warna dan toolbar Streamlit. |
| `.streamlit/secrets.toml` | Konfigurasi koneksi basis data dan parameter analitik yang aktif (tidak dilampirkan karena berisi kredensial). |
| `.streamlit/secrets.toml.example` | Contoh/templat konfigurasi tanpa kredensial. |
| `config/settings.py` | Pusat konfigurasi yang membaca environment variable, `secrets.toml`, atau nilai default untuk basis data, analitik, dan forecasting. |
| `core/database.py` | Membentuk connection string ODBC, membuat engine SQLAlchemy ke SQL Server, dan menyediakan fungsi uji koneksi. |
| `core/schema.py` | Mendefinisikan kolom dan DDL star schema (`DIM_DATE`, `DIM_VESSEL`, `DIM_VOYAGE`, `FACT_NOON_REPORT`, `FACT_CYLINDER_ANOMALY`) beserta tabel log dan staging. |
| `etl/extract.py` | Mengambil data mentah dari tabel sumber `NOON_REPORT_COPY`, `V_Voyages`, dan `vessels` (penuh atau sejak watermark). |
| `etl/transform.py` | Membersihkan data, mengonversi tipe, memvalidasi EGT, serta membentuk kunci dimensi dan tabel fakta. |
| `etl/load.py` | Menulis dimensi dan fakta ke skema `dw` (full atau incremental melalui staging), menyimpan hasil anomali, watermark, dan log ETL. |
| `etl/pipeline.py` | Mengorkestrasi urutan Extract → Transform → Load → Analyze → Finalize dalam satu transaksi dengan penguncian proses. |
| `etl/auto.py` | Memantau tabel sumber secara berkala dan menjalankan ETL incremental otomatis bila ada data baru. |
| `analytics/thermal.py` | Menghitung median EGT, cylinder deviation, historical baseline, MAD, Modified Z-Score, dan status anomali. |
| `analytics/forecast.py` | Mengimplementasikan Double Exponential Smoothing (Holt), grid search α dan β, serta evaluasi MAE dan MAPE. |
| `analytics/descriptive.py` | Menghitung statistik deskriptif dan kelengkapan data (dipakai halaman Data Information). |
| `services/data.py` | Lapisan akses data berisi query berparameter ke data mart dengan cache Streamlit. |
| `ui/theme.py` | Mendefinisikan warna dan CSS tampilan. |
| `ui/components.py` | Menyediakan komponen tampilan seperti kartu KPI, info strip, tile silinder, dan callout. |
| `ui/charts.py` | Membuat grafik Plotly (garis, batang deviasi, grafik EGT) dan peta posisi kapal. |
| `ui/filters.py` | Menampilkan filter global kapal, voyage, dan rentang tanggal yang tetap tersimpan saat berpindah halaman. |
| `ui/layout.py` | Mengecek kesiapan data warehouse sebelum halaman ditampilkan. |
| `views/noon_report.py` | Halaman Noon Report Dashboard (grafik operasional, kondisi termal, peta, tabel, unduh CSV). |
| `views/thermal_anomaly.py` | Halaman Thermal Anomaly (KPI anomali, grafik EGT, cylinder deviation, tabel hasil, unduh CSV). |
| `views/forecasting.py` | Halaman Forecasting (filter cakupan, grafik histori dan ramalan, tabel evaluasi). |
| `views/etl_pipeline.py` | Halaman ETL Pipeline (uji koneksi, pembuatan skema, menjalankan ETL, laporan kualitas data, riwayat). |
| `views/overview.py` | Halaman ringkasan armada yang ada di kode tetapi tidak didaftarkan di menu navigasi. |
| `views/data_information.py` | Halaman statistik deskriptif yang ada di kode tetapi tidak didaftarkan di menu navigasi. |
| `scripts/run_etl.py` | Menjalankan ETL melalui command line (untuk Windows Task Scheduler). |
| `scripts/auto_etl.py` | Menjalankan pemantau Auto ETL tanpa browser. |
| `scripts/cek_koneksi.py` | Mengukur kecepatan koneksi ke beberapa alternatif nama server. |
| `sql/create_warehouse.sql` | Skrip DDL star schema yang dapat dijalankan di SSMS. |
| `docs/RUMUS.md` | Dokumentasi rumus (sebagian sudah tidak sesuai kode, lihat bagian Perbedaan). |
| `docs/UAT.md` | Dokumen skenario User Acceptance Testing. |
| `tests/test_core.py` | Unit test logika anomali, transformasi, statistik deskriptif, dan forecasting tanpa basis data. |

**Hasil** : Screenshot struktur folder pada Explorer VS Code (folder `venv312` dan `__pycache__` disembunyikan atau dipotong).

---

### 4.3.2 Implementasi Kode Koneksi Database dan Proses ETL

**Paragraf pengantar**
Sistem terhubung ke Microsoft SQL Server melalui pyodbc dan SQLAlchemy. Data noon report dari tabel sumber diproses dengan alur ETL (Extract, Transform, Load) lalu disimpan ke data mart berbentuk star schema pada skema `dw`. Proses ETL dapat dijalankan penuh (full) atau bertahap (incremental) berdasarkan watermark waktu perubahan data.

**Gambar 4.2 Potongan Kode Konfigurasi Koneksi Database**
File: config/settings.py, baris 59–69
```python
@dataclass(frozen=True)
class DatabaseSettings:
    server: str = _get("database", "server", r"SERVER_NAME")
    database: str = _get("database", "database", "DATABASE_NAME")
    driver: str = _get("database", "driver", "auto")  # "auto" = deteksi otomatis
    trusted_connection: bool = _get("database", "trusted_connection", True)
    username: str = _get("database", "username", "USERNAME")
    password: str = _get("database", "password", "PASSWORD")
    encrypt: bool = _get("database", "encrypt", True)
    trust_server_certificate: bool = _get("database", "trust_server_certificate", True)
    timeout: int = _get("database", "timeout", 30)
```

**Penjelasan**
Kelas `DatabaseSettings` menyimpan parameter koneksi. Fungsi `_get()` mengambil nilai dari environment variable terlebih dahulu, lalu dari file `.streamlit/secrets.toml`, dan terakhir dari nilai default. Dengan cara ini, kredensial tidak ditulis langsung di dalam kode program. Atribut `trusted_connection` menentukan apakah autentikasi memakai akun Windows (Integrated Security) atau SQL Server Authentication dengan username dan password.

**Hasil** : Tidak ada output langsung. Konfigurasi ini terlihat pada kartu *Connection* di halaman ETL Pipeline (server dan database tampil, password tidak ditampilkan).

---

**Gambar 4.3 Potongan Kode Pembentukan Koneksi ODBC dan Engine**
File: core/database.py, baris 47–72
```python
def build_odbc_string(cfg: DatabaseSettings) -> str:
    driver = detect_driver(cfg.driver)
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={cfg.server}",
        f"DATABASE={cfg.database}",
        f"Connection Timeout={cfg.timeout}",
        "APP=Marine BI Analytics",
    ]
    if cfg.trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        parts += [f"UID={cfg.username}", f"PWD={cfg.password}"]
    # Driver lama "SQL Server" tidak mendukung opsi Encrypt modern
    if driver != "SQL Server":
        parts.append(f"Encrypt={'yes' if cfg.encrypt else 'no'}")
        parts.append(
            f"TrustServerCertificate={'yes' if cfg.trust_server_certificate else 'no'}"
        )
    return ";".join(parts) + ";"


def make_engine(cfg: DatabaseSettings) -> Engine:
    odbc = build_odbc_string(cfg)
    url = "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(odbc)
    return create_engine(url, fast_executemany=True, pool_pre_ping=True, future=True)
```

**Penjelasan**
Fungsi `build_odbc_string()` menyusun connection string ODBC dari konfigurasi. Driver dipilih otomatis oleh `detect_driver()` dengan urutan prioritas ODBC Driver 18, 17, lalu 13. Contoh hasilnya: `DRIVER={ODBC Driver 18 for SQL Server};SERVER=SERVER_NAME;DATABASE=DATABASE_NAME;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;`. Fungsi `make_engine()` membungkus string tersebut menjadi URL `mssql+pyodbc` untuk SQLAlchemy. Opsi `fast_executemany=True` mempercepat penulisan data dalam jumlah besar, sedangkan `pool_pre_ping=True` memeriksa koneksi sebelum dipakai agar koneksi yang terputus tidak menyebabkan galat.

**Hasil** : Tombol *Test connection* di halaman ETL Pipeline menampilkan pesan "Connected to SERVER_NAME / DATABASE_NAME · SQL Server *versi* (*edisi*)". Ambil screenshot pesan berhasil tersebut (samarkan nama server bila perlu).

---

**Gambar 4.4 Potongan Kode Definisi Star Schema**
File: core/schema.py, baris 159–175
```python
def warehouse_ddl(schema: str = "dw") -> list[str]:
    s = schema
    stmts = [
        f"IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'{s}') EXEC(N'CREATE SCHEMA [{s}]');",
        _create_table(s, "DIM_DATE", {
            "Date_Key": "INT NOT NULL", "Full_Date": "DATE NOT NULL", "Day": "TINYINT NOT NULL",
            # ... (Month, Year, Month_Name, Quarter, Day_Of_Week, Year_Month)
        }, "[Date_Key]"),
        _create_table(s, "DIM_VESSEL", {
            "Vessel_Key": "NVARCHAR(20) NOT NULL", "NAME": "NVARCHAR(200) NULL", "SPEED": "FLOAT NULL",
            # ... (MFO_AT_PORT, MFO_AT_SEA, MDO_AT_PORT, MDO_AT_SEA, FW)
        }, "[Vessel_Key]"),
        _create_table(s, "DIM_VOYAGE", DIM_VOYAGE_COLS, "[Voyage_Key]"),
        _create_table(s, "FACT_NOON_REPORT", fact_column_types(), "[Noon_Report_Key]"),
        _create_table(s, "FACT_CYLINDER_ANOMALY", CYLINDER_FACT_COLS, "[Noon_Report_Key], [Cylinder_No]"),
        # ... (ETL_RUN_LOG, ETL_WATERMARK, migrasi kolom, dan index)
    ]
```

**Penjelasan**
Fungsi `warehouse_ddl()` menghasilkan perintah DDL untuk membuat skema `dw` beserta tiga tabel dimensi (`DIM_DATE`, `DIM_VESSEL`, `DIM_VOYAGE`) dan dua tabel fakta. `FACT_NOON_REPORT` memiliki grain satu baris per noon report dengan primary key `Noon_Report_Key`. `FACT_CYLINDER_ANOMALY` memiliki grain satu baris per laporan per silinder dengan primary key gabungan `(Noon_Report_Key, Cylinder_No)`, karena satu laporan memuat hingga delapan nilai EGT. Setiap tabel dibuat dengan pola `IF OBJECT_ID(...) IS NULL CREATE TABLE`, sehingga perintah aman dijalankan berulang kali (idempotent).

**Hasil** : Screenshot Object Explorer SSMS yang menampilkan tabel `dw.DIM_DATE`, `dw.DIM_VESSEL`, `dw.DIM_VOYAGE`, `dw.FACT_NOON_REPORT`, dan `dw.FACT_CYLINDER_ANOMALY`. Bisa juga screenshot pesan "Star schema [dw] is ready." setelah tombol *Create / verify schema* ditekan.

---

**Gambar 4.5 Potongan Kode Extract Data Noon Report (Full dan Incremental)**
File: etl/extract.py, baris 12–16 dan 48–64
```python
# Timestamp perubahan baris sumber: ambil yang terbaru antara CREATED_DATE & MODIFIED_DATE
CHANGE_TS_EXPR = (
    "CASE WHEN ISNULL(MODIFIED_DATE, '19000101') > ISNULL(CREATED_DATE, '19000101') "
    "THEN MODIFIED_DATE ELSE CREATED_DATE END"
)
# ...
def extract_noon_reports(engine: Engine, cfg: DatabaseSettings,
                         since: dt.datetime | None = None,
                         chunksize: int = 50_000) -> pd.DataFrame:
    # ...
    sql = f"SELECT *, {CHANGE_TS_EXPR} AS _CHANGE_TS FROM {_src(cfg, cfg.source_noon_table)}"
    params = {}
    if since is not None:
        sql += f" WHERE {CHANGE_TS_EXPR} > :since"
        params["since"] = since
    chunks = []
    with engine.connect() as conn:
        for chunk in pd.read_sql(text(sql), conn, params=params, chunksize=chunksize):
            chunks.append(chunk)
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)
```

**Penjelasan**
Ekspresi `CHANGE_TS_EXPR` menentukan waktu perubahan terakhir setiap baris, yaitu nilai terbesar antara `CREATED_DATE` dan `MODIFIED_DATE`. Pada mode full, parameter `since` bernilai `None` sehingga seluruh baris `NOON_REPORT_COPY` diambil. Pada mode incremental, query ditambah klausa `WHERE ... > :since` sehingga hanya baris yang dibuat atau diubah setelah watermark terakhir yang diambil. Parameter dikirim sebagai bind parameter (`:since`) agar aman dari SQL injection. Data dibaca per 50.000 baris (`chunksize`) agar penggunaan memori tetap terkendali.

**Hasil** : Pada progress ETL tampil tahap "Extract: noon report (all rows)" untuk full, atau "Extract: noon report (changed since …)" untuk incremental. Metrik *Rows extracted* menunjukkan jumlah baris yang diambil.

---

**Gambar 4.6 Potongan Kode Transform: Validasi EGT dan RPM**
File: etl/transform.py, baris 175–192
```python
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
```

**Penjelasan**
Kode ini menerapkan validasi data EGT. Untuk setiap kolom `EXH_TEMP_CYL1` sampai `EXH_TEMP_CYL8`, nilai 0 atau negatif dianggap tidak dilaporkan, misalnya CYL7–CYL8 pada mesin enam silinder. Nilai di luar rentang `egt_valid_min`–`egt_valid_max` (100–600 °C) dianggap tidak valid. Kedua jenis nilai tersebut diganti NULL melalui `v.mask()` sehingga tidak ikut dalam perhitungan median. Selain itu, bila RPM bernilai 0 (mesin tidak beroperasi), seluruh nilai EGT pada laporan tersebut juga dijadikan NULL. Jumlah setiap kasus dicatat di variabel `dq` dan ditampilkan sebagai laporan kualitas data.

**Hasil** : Tabel *Data quality report* di halaman ETL Pipeline menampilkan baris "EGT values = 0 / not reported → NULL", "EGT outside 100–600 °C → NULL", dan "Reports with EGT but RPM = 0 → EGT set to NULL" beserta jumlahnya. Ambil screenshot tabel tersebut setelah Full reload.

---

**Gambar 4.7 Potongan Kode Transform: Pembentukan Kunci Dimensi**
File: etl/transform.py, baris 206–225
```python
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
```

**Penjelasan**
Hanya laporan aktif dan tidak diarsipkan (`IS_ACTIVE = 1`, `IS_ARCHIVED ≠ 1`) yang dimuat ke tabel fakta. Laporan tanpa `REPORT_DATE` dibuang karena tidak dapat dihubungkan ke `DIM_DATE`. `Date_Key` dibentuk dengan format `YYYYMMDD` dari `REPORT_DATE`, misalnya 20 Juli 2026 menjadi `20260720`. `Vessel_Key` diperoleh dengan memetakan `FID_VOYAGE` ke `V_Voyages.FCODE_VESSEL`. Laporan yang voyage atau kapalnya tidak ditemukan di data master tetap disimpan dengan `Vessel_Key = 'UNKNOWN'` agar tidak ada data yang hilang diam-diam.

**Hasil** : Baris "Inactive / archived reports excluded", "Rows dropped: missing REPORT_DATE", dan "Reports whose FID_VOYAGE is not in V_Voyages" pada *Data quality report*.

---

**Gambar 4.8 Potongan Kode Load Incremental (Delete-then-Insert)**
File: etl/load.py, baris 108–131
```python
def load_fact_incremental(conn: Connection, fact: pd.DataFrame, changed_keys: list[str],
                          dw: str) -> tuple[int, int, set[str]]:
    # ...
    if not changed_keys:
        return 0, 0, set()
    insert_df(conn, pd.DataFrame({"Noon_Report_Key": changed_keys}), "STG_CHANGED_KEYS", dw)
    insert_df(conn, fact, "STG_NOON_REPORT", dw)
    old_vessels = conn.execute(text(f"""
        SELECT DISTINCT f.Vessel_Key FROM [{dw}].[FACT_NOON_REPORT] f
        JOIN [{dw}].[STG_CHANGED_KEYS] k ON k.Noon_Report_Key = f.Noon_Report_Key;""")).scalars().all()
    conn.execute(text(f"""
        DELETE c FROM [{dw}].[FACT_CYLINDER_ANOMALY] c
        JOIN [{dw}].[STG_CHANGED_KEYS] k ON k.Noon_Report_Key = c.Noon_Report_Key;"""))
    removed = conn.execute(text(f"""
        DELETE f FROM [{dw}].[FACT_NOON_REPORT] f
        JOIN [{dw}].[STG_CHANGED_KEYS] k ON k.Noon_Report_Key = f.Noon_Report_Key;""")).rowcount
    cols = ", ".join(f"[{c}]" for c in schema.FACT_LOAD_COLUMNS)
    conn.execute(text(f"INSERT INTO [{dw}].[FACT_NOON_REPORT] ({cols}) "
                      f"SELECT {cols} FROM [{dw}].[STG_NOON_REPORT];"))
    affected = set(old_vessels) | set(fact["Vessel_Key"].dropna())
    return len(fact), int(removed or 0), affected
```

**Penjelasan**
Pada mode incremental, kunci laporan yang berubah dan data hasil transformasi lebih dulu dimasukkan ke tabel staging (`STG_CHANGED_KEYS` dan `STG_NOON_REPORT`). Baris versi lama di `FACT_CYLINDER_ANOMALY` dan `FACT_NOON_REPORT` kemudian dihapus melalui JOIN dengan staging, lalu versi baru disisipkan dari `STG_NOON_REPORT`. Pola delete-then-insert ini mencegah duplikasi data ketika sebuah laporan diedit di sistem sumber. Fungsi juga mengembalikan daftar kapal yang terdampak, sehingga perhitungan anomali hanya diulang untuk kapal tersebut. Pada mode full, fungsi `load_fact_full()` (baris 102–105) mengosongkan tabel dengan `TRUNCATE` lalu memuat ulang seluruh data.

**Hasil** : Metrik *Reports loaded* dan *Old versions replaced* pada halaman ETL Pipeline setelah ETL incremental.

---

**Gambar 4.9 Potongan Kode Orkestrasi Pipeline ETL**
File: etl/pipeline.py, baris 124–178 (baris `step(...)` untuk progress bar dihilangkan)
```python
        # ---------------- EXTRACT ----------------
        vessels_raw = extract.extract_vessels(engine, db)
        voyages_raw = extract.extract_voyages(engine, db)
        noon_raw = extract.extract_noon_reports(engine, db, since=wm_from)
        # ---------------- TRANSFORM ----------------
        dim_vessel = transform.transform_vessels(vessels_raw)
        dim_voyage = transform.transform_voyages(voyages_raw)
        fact, changed_keys, extra_voy, dq = transform.transform_noon_reports(
            noon_raw, dim_voyage, dim_vessel, an)
        # ...
        # ---------------- LOAD + ANALYZE (1 transaksi) ----------------
        with engine.begin() as conn:
            load.load_dim_vessel(conn, dim_vessel, dw)
            load.load_dim_voyage(conn, dim_voyage, dw)
            if mode == "full":
                res.rows_loaded = load.load_fact_full(conn, fact, dw)
                vessels_to_compute = None
            else:
                res.rows_loaded, res.rows_removed, affected = load.load_fact_incremental(
                    conn, fact, changed_keys, dw)
                vessels_to_compute = sorted(affected)
            if vessels_to_compute is None or vessels_to_compute:
                egt_df = load.read_egt_for_vessels(conn, dw, vessels_to_compute)
                cyl_df, summary_df = compute_thermal(egt_df, params)
                res.cylinder_rows = load.load_thermal(conn, cyl_df, summary_df, vessels_to_compute, dw)
            # ...
            load.rebuild_dim_date(conn, dw, transform.build_date_dim)
            load.refresh_voyage_attributes(conn, dw)
            load.set_watermark(conn, dw, res.watermark_to)
```

**Penjelasan**
Fungsi `run_etl()` menjalankan seluruh tahap secara berurutan. Tahap Extract mengambil data dari tiga tabel sumber, lalu tahap Transform membentuk tabel dimensi dan fakta. Tahap Load dan Analyze dijalankan di dalam satu transaksi (`engine.begin()`), sehingga bila terjadi galat di tengah proses, seluruh perubahan dibatalkan (rollback) dan data mart tidak berada dalam kondisi setengah jadi. Setelah fakta dimuat, histori EGT dibaca kembali untuk menghitung anomali termal (`compute_thermal`) dan hasilnya disimpan ke `FACT_CYLINDER_ANOMALY`. Tahap terakhir membangun ulang `DIM_DATE` dari rentang tanggal laporan, memperbarui atribut voyage, dan menyimpan watermark baru untuk ETL incremental berikutnya.

**Hasil** : Progress bar dan daftar tahap (Extract → Transform → Load → Analyze → Finalize) di halaman ETL Pipeline, diakhiri status **SUCCESS** beserta durasi. Ambil screenshot kotak status ETL dan lima metrik hasil (*Rows extracted, Reports loaded, Old versions replaced, Cylinder rows scored, Anomalies*).

---

**Gambar 4.10 Potongan Kode Auto ETL**
File: etl/auto.py, baris 38–54
```python
def check_new_data(engine: Engine, db: DatabaseSettings) -> CheckResult:
    # ...
    wm = load.get_watermark(engine, db.dw_schema)
    if wm is None:
        return CheckResult(None, 0, None)
    n, latest = extract.count_changes_since(engine, db, wm)
    return CheckResult(wm, n, latest)


def run_if_new_data(engine: Engine, db: DatabaseSettings, an: AnalyticsSettings,
                    progress: ProgressFn | None = None) -> tuple[CheckResult, ETLResult | None]:
    chk = check_new_data(engine, db)
    if chk.new_rows == 0:
        return chk, None
    return chk, run_etl(engine, db, an, mode="incremental", progress=progress)
```

**Penjelasan**
Fungsi `check_new_data()` membaca watermark terakhir, lalu menghitung jumlah baris sumber yang berubah setelah watermark tersebut dengan query `COUNT_BIG(*)` yang ringan. Jika ada data baru, ETL incremental dijalankan otomatis. Pengecekan ini dilakukan oleh thread latar belakang `AutoETLWatcher` setiap 60 detik (`interval_seconds`) selama aplikasi berjalan.

**Hasil** : Indikator "🟢 Auto ETL on · checked *jam*" di sidebar dan kartu *Auto ETL* di halaman ETL Pipeline.

---

### 4.3.3 Implementasi Kode Perhitungan KPI

**Paragraf pengantar**
KPI (Key Performance Indicator) yang ditampilkan sistem berupa jumlah laporan, kecepatan operasional, RPM, total konsumsi bahan bakar main engine, serta ringkasan hasil deteksi anomali. Kolom turunan KPI dihitung di lapisan akses data agar konsisten di semua halaman.

**Gambar 4.11 Potongan Kode Kolom Turunan KPI (Kecepatan Operasional dan Total Konsumsi ME)**
File: services/data.py, baris 50–60
```python
def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Kolom turunan untuk dashboard (bukan bagian rumus anomali)."""
    if df.empty:
        return df
    sc = speed_col()
    if sc in df.columns:
        df["OPERATIONAL_SPEED"] = df[sc]
    if {"ME_MFO_CONS", "ME_MDO_CONS"} <= set(df.columns):
        both_null = df["ME_MFO_CONS"].isna() & df["ME_MDO_CONS"].isna()
        df["ME_TOTAL_CONS"] = (df["ME_MFO_CONS"].fillna(0) + df["ME_MDO_CONS"].fillna(0)).mask(both_null)
    return df
```

**Penjelasan**
Fungsi `add_derived()` membentuk dua kolom KPI. `OPERATIONAL_SPEED` diambil dari kolom kecepatan yang dikonfigurasi (`speed_column`), yaitu `SPEED_OVER_GROUND` secara default, karena kolom `AVG_SPEED` pada data sumber hampir selalu bernilai 0. `ME_TOTAL_CONS` adalah konsumsi bahan bakar main engine per laporan, yaitu `ME_MFO_CONS + ME_MDO_CONS`. Jika salah satu kolom kosong, nilainya dianggap 0. Jika keduanya kosong, hasilnya tetap NULL (`mask(both_null)`), sehingga laporan tanpa data konsumsi tidak terbaca sebagai konsumsi 0.

**Hasil** : Kolom `SPEED_OVER_GROUND (knots)` dan `ME_TOTAL_CONS (MT)` pada tabel *Detailed Noon Reports* di halaman Noon Report.

---

**Gambar 4.12 Potongan Kode KPI Halaman Noon Report**
File: views/noon_report.py, baris 30–31, 47–48, dan 77–79
```python
n_vessels = df["Vessel_Key"].nunique()
n_voyages = df["Voyage_Key"].nunique()
# ...
with c_kpi:
    ui.kpi("Total Noon Reports", f"{len(df):,} reports", f"{date_txt} · {n_voyages} voyages")
# ...
tot_mfo, tot_mdo = df["ME_MFO_CONS"].sum(min_count=1), df["ME_MDO_CONS"].sum(min_count=1)
ui.foot(f"Total ME consumption = ΣME_MFO_CONS + ΣME_MDO_CONS over {len(df):,} selected records = "
        f"{ui.fmt_num(tot_mfo)} + {ui.fmt_num(tot_mdo)} MT. Missing values are not imputed.")
```

**Penjelasan**
KPI *Total Noon Reports* menghitung jumlah laporan dan jumlah voyage unik pada rentang filter. Total konsumsi main engine dihitung sebagai ΣME_MFO_CONS + ΣME_MDO_CONS. Parameter `min_count=1` membuat hasilnya NULL (bukan 0) bila seluruh nilai kosong. Nilai kosong tidak diisi dengan tebakan (tidak diimputasi).

**Hasil** : Kartu KPI *Total Noon Reports* dan catatan "Total ME consumption = …" di bawah grafik konsumsi. Ambil screenshot bagian atas halaman Noon Report.

---

**Gambar 4.13 Potongan Kode KPI Halaman Thermal Anomaly**
File: views/thermal_anomaly.py, baris 48–62
```python
n_obs = len(cyl)
n_anom = int((cyl["ANOMALY_STATUS"] == ANOMALY).sum())
n_norm = int((cyl["ANOMALY_STATUS"] == NORMAL).sum())
n_na = int((cyl["ANOMALY_STATUS"] == NOT_VALID).sum())
n_rep_anom = int((noon["Anomaly_Status"] == ANOMALY).sum())
k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.kpi("Cylinder observations", f"{n_obs:,}", f"{len(noon):,} reports × installed cylinders")
with k2:
    ui.kpi("Anomalies", f"{n_anom:,}", f"{n_anom / max(n_anom + n_norm, 1) * 100:.2f}% of calculable · "
           f"{n_rep_anom:,} reports flagged")
with k3:
    ui.kpi("Normal", f"{n_norm:,}", "|Modified Z| ≤ 3.5")
with k4:
    ui.kpi("Data not valid", f"{n_na:,}", "criteria not met (EGT/RPM, baseline, MAD = 0)")
```

**Penjelasan**
Empat KPI anomali dihitung dari tabel `FACT_CYLINDER_ANOMALY`, yaitu jumlah observasi silinder, jumlah ANOMALY, jumlah NORMAL, dan jumlah DATA_NOT_VALID. Persentase anomali dihitung terhadap observasi yang dapat dihitung saja (ANOMALY + NORMAL), bukan terhadap seluruh observasi. Dengan begitu, data yang tidak valid tidak memperkecil persentase anomali secara semu. Fungsi `max(..., 1)` mencegah pembagian dengan nol.

**Hasil** : Empat kartu KPI di bagian atas halaman Thermal Anomaly. Ambil screenshot bagian tersebut.

> KPI lain seperti SFOC, konsumsi per mil laut, atau efisiensi per voyage **tidak ditemukan di kode**.

---

### 4.3.4 Implementasi Kode Deteksi Anomali Termal

**Paragraf pengantar**
Deteksi anomali termal dilakukan pada suhu gas buang (EGT) setiap silinder main engine. Perhitungan berurutan dari validasi data, median EGT per laporan, cylinder deviation, historical baseline, MAD, Modified Z-Score, hingga penentuan status. Seluruh perhitungan berada di file `analytics/thermal.py` dan dijalankan pada tahap Analyze dalam ETL.

**Gambar 4.14 Potongan Kode Parameter Deteksi Anomali**
File: analytics/thermal.py, baris 43–53
```python
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
```

**Penjelasan**
Kelas `ThermalParams` menampung parameter metode: minimal empat silinder valid per laporan, baseline maksimal 60 data terakhir, konstanta 0,6745 dan ambang 3,5 untuk Modified Z-Score, serta pengelompokan baseline per rentang RPM selebar 10. Nilai yang dipakai saat aplikasi berjalan diambil dari konfigurasi melalui `ThermalParams.from_settings()`. **Perhatian:** pada konfigurasi yang aktif saat verifikasi, `min_baseline_obs` bernilai **20**, bukan 10 seperti default di potongan kode ini (lihat bagian Perbedaan Kode dengan Skripsi).

**Hasil** : Kartu *Analysis parameters* di halaman ETL Pipeline yang menampilkan nilai parameter aktif.

---

**Gambar 4.15 Potongan Kode Median EGT dan Cylinder Deviation**
File: analytics/thermal.py, baris 73–84
```python
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
```

**Penjelasan**
Input berupa matriks EGT berukuran (jumlah laporan × 8 silinder). Nilai yang tidak valid sudah berupa NaN dari tahap transformasi. `np.nanmedian()` menghitung median EGT setiap laporan hanya dari silinder yang valid. Bila jumlah silinder valid kurang dari `min_valid` (4), median dianggap tidak tersedia. Baris `dev = egt - med[:, None]` mengimplementasikan Cylinder Deviation (persamaan 10), yaitu $D_i = EGT_i - \tilde{M}_r$. Deviasi ini **bertanda**: positif berarti silinder lebih panas dari median laporan, negatif berarti lebih dingin.

**Hasil** : Kolom `MEDIAN_EGT (°C)` dan `CYLINDER_DEVIATION (°C)` di *Thermal Anomaly Results Table*, serta grafik batang *Cylinder Deviation*. Ambil screenshot grafik *Cylinder Deviation* untuk laporan CAPIBARA 20 Juli 2026.

---

**Gambar 4.16 Potongan Kode Kelompok RPM dan Historical Baseline**
File: analytics/thermal.py, baris 62–70 dan 164–177
```python
def rpm_group(rpm: np.ndarray, width: float) -> tuple[np.ndarray, np.ndarray]:
    # ...
    rpm = np.asarray(rpm, dtype=float)
    ok = np.isfinite(rpm) & (rpm > 0)
    lo = np.where(ok, np.floor(np.where(ok, rpm, 0) / width) * width, np.nan)
    label = np.array([f"{a:g}–{a + width:g}" if np.isfinite(a) else "" for a in lo], dtype=object)
    return lo, label
# ...
    # ----- historical baseline per (kapal, silinder[, rentang RPM]), hanya deviasi valid -----
    group_keys = ["Vessel_Key", "Cylinder_No", "_rpm_lo"]
    long = long.sort_values([*group_keys, "_order"], kind="mergesort")
    valid_mask = np.isfinite(long["CYLINDER_DEVIATION"].to_numpy())
    valid_rows = long[valid_mask]
    # ...
    pos = 0
    for _, grp in valid_rows.groupby(group_keys, sort=False):
        n_b, m_b, mad_b = rolling_baseline(grp["CYLINDER_DEVIATION"].to_numpy(), params.baseline_window)
        k = len(grp)
        n_base_all[pos:pos + k], med_all[pos:pos + k], mad_all[pos:pos + k] = n_b, m_b, mad_b
        pos += k
```

**Penjelasan**
Fungsi `rpm_group()` mengelompokkan RPM ke rentang selebar 10. Contohnya, RPM 108,6 masuk rentang 100–110. Data deviasi kemudian dikelompokkan berdasarkan kombinasi kapal, nomor silinder, dan rentang RPM, lalu diurutkan menurut waktu laporan. Setiap kelompok diproses oleh `rolling_baseline()` sehingga baseline sebuah silinder hanya berisi histori silinder yang sama, pada kapal yang sama, dan pada kondisi beban mesin yang sebanding.

**Hasil** : Kolom `RPM range` dan `BASELINE_N` pada *Thermal Anomaly Results Table*.

---

**Gambar 4.17 Potongan Kode Rolling Baseline dan MAD**
File: analytics/thermal.py, baris 87–103
```python
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
```

**Penjelasan**
Untuk setiap observasi ke-i, baseline B adalah maksimal 60 deviasi valid **sebelum** observasi tersebut (`dev_valid[i-window : i]`). Observasi yang sedang dinilai tidak ikut dalam baseline-nya sendiri (tanpa *look-ahead*). Deret diberi padding NaN sepanjang `window` di depan, lalu `sliding_window_view` membentuk jendela geser. Dari setiap jendela dihitung median baseline, Median(B), dan MAD $= \operatorname{Median}(|B - \operatorname{Median}(B)|)$ sesuai persamaan MAD pada Bab 2. `n_base` mencatat jumlah data baseline yang tersedia.

**Hasil** : Kolom `BASELINE_N`, `BASELINE_MEDIAN_DEV (°C)`, dan `MAD (°C)` pada *Thermal Anomaly Results Table*.

---

**Gambar 4.18 Potongan Kode Modified Z-Score dan Status Anomali**
File: analytics/thermal.py, baris 136–139 dan 183–203
```python
    use_rpm = params.baseline_mode == "rpm_bin"
    rpm_ok_rep = (np.isfinite(rpm) & (rpm > 0)) if use_rpm else np.ones(len(rpm), dtype=bool)
    # Laporan tanpa RPM valid tidak diteruskan ke analisis (kriteria validasi proposal)
    dev = np.where(rpm_ok_rep[:, None], dev, np.nan)
    # ...
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
```

**Penjelasan**
Laporan dengan RPM kosong atau 0 tidak diteruskan ke analisis. Modified Z-Score dihitung dengan baris `z = 0.6745 * (d - bmed) / mad`, sesuai persamaan 14: $M_i = \dfrac{0{,}6745\,(D_i - \operatorname{Median}(B))}{MAD}$. Nilai hanya dihitung bila seluruh syarat terpenuhi (`can`): EGT valid, RPM > 0, median tersedia (≥ 4 silinder valid), jumlah baseline ≥ `min_baseline_obs`, dan MAD > 0. Status ditentukan dengan aturan: ANOMALY jika |M| > 3,5, NORMAL jika |M| ≤ 3,5, dan DATA_NOT_VALID jika syarat tidak terpenuhi. Kolom `reason` mencatat penyebab DATA_NOT_VALID agar status tidak pernah dikarang. Di tingkat laporan (baris 236–238), sebuah laporan berstatus ANOMALY bila minimal satu silinder berstatus ANOMALY.

**Hasil** : Kolom `MODIFIED_Z_SCORE` dan `ANOMALY_STATUS` pada *Thermal Anomaly Results Table*, lingkaran merah pada grafik *Historical exhaust gas temperature*, dan kotak merah (callout) "CYL4 is flagged under the historical baseline" untuk laporan CAPIBARA 20 Juli 2026. Ambil juga screenshot bagian *Calculation context* → *Worked example*.

---

### 4.3.5 Implementasi Kode Peramalan Konsumsi Bahan Bakar

**Paragraf pengantar**
Peramalan konsumsi bahan bakar main engine dilakukan pada data bulanan dengan metode Double Exponential Smoothing (Holt). Parameter α dan β dipilih dengan grid search, lalu model dievaluasi menggunakan MAPE dan MAE pada beberapa bulan terakhir sebagai data uji.

**Gambar 4.19 Potongan Kode Agregasi Bulanan Konsumsi Bahan Bakar**
File: services/data.py, baris 238–256
```python
    return _read(f"""
        WITH x AS (
            SELECT d.Year_Month, f.RPM, f.REPORT_DATE,
                   CASE WHEN f.ME_MFO_CONS IS NULL AND f.ME_MDO_CONS IS NULL THEN NULL
                        ELSE ISNULL(f.ME_MFO_CONS, 0) + ISNULL(f.ME_MDO_CONS, 0) END AS ME_TOTAL
            FROM [{dw}].[FACT_NOON_REPORT] f
            JOIN [{dw}].[DIM_DATE] d ON d.Date_Key = f.Date_Key
            WHERE 1 = 1 {vessel_sql}
        )
        SELECT Year_Month,
               COUNT(*)                                                         AS All_Reports,
               SUM(CASE WHEN RPM > 0 AND ME_TOTAL > 0 AND ME_TOTAL <= :mx THEN 1 ELSE 0 END) AS Valid_Reports,
               SUM(CASE WHEN RPM > 0 AND ME_TOTAL > :mx THEN 1 ELSE 0 END)       AS Outlier_Reports,
               AVG(CASE WHEN RPM > 0 AND ME_TOTAL > 0 AND ME_TOTAL <= :mx THEN ME_TOTAL END) AS Avg_Cons,
               SUM(CASE WHEN RPM > 0 AND ME_TOTAL > 0 AND ME_TOTAL <= :mx THEN ME_TOTAL ELSE 0 END) AS Total_Cons,
               MAX(REPORT_DATE)                                                  AS Last_Report
        FROM x
        GROUP BY Year_Month
        ORDER BY Year_Month""", p)
```

**Penjelasan**
Query ini menggabungkan `FACT_NOON_REPORT` dengan `DIM_DATE` untuk mengelompokkan laporan per bulan (`Year_Month`). Konsumsi per laporan adalah `ME_MFO_CONS + ME_MDO_CONS`. Laporan valid adalah laporan dengan RPM > 0 dan konsumsi di antara 0 dan `fuel_valid_max` (100 MT). Nilai di atas 100 MT dihitung sebagai *outlier* (kemungkinan salah input). Query menghasilkan dua ukuran, yaitu `Total_Cons` (jumlah) dan `Avg_Cons` (rata-rata per laporan valid). **Nilai yang diramal adalah `Avg_Cons`**, yaitu rata-rata konsumsi per laporan valid (≈ MT per hari), bukan total konsumsi per bulan.

**Hasil** : Tabel di expander *Monthly data used* pada halaman Forecasting (kolom `Valid_Reports`, `Avg ME cons / report`, `Total ME cons (MT)`).

---

**Gambar 4.20 Potongan Kode Pemilihan Bulan yang Dipakai**
File: analytics/forecast.py, baris 115–130
```python
    # bulan terakhir yang belum lengkap (data terpotong di tengah bulan) tidak dipakai
    if "Last_Report" in df.columns and len(df):
        last_dt = pd.to_datetime(df["Last_Report"].iloc[-1])
        month_end = df["period"].iloc[-1] + pd.offsets.MonthEnd(0)
        if pd.notna(last_dt) and last_dt.normalize() < month_end.normalize() - pd.Timedelta(days=2):
            # ...
            df = df.iloc[:-1]
    dropped = df[df["Valid_Reports"] < min_reports]
    # ...
    df = df[df["Valid_Reports"] >= min_reports]
    df = df[df["Avg_Cons"].notna() & (df["Avg_Cons"] > 0)]
    if len(df) < test_months + 6:
        return None
```

**Penjelasan**
Sebelum pemodelan, bulan terakhir dibuang bila datanya berhenti lebih dari dua hari sebelum akhir bulan. Bulan dengan laporan valid kurang dari `min_reports` (15) juga dikeluarkan karena rata-ratanya kurang representatif. Peramalan hanya dijalankan bila tersisa minimal `test_months + 6` bulan (9 bulan untuk 3 bulan uji).

**Hasil** : Catatan di bawah grafik forecasting, misalnya "12 month(s) with fewer than 15 valid reports excluded: …".

---

**Gambar 4.21 Potongan Kode Double Exponential Smoothing (Holt)**
File: analytics/forecast.py, baris 56–67
```python
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
```

**Penjelasan**
Nilai awal ditetapkan $L_1 = y_1$ dan $T_1 = y_2 - y_1$. Pada setiap periode, baris `new_level = alpha * v + (1 - alpha) * (level + trend)` mengimplementasikan persamaan level (persamaan 15), $L_t = \alpha y_t + (1-\alpha)(L_{t-1} + T_{t-1})$. Baris `trend = beta * (new_level - level) + (1 - beta) * trend` mengimplementasikan persamaan tren (persamaan 16), $T_t = \beta(L_t - L_{t-1}) + (1-\beta)T_{t-1}$. Nilai `level + trend` yang disimpan di `fitted` adalah ramalan satu langkah ke depan. Dari nilai tersebut dihitung SSE (*sum of squared errors*) sebagai ukuran kecocokan model.

**Hasil** : Garis titik-titik *Holt fit* pada grafik halaman Forecasting.

---

**Gambar 4.22 Potongan Kode Grid Search α, β dan Ramalan**
File: analytics/forecast.py, baris 29 dan 70–81
```python
GRID = np.round(np.arange(0.05, 0.951, 0.05), 2)
# ...
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
```

**Penjelasan**
Grid berisi 19 nilai (0,05; 0,10; …; 0,95). Fungsi `holt_optimize()` mencoba seluruh 19 × 19 = 361 kombinasi α dan β, lalu memilih kombinasi dengan SSE terkecil pada data latih. Fungsi `holt_forecast()` mengimplementasikan persamaan ramalan (persamaan 17), $F_{t+m} = L_t + m\,T_t$, untuk m = 1 sampai horizon.

**Hasil** : Nilai α dan β pada kartu KPI *MAE (test)* serta tabel *Forecast* untuk 3 bulan ke depan.

---

**Gambar 4.23 Potongan Kode Evaluasi MAE dan MAPE**
File: analytics/forecast.py, baris 84–104
```python
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
```

**Penjelasan**
Fungsi `mae()` menghitung $MAE = \frac{1}{n}\sum|y_t - F_t|$. Fungsi `mape()` mengimplementasikan persamaan 18, $MAPE = \frac{100\%}{n}\sum\left|\frac{y_t - F_t}{y_t}\right|$. Bulan dengan nilai aktual 0 dikecualikan untuk menghindari pembagian dengan nol. Fungsi `mape_rating()` menerjemahkan nilai MAPE ke kategori Lewis (1982): < 10% sangat baik, 10–20% baik, 20–50% layak, dan > 50% buruk.

**Hasil** : Kartu KPI *MAPE (test)* dan *MAE (test)*, serta tabel *Model evaluation*.

---

**Gambar 4.24 Potongan Kode Skema Uji dan Model Akhir**
File: analytics/forecast.py, baris 139–152
```python
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
```

**Penjelasan**
Evaluasi menggunakan pembagian data latih dan data uji: model dilatih tanpa 3 bulan terakhir, lalu ramalan 3 bulan dibandingkan dengan data aktual untuk menghitung MAE dan MAPE. Setelah itu, model akhir dilatih ulang dengan seluruh data untuk meramal 3 bulan ke depan. Karena grid search dijalankan dua kali, nilai α dan β model uji (`m_train`) dapat berbeda dari α dan β model akhir (`m_full`) yang ditampilkan di layar.

**Hasil** : Grafik *history and forecast* (garis Actual, Holt fit, Forecast putus-putus, dan tanda × *Test forecast*) serta tabel *Model evaluation*. Ambil screenshot halaman Forecasting dengan Scope = CAPIBARA.

---

### 4.3.6 Implementasi Tampilan Halaman Website

**Paragraf pengantar**
Aplikasi web dibangun dengan Streamlit dan memiliki empat halaman di menu navigasi: Noon Report Dashboard, Thermal Anomaly, Forecasting, dan ETL Pipeline. Halaman Noon Report dan Thermal Anomaly memakai filter global yang sama. Grafik dan peta dibuat dengan Plotly, dan setiap halaman analisis menyediakan tombol unduh CSV.

**Gambar 4.25 Potongan Kode Filter Global (Query Berparameter)**
File: services/data.py, baris 78–99
```python
@dataclass(frozen=True)
class Filters:
    vessel: str = ALL
    voyage: str = ALL
    start: dt.date | None = None
    end: dt.date | None = None

    def where(self, alias: str = "f") -> tuple[str, dict]:
        cond, p = [], {}
        if self.start:
            cond.append(f"{alias}.REPORT_DATE >= :start")
            p["start"] = dt.datetime.combine(self.start, dt.time.min)
        if self.end:
            cond.append(f"{alias}.REPORT_DATE < :end")
            p["end"] = dt.datetime.combine(self.end + dt.timedelta(days=1), dt.time.min)
        if self.vessel != ALL:
            cond.append(f"{alias}.Vessel_Key = :vessel")
            p["vessel"] = self.vessel
        if self.voyage != ALL:
            cond.append(f"{alias}.Voyage_Key = :voyage")
            p["voyage"] = self.voyage
        return (" WHERE " + " AND ".join(cond)) if cond else "", p
```

**Penjelasan**
Kelas `Filters` menyimpan pilihan kapal, voyage, dan rentang tanggal, lalu mengubahnya menjadi klausa `WHERE` berparameter. Batas akhir memakai `REPORT_DATE < end + 1 hari`, sehingga seluruh laporan pada tanggal akhir ikut terambil. Nilai filter dikirim sebagai parameter, bukan digabung langsung ke teks SQL, sehingga aman dari SQL injection. Tampilan filter dibuat di `ui/filters.py` (baris 71–92) berupa dua selectbox (Vessel, Voyage), dua date input (Start Date, End Date), serta tombol *Apply Filters* dan *Reset*. Pilihan voyage otomatis menyesuaikan kapal yang dipilih.

**Hasil** : Screenshot filter bar (Vessel, Voyage / FID_VOYAGE, Start Date, End Date, Apply Filters, Reset).

---

**Gambar 4.26 Potongan Kode Halaman Noon Report Dashboard**
File: views/noon_report.py, baris 20–21, 61–75, 124–128, dan 160–161
```python
flt = render_filter_bar("Apply Filters")
df = data.noon_reports(flt)
# ...
c1, c2, c3 = st.columns(3)
with c1, st.container(border=True):
    ui.card_title("Operational speed", sub)
    charts.show(charts.line_chart(series_df, "REPORT_DATE", [("OPERATIONAL_SPEED", data.speed_col(), theme.PRIMARY)],
                                  "knots"), key="nr_speed")
with c2, st.container(border=True):
    ui.card_title("Main engine RPM", sub)
    charts.show(charts.line_chart(series_df, "REPORT_DATE", [("RPM", "RPM", theme.PRIMARY)], "RPM"),
                key="nr_rpm")
with c3, st.container(border=True):
    ui.card_title("Main engine consumption", sub)
    charts.show(charts.line_chart(series_df, "REPORT_DATE",
                                  [("ME_MFO_CONS", "ME_MFO_CONS", theme.PRIMARY),
                                   ("ME_MDO_CONS", "ME_MDO_CONS", theme.PRIMARY_LIGHT)], "MT"),
                key="nr_cons")
# ...
    fig_map = charts.vessel_map(df, selected_key=sel_key, speed_col=data.speed_col())
    if fig_map is None:
        st.caption("No valid positions (LATITUDE / LONGITUDE) in the selected reports.")
    else:
        charts.show_map(fig_map, key="nr_map")
# ...
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="noon_reports.csv", mime="text/csv", icon=":material/download:")
```

**Penjelasan**
Halaman Noon Report membaca data sesuai filter, lalu menampilkan tiga grafik garis: kecepatan operasional, RPM main engine, dan konsumsi ME (MFO dan MDO). Jika lebih dari satu kapal dipilih, nilai harian dirata-ratakan antar kapal. Peta posisi kapal dibuat oleh `charts.vessel_map()`. Fungsi `valid_positions()` (`ui/charts.py` baris 91–96) membuang koordinat kosong, 0/0, atau di luar rentang bumi. Setiap kapal digambar sebagai satu lintasan `Scattermap`, laporan ANOMALY ditandai lingkaran merah, dan laporan terpilih ditandai titik navy. Tombol *Download CSV* mengunduh seluruh laporan hasil filter.

**Hasil** : Screenshot (1) tiga grafik operasional, (2) kartu *Main engine thermal condition* dan *Environmental conditions*, (3) peta *Vessel positions & track*, dan (4) tabel *Detailed Noon Reports* dengan tombol *Download CSV*.

---

**Gambar 4.27 Potongan Kode Halaman Thermal Anomaly**
File: views/thermal_anomaly.py, baris 36–38, 98–99, 111–113, 142–153, dan 191–193
```python
flt = render_filter_bar("Run Analysis")
noon = data.noon_reports(flt)
cyl = data.cylinder_anomalies(flt)
# ...
    charts.show(charts.egt_chart(egt_df, "REPORT_DATE", EGT_COLS, height=330, anomalies=anom,
                                 selected_date=sel_date), key="ta_egt")
# ...
    charts.show(charts.deviation_bar([f"CYL{n}" for n in sel["Cylinder_No"]],
                                     sel["CYLINDER_DEVIATION"].tolist(), sel["ANOMALY_STATUS"].tolist(),
                                     height=270), key="ta_dev")
# ...
    status_f = f2.selectbox("Status", ["All statuses", ANOMALY, NORMAL, NOT_VALID],
                            label_visibility="collapsed", key="ta_status")
    tbl = cyl.assign(
        Cylinder="CYL" + cyl["Cylinder_No"].astype(str),
        Reason=cyl["STATUS_REASON"].map(REASON_TEXT).fillna(cyl["STATUS_REASON"]),
    )
    if status_f != "All statuses":
        tbl = tbl[tbl["ANOMALY_STATUS"] == status_f]
    if q:
        hay = (tbl["REPORT_DATE"].dt.strftime("%Y-%m-%d") + " " + tbl["Voyage_Label"].astype(str) + " "
               + tbl["VESSEL_NAME"].astype(str) + " " + tbl["Vessel_Key"].astype(str) + " " + tbl["Cylinder"])
        tbl = tbl[hay.str.contains(q, case=False, regex=False, na=False)]
# ...
    st.download_button("Download results (CSV)", tbl.to_csv(index=False).encode("utf-8"),
                       file_name="thermal_anomaly_results.csv", mime="text/csv",
                       icon=":material/download:")
```

**Penjelasan**
Halaman Thermal Anomaly membaca hasil perhitungan dari `FACT_CYLINDER_ANOMALY`, bukan menghitung ulang, sehingga tampilan cepat dan konsisten dengan hasil ETL. Grafik `egt_chart` menampilkan EGT CYL1–CYL8 terhadap waktu dengan penanda merah pada pembacaan ANOMALY. Grafik `deviation_bar` menampilkan deviasi bertanda setiap silinder pada laporan terpilih: merah untuk ANOMALY dan abu-abu untuk DATA_NOT_VALID. Tabel hasil dapat difilter berdasarkan status dan dicari berdasarkan tanggal, kapal, voyage, atau silinder. Tombol unduh mengekspor tabel sesuai filter yang aktif.

**Hasil** : Screenshot (1) grafik *Historical exhaust gas temperature* dengan lingkaran merah, (2) grafik *Cylinder Deviation* laporan CAPIBARA 20 Juli 2026, (3) callout merah CYL4, (4) *Thermal Anomaly Results Table* dengan filter status ANOMALY, dan (5) tombol *Download results (CSV)*.

---

**Gambar 4.28 Potongan Kode Halaman Forecasting**
File: views/forecasting.py, baris 31–34, 39–41, dan 82–89
```python
    vessel = c1.selectbox("Scope", [ALL, *vessels["Vessel_Key"].tolist()], key="fc_vessel",
                          format_func=lambda k: "All Vessels (fleet)" if k == ALL else f"{names.get(k, '')} ({k})")
    horizon = c2.number_input("Forecast horizon (months)", 1, 12, int(A.forecast_horizon), key="fc_h")
    test_m = c3.number_input("Test months (MAPE)", 2, 6, int(A.forecast_test_months), key="fc_test")
# ...
monthly = data.fuel_monthly(vessel)
res = run_forecast(monthly, horizon=int(horizon), test_months=int(test_m),
                   min_reports=int(A.forecast_min_reports)) if not monthly.empty else None
# ...
    fx = [h["period"].iloc[-1], *res.forecast["period"]]
    fy = [h["value"].iloc[-1], *res.forecast["forecast"]]
    fig.add_trace(go.Scatter(x=fx, y=fy, name="Forecast", mode="lines+markers",
                             line=dict(color=theme.BAD_FG, width=2, dash="dash"), marker=dict(size=6),
                             hovertemplate="%{x|%b %Y}: %{y:.2f} MT<extra>Forecast</extra>"))
    fig.add_trace(go.Scatter(x=res.test["period"], y=res.test["forecast"], name="Test forecast",
                             mode="markers", marker=dict(color="#8C7AA9", size=8, symbol="x"),
                             hovertemplate="%{x|%b %Y}: %{y:.2f} MT<extra>Test forecast</extra>"))
```

**Penjelasan**
Halaman Forecasting memiliki filter sendiri: cakupan (seluruh armada atau satu kapal), horizon ramalan (1–12 bulan), dan jumlah bulan uji (2–6 bulan). Data bulanan diambil dengan `fuel_monthly()` lalu diproses `run_forecast()`. Grafik menampilkan data aktual, *Holt fit*, garis ramalan putus-putus yang disambung dari titik aktual terakhir, dan tanda × untuk ramalan pada periode uji. Tabel *Model evaluation* (baris 104–110) menampilkan nilai aktual, ramalan, dan |Error| % per bulan uji. Halaman ini **tidak memiliki tombol unduh CSV**; data bulanan hanya ditampilkan di expander *Monthly data used*.

**Hasil** : Screenshot halaman Forecasting (Scope = CAPIBARA): empat kartu KPI, grafik history & forecast, tabel *Forecast*, dan tabel *Model evaluation*.

---

**Gambar 4.29 Potongan Kode Halaman ETL Pipeline**
File: views/etl_pipeline.py, baris 81–102
```python
    mode = m1.radio("Mode", ["incremental", "full"], horizontal=True, key="etl_mode",
                    format_func=lambda m: "Incremental (recommended daily)" if m == "incremental"
                    else "Full reload (rebuild everything)")
    # ...
    confirm = True
    if mode == "full":
        confirm = m1.checkbox("I understand a full reload truncates and rebuilds the fact tables.",
                              key="etl_confirm")
    run = m2.button("Run ETL", type="primary", icon=":material/play_arrow:", width="stretch",
                    disabled=not confirm)

    if run:
        bar = st.progress(0.0, text="Starting…")
        with st.status("Running ETL…", expanded=True) as status:
            def progress(msg: str, pct: float) -> None:
                bar.progress(min(max(pct, 0.0), 1.0), text=msg)
                st.write(msg)
            result = run_etl(data.get_engine(), DB, AN, mode=mode, progress=progress)
```

**Penjelasan**
Pengguna memilih mode Incremental atau Full reload. Untuk Full reload, tombol *Run ETL* baru aktif setelah kotak konfirmasi dicentang, karena mode ini mengosongkan tabel fakta. Fungsi `progress()` diteruskan ke `run_etl()` sebagai *callback*, sehingga setiap tahap ETL langsung tampil di progress bar. Halaman ini juga menyediakan tombol *Test connection*, *Create / verify schema*, unduh *DDL (.sql)*, kartu Auto ETL, dan tabel *Run history*.

**Hasil** : Screenshot kartu *Connection* dan *Analysis parameters*, kartu *Run ETL* saat proses berjalan, hasil ETL beserta *Data quality report*, dan tabel *Run history*.

---

### 4.3.7 Evaluasi Hasil Implementasi Kode

**Paragraf pengantar**
Evaluasi dilakukan dengan membandingkan hasil yang diharapkan dari setiap fitur dengan hasil yang dihasilkan sistem. Verifikasi dilakukan dengan tiga cara: perhitungan manual pada data nyata (kapal CAPIBARA), query langsung ke data mart `dw`, dan 12 unit test pada `tests/test_core.py`. Seluruh unit test berstatus PASS.

**Tabel 4.x Evaluasi Hasil Implementasi Kode**

| No | Fitur | Yang diuji | Hasil yang diharapkan | Hasil sistem | Keterangan |
|---|---|---|---|---|---|
| 1 | Koneksi database | Tombol *Test connection* | Terhubung ke SQL Server dan menampilkan nama server, database, dan versi | Pesan "Connected to … / … · SQL Server …" | Sesuai |
| 2 | Pembuatan star schema | Tombol *Create / verify schema* | Skema `dw` beserta 3 dimensi dan 2 fakta terbentuk | "Star schema [dw] is ready." dan tabel tampil di SSMS | Sesuai |
| 3 | ETL full | Run ETL mode Full reload | Seluruh data dimuat, status SUCCESS | Status SUCCESS, metrik *Reports loaded* = jumlah baris `FACT_NOON_REPORT` | Sesuai |
| 4 | ETL incremental | Run ETL setelah data sumber diubah | Hanya baris yang berubah diproses, tanpa duplikasi | Baris lama diganti (*Old versions replaced*), watermark diperbarui | Sesuai |
| 5 | Validasi EGT | EGT = 0 (CYL7–8 mesin 6 silinder), EGT di luar 100–600 °C, RPM = 0 | Nilai dijadikan NULL dan tidak ikut median | Unit test `test_six_cylinder_engine_zero_is_missing` dan `test_egt_invalid_when_rpm_zero` PASS. Pada CAPIBARA 20/07/2026, CYL5, CYL7, dan CYL8 kosong sehingga median dihitung dari 5 silinder | Sesuai |
| 6 | Median EGT | CAPIBARA 20 Juli 2026 | Median(371, 368, 362, 359, 369) = 368 °C | `MEDIAN_EGT` = 368,0 | Sesuai |
| 7 | Cylinder Deviation | CYL4 CAPIBARA 20 Juli 2026 | 359 − 368 = −9 °C | `CYLINDER_DEVIATION` = −9,0 | Sesuai (deviasi bertanda) |
| 8 | Historical baseline | Baseline CYL4, rentang RPM 100–110 | 60 deviasi valid sebelumnya; Median(B) dan MAD tersedia | `BASELINE_N` = 60, Median(B) = 0,0, MAD = 1,0 | Sesuai |
| 9 | Modified Z-Score | CYL4 CAPIBARA 20 Juli 2026 | 0,6745 × (−9 − 0) / 1 = −6,07 | `MODIFIED_Z_SCORE` = −6,0705 | Sesuai |
| 10 | Status anomali | \|M\| CYL4 = 6,07 > 3,5 | ANOMALY | `ANOMALY_STATUS` = ANOMALY; status laporan = ANOMALY | Sesuai |
| 11 | Status NORMAL | Silinder lain di laporan yang sama | \|M\| ≤ 3,5 → NORMAL | CYL1 −0,93; CYL2 0,00; CYL3 −1,35; CYL6 0,22 → NORMAL | Sesuai |
| 12 | Status DATA_NOT_VALID | Baseline kurang, MAD = 0, RPM kosong | Tidak diberi status NORMAL/ANOMALY | Unit test `test_no_lookahead_and_min_baseline`, `test_exact_design_numbers_with_mad_2`, `test_missing_rpm_is_not_valid` PASS | Sesuai |
| 13 | Agregasi bulanan BBM | CAPIBARA per bulan | Rata-rata (MFO + MDO) per laporan valid | Mei 2026 = 9,942; Juni 2026 = 6,384; Juli 2026 = 14,040 MT/laporan | Sesuai dengan kode (rata-rata, bukan total) |
| 14 | Holt + grid search | Model uji CAPIBARA | α, β terpilih dengan SSE minimum | Model uji: α = 0,10, β = 0,95. Model akhir (ditampilkan): α = 0,20, β = 0,95 | Sesuai; lihat catatan α/β |
| 15 | MAPE | CAPIBARA, 3 bulan uji | (34,23 + 4,14 + 59,39) / 3 = 32,59% | MAPE = 32,585% → kategori "Layak" | Sesuai |
| 16 | MAE | CAPIBARA, 3 bulan uji | (3,403 + 0,264 + 8,338) / 3 | MAE = 4,00 MT | Sesuai |
| 17 | Filter global | Pilih kapal, voyage, dan tanggal lalu Apply | Seluruh KPI, grafik, dan tabel mengikuti filter | Query memakai klausa `WHERE` berparameter dari `Filters.where()` | Sesuai |
| 18 | Peta posisi kapal | Halaman Noon Report | Lintasan kapal tampil, koordinat tidak valid tidak digambar | Peta `Scattermap` dengan penanda anomali merah | Sesuai |
| 19 | Unduh CSV | Noon Report dan Thermal Anomaly | File CSV terunduh sesuai filter | `noon_reports.csv` dan `thermal_anomaly_results.csv` | Sesuai; halaman Forecasting tidak punya tombol unduh |
| 20 | Auto ETL | Tambah/ubah baris di sumber | ETL incremental berjalan otomatis ≤ 60 detik | Notifikasi "Auto ETL: N new/changed noon report(s) loaded" | Perlu diuji saat UAT |

**Verifikasi manual 1: Anomali termal CAPIBARA, 20 Juli 2026 13:00 (RPM 108,6, rentang 100–110)**

| Silinder | EGT (°C) | D = EGT − 368 | Median(B) | MAD | M = 0,6745(D − Median(B)) / MAD | Status |
|---|---|---|---|---|---|---|
| CYL1 | 371 | +3 | 14,0 | 8,0 | 0,6745 × (3 − 14) / 8 = −0,93 | NORMAL |
| CYL2 | 368 | 0 | 0,0 | 1,0 | 0,00 | NORMAL |
| CYL3 | 362 | −6 | −2,0 | 2,0 | 0,6745 × (−6 + 2) / 2 = −1,35 | NORMAL |
| **CYL4** | **359** | **−9** | **0,0** | **1,0** | **0,6745 × (−9 − 0) / 1 = −6,07** | **ANOMALY** |
| CYL5 | — | — | — | — | (tidak pernah punya EGT valid di histori CAPIBARA) | dianggap tidak terpasang, tidak dilaporkan |
| CYL6 | 369 | +1 | 0,0 | 3,0 | 0,6745 × 1 / 3 = 0,22 | NORMAL |

Median EGT = median(359, 362, 368, 369, 371) = **368 °C**. |M| CYL4 = 6,07 > 3,5 sehingga statusnya **ANOMALY**. Angka ini cocok dengan isi `dw.FACT_CYLINDER_ANOMALY`. Hasil −6,07 hanya bisa diperoleh dengan deviasi **bertanda** (−9). Jika memakai nilai mutlak |EGT − median| = 9, baseline juga akan berisi nilai mutlak dan hasilnya berbeda.

**Verifikasi manual 2: Forecasting CAPIBARA (3 bulan uji)**

| Bulan | Aktual (MT/laporan) | Ramalan | \|Error\| % |
|---|---|---|---|
| Mei 2026 | 9,942 | 6,539 | 34,23 |
| Juni 2026 | 6,384 | 6,120 | 4,14 |
| Juli 2026 | 14,040 | 5,701 | 59,39 |

MAPE = (34,23 + 4,14 + 59,39) / 3 = **32,59%** (sistem: 32,585%, kategori Layak). Ramalan uji dihasilkan model latih dengan α = 0,10 dan β = 0,95 (L = 6,958; T = −0,419), sehingga F = 6,958 − 0,419 × m untuk m = 1, 2, 3. Angka ini cocok dengan perhitungan ulang dari data mart memakai kode `run_forecast()`.

**Hasil** : Screenshot tabel *Model evaluation* (Scope = CAPIBARA), *Worked example* di halaman Thermal Anomaly, dan output `python tests/test_core.py` yang menampilkan 12 baris PASS.

---

## Perbedaan Kode dengan Skripsi

Daftar berikut membandingkan perilaku kode yang sebenarnya dengan deskripsi metode di skripsi. Bagian yang berbeda perlu disesuaikan di Bab 3/Bab 4, atau kodenya yang disesuaikan.

### A. Deteksi anomali termal
1. **Deviasi bertanda, bukan nilai mutlak.** Kode memakai `D = EGT − median` (`analytics/thermal.py` baris 83), sehingga D bisa positif atau negatif. Nilai mutlak hanya dipakai pada |M| > 3,5 untuk menentukan status. Jika persamaan 10 di skripsi menulis |EGT − median|, persamaannya perlu diubah, karena angka −9 °C dan −6,07 hanya dihasilkan oleh deviasi bertanda.
2. **Rumus Modified Z-Score memakai deviasi terhadap baseline:** M = 0,6745 × (D − Median(B)) / MAD. D tidak dibandingkan dengan nol atau dengan median laporan. Pastikan variabel di persamaan 14 sesuai.
3. **Minimal data baseline yang aktif = 20, bukan 10.** Default di `config/settings.py`, `ThermalParams`, `secrets.toml.example`, dan skenario UAT ETL-06 adalah 10. Namun konfigurasi yang benar-benar dipakai (`.streamlit/secrets.toml`) bernilai `min_baseline_obs = 20`. Tulis di skripsi nilai yang benar-benar dipakai, atau samakan konfigurasinya lalu jalankan Full reload.
4. **"60 data terakhir" = 60 deviasi valid terakhir di kelompok (kapal, silinder, rentang RPM) yang sama, sebelum laporan yang dinilai.** Jadi bukan 60 laporan terakhir secara kalender. Laporan yang dinilai tidak termasuk baseline-nya sendiri (tanpa *look-ahead*).
5. **Syarat validasi tambahan yang tidak disebut di deskripsi:** minimal 4 silinder valid per laporan; EGT = 0 dianggap "tidak dilaporkan"; seluruh EGT dijadikan NULL bila RPM = 0; minimal 20 data baseline; MAD = 0 → DATA_NOT_VALID.
6. **Ada status ketiga, `DATA_NOT_VALID`,** beserta alasannya (`STATUS_REASON`). Status laporan = ANOMALY bila minimal satu silinder ANOMALY.
7. **Silinder yang tidak pernah punya EGT valid pada sebuah kapal disembunyikan** (`drop_uninstalled_cylinders`), misalnya CYL7–8 pada mesin 6 silinder.
8. **Batas EGT 100–600 °C bersifat inklusif:** 100 dan 600 tetap valid; yang dibuang adalah < 100 dan > 600.

### B. Peramalan konsumsi bahan bakar
9. **Yang diramal adalah rata-rata konsumsi per laporan valid per bulan (`Avg_Cons`), bukan total ME_MFO_CONS (+ ME_MDO_CONS) per bulan.** Total bulanan (`Total_Cons`) hanya ditampilkan di expander. Satuan hasil = MT per laporan (≈ MT per hari).
10. **MFO dan MDO dijumlahkan** (ME_MFO_CONS + ME_MDO_CONS), bukan ME_MFO_CONS saja.
11. **Filter data yang tidak disebut di deskripsi:** hanya laporan dengan RPM > 0 dan 0 < konsumsi ≤ 100 MT; bulan dengan < 15 laporan valid dibuang; bulan terakhir dibuang bila datanya berhenti > 2 hari sebelum akhir bulan; minimal 9 bulan data.
12. **Deret bulan tidak harus berurutan.** Untuk CAPIBARA, setelah filter tersisa 10 bulan: 2025-02, 2025-04, 2025-06, 2025-08, 2026-02 s.d. 2026-07. Model Holt memperlakukan bulan-bulan yang berselang ini seolah berurutan.
13. **Juli 2026 hanya berisi data sampai 29 Juli (20 laporan),** tetapi tetap dipakai karena aturan "terpotong > 2 hari" tidak terpenuhi (29 Juli = 31 Juli − 2 hari). Bulan ini menyumbang error terbesar (59,39%).
14. **Grid search meminimalkan SSE pada data latih (ramalan satu langkah), bukan meminimalkan MAPE.** Grid 0,05–0,95 dengan langkah 0,05 (361 kombinasi).
15. **α dan β yang tampil di layar berasal dari model akhir (seluruh data), bukan dari model yang dievaluasi MAPE-nya.** Untuk CAPIBARA, layar menampilkan α = 0,20 dan β = 0,95, sedangkan MAPE 32,59% dihitung dari model uji dengan α = 0,10 dan β = 0,95. Sebutkan keduanya dengan jelas di skripsi.
16. Inisialisasi L₁ = y₁ dan T₁ = y₂ − y₁. Ramalan negatif dipotong menjadi 0. Bulan dengan nilai aktual 0 dikecualikan dari MAPE.

### C. Dashboard dan halaman web
17. **Kecepatan memakai `SPEED_OVER_GROUND`, bukan `AVG_SPEED`,** karena AVG_SPEED di data sumber hampir selalu 0 (`speed_column`). AVG_SPEED masih ditampilkan sebagai kolom tambahan di tabel.
18. **Halaman `overview.py` dan `data_information.py` ada di kode tetapi tidak terdaftar di menu** (`app.py` hanya mendaftarkan 4 halaman). Statistik deskriptif (`analytics/descriptive.py`) tidak dapat diakses dari aplikasi. Kartu "Average speed at sea" di Overview juga masih berlabel AVG_SPEED walaupun datanya memakai kolom kecepatan yang dikonfigurasi.
19. **Halaman Forecasting tidak punya tombol unduh CSV.** Unduhan hanya ada di Noon Report, Thermal Anomaly, dan DDL di ETL Pipeline.
20. **Peta memakai basemap `carto-positron` dari internet,** sehingga peta membutuhkan koneksi internet.

### D. Dokumentasi yang tidak sesuai kode
21. `docs/RUMUS.md` masih menulis status `CANNOT_CALCULATE` (di kode: `DATA_NOT_VALID`) dan baseline tanpa pengelompokan RPM. Jangan dikutip langsung ke skripsi.
22. `README.md` masih mencantumkan halaman Overview dan Data Information dan belum mencantumkan Forecasting.

### E. Bagian yang tidak ditemukan di kode
- KPI efisiensi seperti SFOC, konsumsi per mil laut, atau konsumsi per voyage: **tidak ditemukan di kode**.
- Evaluasi peramalan selain MAE dan MAPE (misalnya RMSE): **tidak ditemukan di kode**.
