# User Acceptance Testing (UAT)
## Sistem Business Intelligence *Marine BI Analytics*: Historical Noon Report, Thermal Anomaly & Fuel Forecasting

---

## 1. Pendahuluan

### 1.1 Tujuan
Dokumen ini menjadi pedoman pelaksanaan *User Acceptance Testing* (UAT). UAT dilakukan untuk memastikan
aplikasi *Marine BI Analytics* sudah memenuhi kebutuhan pengguna dan bisa diterima untuk digunakan.
Pengujian mencakup:
1. **Pengujian skenario (fungsional)**: pengguna menjalankan setiap fitur sesuai langkah uji, lalu
   membandingkan hasilnya dengan hasil yang diharapkan.
2. **Kuesioner penerimaan pengguna**: pengguna memberi penilaian dengan skala Likert 1–5 terhadap
   kemudahan, tampilan, manfaat, dan keakuratan informasi.

### 1.2 Ruang Lingkup
| Modul | Halaman pada aplikasi | Kode uji |
|---|---|---|
| Navigasi & umum | Sidebar, kerangka halaman | NAV |
| ETL Pipeline | *ETL Pipeline* | ETL |
| Filter global | Filter bar pada *Noon Report* & *Thermal Anomaly* | FLT |
| Noon Report Dashboard | *Noon Report* | NR |
| Thermal Anomaly Analysis | *Thermal Anomaly* | TA |
| Fuel Consumption Forecasting | *Forecasting* | FC |

### 1.3 Lingkungan Pengujian
| Komponen | Keterangan |
|---|---|
| Sistem operasi | Windows 10/11 |
| Basis data | Microsoft SQL Server (Express), database `COPY_DATA`, skema sumber `dbo`, skema DW `dw` |
| Driver | ODBC Driver 17/18 for SQL Server |
| Aplikasi | Python 3.12, Streamlit, dijalankan dengan `streamlit run app.py` |
| Browser | Google Chrome / Microsoft Edge versi terbaru |
| Data uji | Data historis `NOON_REPORT_COPY`, `V_Voyages`, `vessels` |

### 1.4 Responden / Penguji
| No | Nama | Jabatan / Peran | Instansi / Divisi | Tanggal Uji |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

### 1.5 Kriteria Penerimaan
- Setiap skenario diberi status **Diterima** (hasil aktual sesuai dengan yang diharapkan) atau **Ditolak**.
- Aplikasi dinyatakan **diterima** bila:
  - **seluruh skenario prioritas Tinggi** berstatus Diterima, dan
  - persentase skenario Diterima **≥ 90%**, dan
  - hasil kuesioner berada pada kategori minimal **"Baik"** (≥ 61%).

---

## 2. Skenario Pengujian (Fungsional)

> **Cara mengisi:** isi kolom **Hasil Aktual** dengan apa yang muncul di layar. Isi kolom **Status** dengan
> ✔ (Diterima) atau ✘ (Ditolak). Tulis temuan atau saran di kolom **Catatan**.
> Prioritas: **T** = Tinggi, **S** = Sedang, **R** = Rendah.

### 2.1 Navigasi & Umum (NAV)

| Kode | Prioritas | Skenario | Langkah Uji | Hasil yang Diharapkan | Hasil Aktual | Status | Catatan |
|---|---|---|---|---|---|---|---|
| NAV-01 | T | Membuka aplikasi | 1. Jalankan `streamlit run app.py`<br>2. Buka alamat yang tampil di browser | Aplikasi terbuka dan langsung menampilkan halaman **Noon Report**. Sidebar menampilkan logo "Marine BI Analytics" | | | |
| NAV-02 | T | Menu sidebar | Periksa isi sidebar | Ada kelompok **ANALYTICS WORKSPACE** (Noon Report, Thermal Anomaly, Forecasting) dan **DATA PIPELINE** (ETL Pipeline) | | | |
| NAV-03 | T | Berpindah halaman | Klik setiap menu di sidebar secara bergantian | Halaman berpindah sesuai menu yang diklik, tanpa pesan error | | | |
| NAV-04 | S | Data warehouse belum siap | Buka halaman Noon Report saat tabel `dw.FACT_NOON_REPORT` belum ada atau masih kosong | Muncul pesan bahwa star schema belum dibuat / tabel fakta kosong, beserta tautan **"Open the ETL Pipeline page"** | | | |
| NAV-05 | R | Tampilan responsif | Perkecil jendela browser / buka di layar laptop kecil | Kartu dan grafik menyesuaikan lebar layar, isi tetap terbaca | | | |

