# Marine BI Analytics (Streamlit 1.66.1)

Dashboard historis Noon Report + analisis anomali suhu gas buang (EGT) per silinder,
dengan **ETL yang bisa dijalankan langsung dari web** (halaman *ETL Pipeline*).

```
SQL Server  COPY_DATA.dbo                       COPY_DATA.dw  (star schema)            Streamlit
┌───────────────────┐   EXTRACT   TRANSFORM   ┌────────────────────────────┐   READ   ┌──────────────────┐
│ NOON_REPORT_COPY  │ ─────────▶ ─────────▶   │ DIM_DATE   DIM_VESSEL      │ ───────▶ │ Overview         │
│ V_Voyages         │   LOAD     ANALYZE      │ DIM_VOYAGE                 │          │ Noon Report      │
│ vessels           │ ─────────▶ ─────────▶   │ FACT_NOON_REPORT           │          │ Thermal Anomaly  │
└───────────────────┘                         │ FACT_CYLINDER_ANOMALY      │          │ Data Information │
                                              │ ETL_RUN_LOG  ETL_WATERMARK │          │ ETL Pipeline     │
                                              └────────────────────────────┘          └──────────────────┘
```

## 1. Instalasi (Windows)

1. Pasang **ODBC Driver 18 (atau 17) for SQL Server** dari Microsoft (biasanya sudah ada jika SSMS terpasang).
2. Buat virtual environment dan pasang paket:
   ```bat
   cd marine_bi
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Konfigurasi koneksi: salin `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`
   (sudah disiapkan untuk `localhost\SQLEXPRESS`, database `COPY_DATA`, Windows Authentication).
4. Jalankan:
   ```bat
   streamlit run app.py
   ```
5. Buka halaman **ETL Pipeline** → *Test connection* → pilih **Full reload** → *Run ETL*.
   Setelah selesai, semua dashboard terisi. Berikutnya cukup **Incremental**.

> Akun Windows yang menjalankan Streamlit butuh izin `CREATE SCHEMA/TABLE` di `COPY_DATA`
> (atau jalankan `sql/create_warehouse.sql` sekali di SSMS sebagai admin).

## 2. Struktur kode

```
marine_bi/
├── app.py                      # entry point: page config, CSS, sidebar, navigasi
├── requirements.txt
├── .streamlit/
│   ├── config.toml             # tema (warna desain), toolbar
│   └── secrets.toml(.example)  # koneksi DB + parameter analitik
├── config/settings.py          # semua konfigurasi terpusat (tanpa ketergantungan Streamlit)
├── core/
│   ├── database.py             # pyodbc/SQLAlchemy engine, auto-detect ODBC driver
│   └── schema.py               # definisi star schema + DDL (satu sumber kebenaran)
├── etl/
│   ├── extract.py              # baca tabel sumber (full / sejak watermark)
│   ├── transform.py            # pembersihan, konversi tipe, kunci, validasi EGT, DQ report
│   ├── load.py                 # tulis dims & facts (full / delete-insert via staging), log
│   └── pipeline.py             # orkestrasi E→T→L→Analyze, lock, progress callback
├── analytics/
│   ├── thermal.py              # Median EGT, Deviation, Baseline, MAD, Modified Z, Status
│   └── descriptive.py          # statistik deskriptif & kelengkapan
├── services/data.py            # query dashboard ber-parameter + cache Streamlit
├── ui/
│   ├── theme.py                # design tokens & CSS (sidebar navy, kartu, badge)
│   ├── components.py           # KPI card, info strip, tile silinder, callout, footer
│   ├── charts.py               # chart Plotly bergaya seragam
│   ├── filters.py              # filter bar global (Apply / Reset), persist antar halaman
│   └── layout.py               # pengecekan kesiapan warehouse
├── views/                      # 1 file = 1 halaman
│   ├── overview.py  noon_report.py  thermal_anomaly.py  data_information.py  etl_pipeline.py
├── scripts/run_etl.py          # ETL via command line (Task Scheduler)
├── sql/create_warehouse.sql    # DDL untuk SSMS
├── docs/RUMUS.md               # keterangan rumus lengkap
└── tests/test_core.py          # unit test rumus & transform (tanpa DB)
```

## 3. Cara kerja ETL

| Tahap | Isi |
|---|---|
| Extract | `SELECT * ... WITH (NOLOCK)` dari 3 tabel sumber. Incremental: hanya baris dengan `MAX(CREATED_DATE, MODIFIED_DATE) > watermark`. |
| Transform | GUID → UPPER; `1900-01-01` → NULL; `'31° C'` → 31; teks numerik → angka; EGT 0/NULL/di luar 100–600 °C → NULL; duplikat ID → versi terbaru; laporan non-aktif/arsip dikeluarkan; `Date_Key`, `Vessel_Key` dibentuk; voyage tak dikenal → `UNKNOWN`. |
| Load | Dimensi dimuat ulang; fact: *full* = TRUNCATE + INSERT, *incremental* = staging → DELETE versi lama → INSERT versi baru. Semua dalam **satu transaksi** (gagal = rollback). |
| Analyze | Anomali dihitung ulang untuk kapal yang datanya berubah (baseline butuh histori), hasil ke `FACT_CYLINDER_ANOMALY`, ringkasan ke `FACT_NOON_REPORT`. |
| Finalize | `DIM_DATE` dibangun dari rentang tanggal, atribut voyage (tanggal awal/akhir, jumlah laporan), watermark & log. |

**Penjadwalan harian** (Windows Task Scheduler): Program `C:\path\marine_bi\.venv\Scripts\python.exe`,
Arguments `-m scripts.run_etl --mode incremental`, Start in `C:\path\marine_bi`.

**Auto ETL (otomatis saat ada data baru).** Selama Streamlit berjalan, sebuah thread latar belakang
mengecek `NOON_REPORT_COPY` setiap `interval_seconds` (default 60 detik). Jika ada baris dengan
`MAX(CREATED_DATE, MODIFIED_DATE) > watermark`, ETL *incremental* dijalankan otomatis dan dashboard
ter-refresh sendiri. Pengaturan ada di `secrets.toml` → `[auto_etl] enabled / interval_seconds`.
Tanpa browser: `python -m scripts.auto_etl` (terus memantau) atau `--once` (cek 1x, untuk Task Scheduler).
ETL dijaga *application lock* SQL Server (`sp_getapplock`), sehingga tidak pernah berjalan dua kali bersamaan.
Load pertama tetap **Full reload** manual.

## 4. Rumus

Lihat **[docs/RUMUS.md](docs/RUMUS.md)** — Median EGT, Cylinder Deviation, aturan baseline,
MAD, Modified Z-Score, Anomaly Status, statistik deskriptif, beserta contoh angka.

## 5. Uji

```bat
python tests\test_core.py
```
Test memverifikasi angka di desain: median 344,5; deviasi CYL6 +15,5; MZ = 5,23 (MAD 2,0);
mean AVG_SPEED 12,36 dengan 12,5 % missing; mesin 6 silinder (CYL7–8 = 0) median 352,5.

## 6. Catatan & asumsi

* `V_Voyages` hanya punya `ID_VOYAGE` (GUID), sehingga label voyage = `KODE_KAPAL · 8 karakter GUID`.
  Jika ada kolom nomor voyage, tambahkan di `etl/transform.py::transform_voyages` (`Voyage_Label`).
* Satuan konsumsi diasumsikan MT — konfirmasi dengan sistem sumber.
* Kolom `MEDIAN_EGT, CYLINDER_DEVIATION, MAD, MODIFIED_Z_SCORE` per silinder disimpan di
  `FACT_CYLINDER_ANOMALY` (grain laporan × silinder), karena 1 laporan punya 8 nilai.
  `FACT_NOON_REPORT` menyimpan ringkasannya (`MEDIAN_EGT`, `MAX_ABS_MODIFIED_Z`, `ANOMALY_CYLINDERS`, `Anomaly_Status`).
* Mengubah parameter analitik → jalankan **Full reload** agar seluruh histori dihitung ulang.
