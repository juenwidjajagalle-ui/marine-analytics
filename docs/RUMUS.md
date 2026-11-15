# Keterangan Rumus — Marine BI Analytics

Dokumen ini menjelaskan setiap rumus yang dipakai aplikasi, **di mana** rumus itu dihitung,
dan **aturan baseline** yang dipakai supaya hasilnya konsisten.

Semua perhitungan anomali ada di `analytics/thermal.py` dan dijalankan saat ETL
(tahap *ANALYZE*). Hasilnya disimpan di `dw.FACT_CYLINDER_ANOMALY` (1 baris per laporan × silinder)
dan ringkasannya di `dw.FACT_NOON_REPORT`.

---

## 0. Validasi data EGT (sebelum rumus apa pun)

| Kondisi `EXH_TEMP_CYLi`                 | Perlakuan                                    |
|-----------------------------------------|----------------------------------------------|
| NULL atau 0                             | *Tidak dilaporkan* → dibuang (NULL)          |
| < 100 °C atau > 600 °C (bisa diatur)     | *Tidak valid* → dibuang (NULL), dicatat di DQ |
| 100–600 °C                              | Valid, dipakai                               |

Kenapa 0 dibuang? Contoh data Anda: `EXH_TEMP_CYL7 = 0`, `EXH_TEMP_CYL8 = 0` — artinya mesin
6 silinder. Jika 0 ikut dihitung, median dan deviasi akan rusak.

---

## 1. Median EGT per laporan

$$
M_r = \operatorname{Median}(EGT_1, \ldots, EGT_8)\quad\text{(hanya silinder valid di laporan } r)
$$

Syarat: minimal **4 silinder valid**. Jika kurang → `CANNOT_CALCULATE` (alasan
`INSUFFICIENT_CYLINDERS`).

Contoh (data Anda, 15 Nov 2024): 345, 350, 330, 355, 375, 370 → urut: 330, 345, 350, 355, 370, 375
→ median = (350 + 355) / 2 = **352,5 °C**.

## 2. Cylinder Deviation

$$
D_i = EGT_i - M_r
$$

Deviasi dibandingkan dengan median laporan yang sama, sehingga perubahan beban mesin
(RPM, kecepatan) yang menaikkan/menurunkan semua silinder bersama-sama **tidak** dianggap anomali.
Positif = silinder lebih panas dari median.

Contoh desain (01 Jun 2025): EGT = 340, 345, 348, 342, 346, 360, 343, 344 → median 344,5
→ CYL6: 360 − 344,5 = **+15,5 °C**.

## 3. Baseline historis (aturan yang dipakai aplikasi)

> **Baseline B untuk silinder *i* pada laporan *r*** = **60 deviasi valid terakhir dari kapal yang
> sama dan silinder yang sama, yang terjadi SEBELUM laporan *r*.**

Aturan ini menjawab catatan "jangan mencampur semua tanggal dan semua silinder":

* **Per kapal** — mesin kapal berbeda punya karakter berbeda.
* **Per silinder** — CYL6 dibandingkan dengan histori CYL6 sendiri.
* **Hanya masa lalu** — laporan yang sedang dinilai tidak ikut di baseline-nya (no look-ahead),
  jadi hasil historis tidak berubah ketika data baru masuk.
* **Rolling** — baseline mengikuti kondisi mesin terbaru (setelah overhaul, dll).
* Minimal **20** nilai di baseline. Kurang dari itu → `CANNOT_CALCULATE`
  (alasan `INSUFFICIENT_BASELINE`).

Parameter `baseline_window` dan `min_baseline_obs` bisa diubah di `.streamlit/secrets.toml`
bagian `[analytics]`. Setelah diubah, jalankan **Full reload** agar semua status dihitung ulang.

## 4. MAD (Median Absolute Deviation)

$$
MAD = \operatorname{Median}\bigl(|B_k - \operatorname{Median}(B)|\bigr)
$$

MAD adalah ukuran sebaran yang **robust** — tidak mudah terpengaruh oleh beberapa nilai ekstrem,
berbeda dengan standar deviasi.

Jika MAD = 0 (semua nilai baseline sama persis) → `CANNOT_CALCULATE` (alasan `MAD_ZERO`),
karena pembagian dengan nol tidak bermakna.

## 5. Modified Z-Score (Iglewicz & Hoaglin)

$$
MZ_i = \frac{0{,}6745\,\bigl(D_i - \operatorname{Median}(B)\bigr)}{MAD}
$$

Konstanta 0,6745 membuat MZ sebanding dengan z-score biasa bila data berdistribusi normal
(karena MAD ≈ 0,6745·σ).

Contoh desain: D = +15,5; Median(B) = 0; MAD = 2,0
→ MZ = 0,6745 × (15,5 − 0) / 2,0 = **5,23**.

## 6. Anomaly Status

$$
Status_i =
\begin{cases}
\text{ANOMALY}, & |MZ_i| > 3{,}5\\
\text{NORMAL}, & |MZ_i| \le 3{,}5\\
\text{CANNOT\_CALCULATE}, & \text{data tidak cukup atau } MAD = 0
\end{cases}
$$

Status level laporan (`FACT_NOON_REPORT.Anomaly_Status`):
`ANOMALY` jika ≥ 1 silinder ANOMALY; `NORMAL` jika ada silinder yang bisa dihitung dan tidak ada
yang ANOMALY; selain itu `CANNOT_CALCULATE`.

**Catatan interpretasi:** status ANOMALY adalah tanda statistik, bukan diagnosis kerusakan.
Pada data acak tanpa anomali sungguhan, aturan ini menandai ±1% observasi
(dengan baseline 60). Window lebih panjang → lebih sedikit tanda palsu, tetapi lebih lambat
menyesuaikan dengan kondisi mesin baru.

---

## 7. Statistik deskriptif (halaman Data Information)

| Ukuran     | Rumus                                         |
|------------|-----------------------------------------------|
| N valid    | jumlah nilai terisi **dan** di dalam rentang valid |
| Missing %  | NULL ÷ total record × 100                     |
| Mean       | Σx ÷ n (hanya nilai valid)                    |
| Median     | nilai tengah setelah diurutkan                |
| Min / Max  | nilai terkecil / terbesar yang valid          |
| Std        | simpangan baku sampel (ddof = 1)              |

Rentang valid (bisa diubah di `config/settings.py`): AVG_SPEED 0–30 knot, RPM 0–250,
ME_MFO_CONS / ME_MDO_CONS 0–200 MT, AIR_TEMPERATURE −40–60 °C, dll.
Opsi **"0 = missing"** menganggap nilai 0 (kapal sandar / mesin mati) sebagai missing.

Contoh desain: AVG_SPEED = 12; 12,5; 13; 11,5; 12; 12,5; 13; NULL
→ N valid 7, missing 12,5 %, mean = 86,5 / 7 = **12,36**, median **12,50**.

## 8. Total konsumsi ME (halaman Noon Report)

$$
\text{Total ME} = \sum ME\_MFO\_CONS + \sum ME\_MDO\_CONS
$$

Nilai kosong tidak diimputasi (tidak diisi tebakan).

## 9. Kunci star schema

* `Date_Key = YYYYMMDD` dari `REPORT_DATE` (contoh 2024-11-15 05:00 → `20241115`).
* `Vessel_Key` = `V_Voyages.FCODE_VESSEL` yang dicari lewat `FID_VOYAGE = ID_VOYAGE`.
* Watermark incremental = nilai terbesar dari `MAX(CREATED_DATE, MODIFIED_DATE)`.