### 2.2 ETL Pipeline (ETL)

| Kode | Prioritas | Skenario | Langkah Uji | Hasil yang Diharapkan | Hasil Aktual | Status | Catatan |
|---|---|---|---|---|---|---|---|
| ETL-01 | T | Menampilkan info koneksi | Buka halaman **ETL Pipeline** | Kartu **Connection** menampilkan pengaturan koneksi (server, database, dll.). Kata sandi disamarkan | | | |
| ETL-02 | T | Tes koneksi berhasil | Klik **Test connection** | Muncul pesan hijau "Connected to *server* / *database* · SQL Server *versi* (*edisi*)" | | | |
| ETL-03 | S | Tes koneksi gagal | Ubah `server` di `.streamlit/secrets.toml` menjadi nama yang salah, jalankan ulang aplikasi, lalu klik **Test connection** | Muncul pesan merah "Connection failed: …" dan aplikasi tidak *crash* | | | |
| ETL-04 | T | Membuat / verifikasi skema | Klik **Create / verify schema** | Muncul pesan "Star schema [dw] is ready." Tabel DIM_DATE, DIM_VESSEL, DIM_VOYAGE, FACT_NOON_REPORT, FACT_CYLINDER_ANOMALY, ETL_RUN_LOG, ETL_WATERMARK ada di SSMS | | | |
| ETL-05 | R | Unduh DDL | Klik **DDL (.sql)** | File `create_warehouse.sql` terunduh dan berisi perintah CREATE SCHEMA/TABLE | | | |
| ETL-06 | S | Parameter analisis | Periksa kartu **Analysis parameters** | Parameter tampil, antara lain: Valid EGT range 100–600 °C, Min valid cylinders 4, Baseline window 60, Min baseline obs 10, Anomaly threshold \|MZ\| > 3.5 | | | |
| ETL-07 | T | Pengaman Full reload | Pilih mode **Full reload**, jangan centang konfirmasi | Tombol **Run ETL** tidak aktif sampai kotak *"I understand a full reload truncates…"* dicentang | | | |
| ETL-08 | T | Menjalankan Full reload | Centang konfirmasi, klik **Run ETL** | *Progress bar* berjalan dan menampilkan tahap Extract → Transform → Load → Analyze. Status akhir **SUCCESS** dengan durasi | | | |
| ETL-09 | T | Ringkasan hasil ETL | Periksa hasil setelah ETL-08 | Tampil metrik *Rows extracted, Reports loaded, Old versions replaced, Cylinder rows scored, Anomalies*, serta tabel **Data quality report** | | | |
| ETL-10 | T | Menjalankan Incremental | Pilih **Incremental**, klik **Run ETL** | ETL selesai dengan status SUCCESS. Hanya data yang dibuat/diubah setelah *watermark* yang diproses | | | |
| ETL-11 | S | Watermark | Periksa teks *Current watermark* sebelum dan sesudah ETL | *Watermark* berisi tanggal/jam perubahan data terakhir dan diperbarui setelah ETL | | | |
| ETL-12 | S | Riwayat ETL | Periksa kartu **Run history** | Proses ETL yang baru dijalankan tercatat (waktu mulai, waktu selesai, mode, status) | | | |
| ETL-13 | S | Kecocokan jumlah data | Di SSMS jalankan `SELECT COUNT(*) FROM dw.FACT_NOON_REPORT`, lalu bandingkan dengan metrik *Reports loaded* (Full reload) | Jumlah baris sama | | | |
| ETL-14 | T | Auto ETL aktif | Jalankan aplikasi, lalu periksa sidebar dan kartu **Auto ETL** di halaman ETL Pipeline | Sidebar menampilkan "🟢 Auto ETL on · checked *jam*". Kartu Auto ETL berstatus **Running** dengan interval 60 s | | | |
| ETL-15 | T | Data baru otomatis masuk | 1. Di SSMS, tambahkan 1 baris baru (atau ubah `MODIFIED_DATE` salah satu baris) di `dbo.NOON_REPORT_COPY`<br>2. Tunggu ± 1 menit tanpa menekan tombol apa pun | ETL incremental berjalan sendiri dan muncul notifikasi *"Auto ETL: N new/changed noon report(s) loaded"*. Laporan baru tampil di dashboard dan tercatat di Run history | | | |
| ETL-16 | S | Cek manual | Klik **Check for new data now** saat tidak ada data baru | Muncul pesan *"No new data since the last ETL"* | | | |
| ETL-17 | S | Tidak ada ETL ganda | Klik **Run ETL** saat Auto ETL sedang berjalan | ETL kedua berstatus **SKIPPED** (*"Another ETL run is already in progress"*), dan data tidak rusak/dobel | | | |

### 2.3 Filter Global (FLT)

| Kode | Prioritas | Skenario | Langkah Uji | Hasil yang Diharapkan | Hasil Aktual | Status | Catatan |
|---|---|---|---|---|---|---|---|
| FLT-01 | T | Nilai awal filter | Buka halaman Noon Report pertama kali | Vessel = **All Vessels**, Voyage = **All Voyages**, rentang tanggal = **30 hari terakhir** dari data | | | |
| FLT-02 | T | Filter kapal | Pilih satu kapal, lalu klik **Apply Filters** | Seluruh KPI, grafik, dan tabel hanya menampilkan data kapal tersebut | | | |
| FLT-03 | T | Voyage mengikuti kapal | Pilih satu kapal, lalu buka dropdown **Voyage / FID_VOYAGE** | Hanya voyage milik kapal tersebut yang tampil, lengkap dengan jumlah laporannya | | | |
| FLT-04 | T | Filter tanggal | Ubah **Start Date** dan **End Date**, lalu klik **Apply Filters** | Data yang tampil hanya berada dalam rentang tanggal tersebut | | | |
| FLT-05 | S | Perubahan belum diterapkan | Ubah filter tanpa menekan Apply | Muncul teks oranye *"Filter changes are not applied yet…"*, data belum berubah | | | |
| FLT-06 | S | Tanggal terbalik | Isi Start Date lebih besar dari End Date, lalu klik Apply | Tanggal otomatis ditukar dan data tetap tampil dengan benar | | | |
| FLT-07 | S | Reset filter | Klik **Reset** | Filter kembali ke nilai awal (FLT-01) | | | |
| FLT-08 | S | Filter tetap saat pindah halaman | Terapkan filter di Noon Report, lalu buka Thermal Anomaly | Filter yang sama tetap terpasang di halaman Thermal Anomaly | | | |
| FLT-09 | S | Hasil filter kosong | Pilih kombinasi filter yang tidak punya data | Muncul pesan *"No noon reports match the selected filters."* tanpa error | | | |

### 2.4 Noon Report Dashboard (NR)

| Kode | Prioritas | Skenario | Langkah Uji | Hasil yang Diharapkan | Hasil Aktual | Status | Catatan |
|---|---|---|---|---|---|---|---|
| NR-01 | T | Ringkasan laporan | Buka halaman **Noon Report** | *Info strip* menampilkan Voyage, REPORT_DATE, NEXT_PORT (latest), Vessel. KPI **Total Noon Reports** menampilkan jumlah laporan dan jumlah voyage | | | |
| NR-02 | T | Grafik operasional | Periksa tiga grafik | Tampil grafik garis **Operational speed** (knots), **Main engine RPM**, dan **Main engine consumption** (ME_MFO_CONS & ME_MDO_CONS, MT) | | | |
| NR-03 | S | Mode multi-kapal | Pilih **All Vessels** | Subjudul grafik berubah menjadi *"Daily mean across N vessels"* | | | |
| NR-04 | S | Interaksi grafik | Arahkan kursor ke titik grafik / lakukan zoom | Muncul *tooltip* berisi tanggal dan nilai, dan grafik bisa di-zoom | | | |
| NR-05 | S | Total konsumsi | Periksa catatan di bawah grafik | Tampil rumus Total ME consumption = ΣME_MFO_CONS + ΣME_MDO_CONS beserta nilainya | | | |
| NR-06 | T | Memilih laporan | Pilih tanggal pada dropdown **Selected report** | Kartu **Main engine thermal condition** menampilkan suhu EXH_TEMP_CYL1–8 dan median, dan kartu **Environmental conditions** ikut berubah. Laporan anomali diberi tanda ⚠ ANOMALY | | | |
| NR-07 | T | Tabel detail | Periksa tabel **Detailed Noon Reports** dan **Cylinder detail** | Kedua tabel menampilkan laporan dengan urutan yang sama. Jumlah baris sesuai label *N RECORDS* | | | |
| NR-08 | S | Unduh CSV | Klik **Download CSV** | File `noon_reports.csv` terunduh dan isinya sesuai filter | | | |
| NR-09 | S | Kecocokan data | Pilih satu laporan, lalu bandingkan nilai RPM, konsumsi, dan EGT-nya dengan tabel sumber `dbo.NOON_REPORT_COPY` di SSMS | Nilainya sama (suhu teks seperti `'31° C'` tampil sebagai 31) | | | |

### 2.5 Thermal Anomaly Analysis (TA)

| Kode | Prioritas | Skenario | Langkah Uji | Hasil yang Diharapkan | Hasil Aktual | Status | Catatan |
|---|---|---|---|---|---|---|---|
| TA-01 | T | KPI anomali | Buka halaman **Thermal Anomaly**, klik **Run Analysis** | Tampil 4 KPI: Cylinder observations, Anomalies (beserta % dan jumlah laporan), Normal, Data not valid | | | |
| TA-02 | T | Grafik EGT historis | Periksa grafik **Historical exhaust gas temperature** | Garis EGT CYL1–CYL8 tampil. Pembacaan anomali ditandai **lingkaran merah**, dan laporan terpilih ditandai garis putus-putus | | | |
| TA-03 | S | Tooltip anomali | Arahkan kursor ke lingkaran merah | *Tooltip* menampilkan kapal, silinder, dan Modified Z-Score | | | |
| TA-04 | S | Laporan default | Buka halaman tanpa memilih laporan | Laporan yang terpilih otomatis adalah laporan anomali terbaru (atau laporan terbaru jika tidak ada anomali) | | | |
| TA-05 | T | Deviasi silinder | Pilih laporan lain di dropdown kanan | Grafik batang **Cylinder Deviation** berubah. Batang merah = ANOMALY, abu-abu = tidak bisa dihitung | | | |
| TA-06 | T | Pesan kesimpulan | Pilih laporan yang ANOMALY, lalu laporan yang NORMAL | Laporan anomali menampilkan kotak merah berisi silinder, deviasi, dan Z-score. Laporan normal menampilkan *"no cylinder exceeds the threshold"* | | | |
| TA-07 | S | Pencarian tabel | Ketik nama kapal / tanggal / "CYL3" di kolom **Search** | Tabel hanya menampilkan baris yang cocok | | | |
| TA-08 | S | Filter status | Pilih status **ANOMALY** pada dropdown status | Tabel hanya menampilkan baris ANOMALY, dengan warna badge sesuai statusnya | | | |
| TA-09 | S | Alasan status | Periksa kolom **Reason** untuk baris DATA_NOT_VALID | Alasan tampil dengan jelas, misalnya *"EGT missing, 0 or outside valid range"*, *"MAD = 0"*, *"Fewer than 10 historical deviations…"* | | | |
| TA-10 | S | Unduh hasil | Klik **Download results (CSV)** | File `thermal_anomaly_results.csv` terunduh sesuai filter tabel | | | |
| TA-11 | T | Verifikasi rumus | Pada *Worked example* (bagian **Calculation context**), hitung manual MZ = 0,6745 × (D − Median(B)) / MAD | Hasil hitung manual sama dengan nilai MODIFIED_Z_SCORE di aplikasi (selisih ≤ 0,01). Status ANOMALY jika \|MZ\| > 3,5 | | | |
| TA-12 | S | Silinder tidak terpasang | Pilih kapal bermesin 6 silinder | CYL7–CYL8 tidak dihitung sebagai suhu dan tidak memicu anomali | | | |

### 2.6 Fuel Consumption Forecasting (FC)

| Kode | Prioritas | Skenario | Langkah Uji | Hasil yang Diharapkan | Hasil Aktual | Status | Catatan |
|---|---|---|---|---|---|---|---|
| FC-01 | T | Forecast armada | Buka halaman **Forecasting** (Scope = All Vessels (fleet)) | Tampil 4 KPI: Forecast bulan berikutnya (MT), Last actual, **MAPE (test)** beserta kategori, dan **MAE (test)** beserta nilai α dan β | | | |
| FC-02 | T | Grafik forecast | Periksa grafik history & forecast | Tampil garis Actual, *Holt fit* (titik-titik), Forecast (putus-putus), dan *Test forecast* (tanda ×) | | | |
| FC-03 | T | Ubah horizon | Ubah **Forecast horizon** menjadi 6 | Tabel **Forecast** berisi 6 bulan dan grafik forecast bertambah panjang | | | |
| FC-04 | S | Ubah bulan uji | Ubah **Test months (MAPE)** menjadi 4 | Tabel **Model evaluation** berisi 4 bulan, dan nilai MAPE/MAE diperbarui | | | |
| FC-05 | S | Forecast per kapal | Pilih satu kapal pada Scope | Forecast kapal tersebut tampil, disertai catatan oranye bahwa data per kapal lebih fluktuatif | | | |
| FC-06 | S | Data tidak cukup | Pilih kapal dengan data bulanan yang sedikit | Muncul pesan *"Not enough monthly data to build a forecast…"* tanpa error | | | |
| FC-07 | S | Data bulanan | Buka expander **Monthly data used** | Tampil tabel rata-rata dan total konsumsi ME per bulan | | | |
| FC-08 | T | Verifikasi MAPE | Dari tabel **Model evaluation**, hitung rata-rata kolom \|Error\| % | Hasilnya sama dengan nilai KPI MAPE (selisih ≤ 0,01%) | | | |

### 2.7 Rekapitulasi Skenario

| Modul | Jumlah Skenario | Diterima | Ditolak | % Diterima |
|---|---|---|---|---|
| Navigasi & Umum (NAV) | 5 | | | |
| ETL Pipeline (ETL) | 17 | | | |
| Filter Global (FLT) | 9 | | | |
| Noon Report (NR) | 9 | | | |
| Thermal Anomaly (TA) | 12 | | | |
| Forecasting (FC) | 8 | | | |
| **Total** | **60** | | | |

% Diterima = (Jumlah Diterima / Jumlah Skenario) × 100%

---

## 3. Kuesioner Penerimaan Pengguna

**Petunjuk:** Setelah mencoba aplikasi, beri tanda ✔ pada salah satu kolom untuk setiap pernyataan.

| Skor | Keterangan |
|---|---|
| 5 | Sangat Setuju (SS) |
| 4 | Setuju (S) |
| 3 | Netral (N) |
| 2 | Tidak Setuju (TS) |
| 1 | Sangat Tidak Setuju (STS) |

| No | Aspek | Pernyataan | SS (5) | S (4) | N (3) | TS (2) | STS (1) |
|---|---|---|---|---|---|---|---|
| 1 | Kemudahan Penggunaan | Menu dan navigasi aplikasi mudah dipahami | | | | | |
| 2 | Kemudahan Penggunaan | Filter kapal, voyage, dan tanggal mudah digunakan | | | | | |
| 3 | Kemudahan Penggunaan | Proses ETL dapat dijalankan dengan mudah dari halaman web | | | | | |
| 4 | Kemudahan Penggunaan | Saya dapat mempelajari aplikasi ini dengan cepat tanpa banyak bantuan | | | | | |
| 5 | Tampilan | Tampilan dashboard rapi, konsisten, dan menarik | | | | | |
| 6 | Tampilan | Grafik dan tabel mudah dibaca dan dipahami | | | | | |
| 7 | Tampilan | Penanda warna (merah = ANOMALY) membantu saya mengenali masalah | | | | | |
| 8 | Fungsionalitas | Dashboard Noon Report membantu memantau performa operasional kapal (speed, RPM, konsumsi BBM) | | | | | |
| 9 | Fungsionalitas | Halaman Thermal Anomaly membantu mendeteksi silinder dengan suhu gas buang tidak wajar | | | | | |
| 10 | Fungsionalitas | Hasil forecasting membantu perencanaan kebutuhan bahan bakar | | | | | |
| 11 | Fungsionalitas | Fitur unduh CSV bermanfaat untuk pelaporan lebih lanjut | | | | | |
| 12 | Akurasi Informasi | Data yang ditampilkan sesuai dengan data noon report yang tercatat | | | | | |
| 13 | Akurasi Informasi | Penjelasan rumus (Calculation context) membuat hasil analisis dapat dipercaya | | | | | |
| 14 | Akurasi Informasi | Informasi yang disajikan relevan untuk pengambilan keputusan | | | | | |
| 15 | Kepuasan | Secara keseluruhan saya puas dan bersedia menggunakan aplikasi ini | | | | | |

**Saran / masukan responden:**

.................................................................................................................................

.................................................................................................................................

### 3.1 Metode Perhitungan Hasil Kuesioner

1. Skor tiap pernyataan = Σ (jumlah responden yang memilih suatu jawaban × bobot jawaban tersebut)
2. Skor maksimum = jumlah responden × 5
3. Persentase kelayakan:

$$ P = \frac{\text{Total skor yang diperoleh}}{\text{Skor maksimum}} \times 100\% $$

4. Interpretasi hasil:

| Persentase | Kategori |
|---|---|
| 0% – 20% | Sangat Tidak Baik |
| 21% – 40% | Tidak Baik |
| 41% – 60% | Cukup |
| 61% – 80% | Baik |
| 81% – 100% | Sangat Baik |

### 3.2 Tabel Rekap Kuesioner

| No | SS (×5) | S (×4) | N (×3) | TS (×2) | STS (×1) | Total Skor | Skor Maks | % | Kategori |
|---|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | | |
| 2 | | | | | | | | | |
| 3 | | | | | | | | | |
| 4 | | | | | | | | | |
| 5 | | | | | | | | | |
| 6 | | | | | | | | | |
| 7 | | | | | | | | | |
| 8 | | | | | | | | | |
| 9 | | | | | | | | | |
| 10 | | | | | | | | | |
| 11 | | | | | | | | | |
| 12 | | | | | | | | | |
| 13 | | | | | | | | | |
| 14 | | | | | | | | | |
| 15 | | | | | | | | | |
| **Rata-rata** | | | | | | | | | |

*Contoh:* 5 responden menjawab pernyataan no. 1 dengan 3 orang SS dan 2 orang S. Skornya = 3×5 + 2×4 = 23,
skor maksimum = 5×5 = 25, sehingga P = 23/25 × 100% = **92% (Sangat Baik)**.

---

## 4. Kesimpulan & Lembar Persetujuan

| Item | Hasil |
|---|---|
| Persentase skenario Diterima | ........ % |
| Skenario prioritas Tinggi yang Ditolak | ........ |
| Persentase kuesioner | ........ % (kategori: ................) |
| **Keputusan** | ☐ Diterima  ☐ Diterima dengan perbaikan  ☐ Ditolak |

**Catatan perbaikan:**

.................................................................................................................................

Dengan ini menyatakan bahwa pengujian *User Acceptance Testing* aplikasi **Marine BI Analytics** telah dilaksanakan.

| Penguji / Pengguna | Pengembang |
|---|---|
| <br><br><br>(..................................)<br>Jabatan: | <br><br><br>(..................................)<br>NIM: |

Tempat, Tanggal: ...................................
