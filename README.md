# Robot Framework Automation Suite: Anti-Fraud JNS7 (PB082643640012YA)

Suite otomasi pengujian **Robot Framework** berbasis **True Web UI Testing** menggunakan engine **Playwright Chromium** untuk fitur **Anti-Fraud CMS** pada aplikasi **MobileBroadcast (JNS7)**.

---

## 📌 Informasi Proyek
- **Tiket JIRA**: `PB082643640012YA`
- **SUT (System Under Test)**: JNS7 Web CMS (`mobilebroadcast`) - Laravel & AdminLTE
- **Target URL**: `http://192.168.181.60/mobilebroadcast/`
- **Cakupan Pengujian**: 30 Test Cases (TC-001 s/d TC-030)
- **Kaidah Utama**: 
  - **Clean BDD Murni**: *Zero Dollar Signs* (`${...}`) pada blok `*** Test Cases ***`.
  - **True Web UI Testing**: 100% aksi pemicu bisnis dilakukan melalui browser Playwright (bukan synthetic HTTP API).
  - **Multi-Layer Observability**: Verifikasi menyeluruh pada DOM, respons jaringan AJAX, MySQL (20+ kolom), ActiveMQ STOMP, dan log Laravel delta via SSH.
  - **Zero Truncation**: Flag `--maxassignlength 0` dan logging chunked via `_log_chunked`.

---

## 📂 Struktur Direktori
```
rf_mobilebroadcast/
├── libraries/                  # Custom Python Libraries & Listeners
│   ├── AntiFraudLibrary.py     # Driver Playwright UI, Database, ActiveMQ STOMP, & SSH
│   ├── CsvListener.py          # Auto-update listener untuk testcase.csv (12 kolom wajib)
│   ├── LogHelper.py            # Helper logging anti-truncation (_log_chunked)
│   ├── SutLogLibrary.py        # Pengambil snapshot log delta Laravel via SSH
│   └── mock_events_queue.py    # Thread-safe event queue
├── resources/
│   └── keywords/
│       └── anti_fraud_keywords.robot # Definisi Clean BDD Keyword (Bahasa Indonesia)
├── tests/
│   └── test_anti_fraud_cms.robot     # Suite pengujian 30 test case (TC-001 s/d TC-030)
├── scripts/
│   ├── run_tests.sh            # Standard runner (Headless/CI-CD mode)
│   ├── run_headed.sh           # Live Watch runner (Tampil jendela browser di layar)
│   ├── run_poc_journey.sh      # POC Interactive 7-step Spotlight HUD runner
│   ├── check_duplicate_keywords.sh # Gate 1: Cek duplikasi keyword
│   ├── check_keyword_collision.sh  # Gate 1: Cek benturan nama keyword (rekursi)
│   └── check_missing_keywords.sh   # Gate 1: Cek keyword yang belum didefinisikan
├── results/                    # Output artefak pengujian (log.html, report.html, output.xml)
├── testcase.csv                # Lembar tracking QA 12 kolom terstandarisasi
├── sut_profile.yaml            # Spesifikasi profil SUT & audit regex
└── README.md                   # Petunjuk penggunaan suite
```

---

## 🚀 Panduan Menjalankan Pengujian

Anda dapat menjalankan perintah langsung dari root workspace `mobilebroadcast/` atau dari dalam direktori `rf_mobilebroadcast/`.

### 1. Menjalankan Seluruh Test Case (Full Suite 30 TC)

#### A. Mode Headless (Default / Background - Cepat & Stabil)
Browser berjalan di latar belakang tanpa memunculkan jendela GUI.
```bash
# Dari root workspace:
./rf_mobilebroadcast/run_tests.sh tests/test_anti_fraud_cms.robot

# Atau dari dalam folder rf_mobilebroadcast:
cd rf_mobilebroadcast
./run_tests.sh tests/test_anti_fraud_cms.robot
```

#### B. Mode Headed (Live Watch - Memunculkan Jendela Browser di Layar)
Membuka browser Chromium di layar (`DISPLAY=:0`) sehingga Anda dapat melihat interaksi klik, form, modal, dan navigasi secara langsung.
```bash
# Dari root workspace:
./rf_mobilebroadcast/run_headed.sh tests/test_anti_fraud_cms.robot

# Atau dari dalam folder rf_mobilebroadcast:
cd rf_mobilebroadcast
./run_headed.sh tests/test_anti_fraud_cms.robot
```

---

### 2. Menjalankan Test Case Tertentu (Single / Spesifik)

Gunakan flag `-t` atau `--test` diikuti nama atau pola test case:

```bash
# Menjalankan hanya TC-001 (Verifikasi Sidebar & Menu):
./rf_mobilebroadcast/run_headed.sh -t "TC-001*" tests/test_anti_fraud_cms.robot

# Menjalankan hanya TC-003 (Tambah Konfigurasi Client Baru):
./rf_mobilebroadcast/run_headed.sh -t "TC-003*" tests/test_anti_fraud_cms.robot

# Menjalankan hanya TC-024 (CCO Unblock Target):
./rf_mobilebroadcast/run_headed.sh -t "TC-024*" tests/test_anti_fraud_cms.robot

# Menjalankan beberapa test case sekaligus:
./rf_mobilebroadcast/run_tests.sh -t "TC-001*" -t "TC-002*" -t "TC-003*" tests/test_anti_fraud_cms.robot
```

---

### 3. Menjalankan Pengujian Berdasarkan Tag

Gunakan flag `-i` atau `--include` diikuti tag pengujian:

```bash
# Menjalankan seluruh test case berprioritas P0:
./rf_mobilebroadcast/run_tests.sh -i P0 tests/test_anti_fraud_cms.robot

# Menjalankan seluruh skenario Happy Path:
./rf_mobilebroadcast/run_tests.sh -i happy_path tests/test_anti_fraud_cms.robot

# Menjalankan seluruh skenario Negative / Validasi:
./rf_mobilebroadcast/run_tests.sh -i negative tests/test_anti_fraud_cms.robot

# Menjalankan kelompok fitur Whitelist (TC-018 s/d TC-022):
./rf_mobilebroadcast/run_tests.sh -i whitelist tests/test_anti_fraud_cms.robot

# Menjalankan kelompok fitur Blocklist & Unblock (TC-023 s/d TC-026):
./rf_mobilebroadcast/run_tests.sh -i blocklist tests/test_anti_fraud_cms.robot

# Menjalankan pengujian Audit Trail (TC-027 s/d TC-028):
./rf_mobilebroadcast/run_tests.sh -i audit tests/test_anti_fraud_cms.robot

# Menjalankan pengujian Multi-Tenant & Isolasi Data (TC-029 s/d TC-030):
./rf_mobilebroadcast/run_tests.sh -i multitenant tests/test_anti_fraud_cms.robot
```

---

### 4. Pengecekan Sintaks & Validasi (Dry Run & Quality Audits)

#### A. Dry Run (Kompilasi Cepat Tanpa Membuka Browser)
Memverifikasi bahwa seluruh keyword Clean BDD terhubung ke implementasi Python tanpa error:
```bash
python3 -m robot --pythonpath rf_mobilebroadcast/libraries --dryrun rf_mobilebroadcast/tests/test_anti_fraud_cms.robot
```

#### B. Audit Gerbang Kualitas (Gate 1)
Memeriksa integritas keyword, mendeteksi duplikasi, dan mencegah risiko rekursi:
```bash
cd rf_mobilebroadcast
./scripts/check_duplicate_keywords.sh
./scripts/check_keyword_collision.sh
./scripts/check_missing_keywords.sh
```

---

### 5. Injected DOM Spotlight Box Overlay & HUD (Live Visual Monitoring)
Suite ini dilengkapi dengan teknologi **Injected DOM Spotlight Box Overlay & HUD** yang aktif secara otomatis pada seluruh 30 Test Case (TC-001 s/d TC-030) saat dijalankan dalam mode **Headed** (`./scripts/run_headed.sh` atau `HEADED=1`).

#### Fitur Visual HUD & Spotlight:
- **Top HUD Bar**: Menampilkan ID Test Case (`TC-xxx`), BDD Phase Badge (`GIVEN`, `WHEN`, `THEN`, `AND`), Judul Aksi, Rincian Langkah, dan Status (`RUNNING` / `PASSED`).
- **Neon Cyan Spotlight Box**: Kotak beranimasi cyan dengan efek *shadow scrim mask* (`box-shadow: 0 0 0 9999px rgba(...)`) yang menyorot dan menandai secara presisi setiap elemen aktif:
  - Form field (input username, password, email alert, threshold, reason unblock)
  - Dropdown selector (pilihan client ID, tipe whitelist MSISDN/Prefix)
  - Tombol aksi (Submit, Approve, Reject, Deactivate, Reopen, SYNC, Tambah Whitelist, Toggle, Unblock)
  - Baris DataTables dan status badge
  - Banner alert validasi dan penolakan
- **Human-Observable Pacing**: Penundaan visual terukur (~0.35s) di mode headed sehingga pengguna dapat memantau jalannya pengujian dan asersi secara *real-time*.
- **Zero Overhead di Mode Headless**: Di mode default CI-CD (`HEADED=0`), visual delay di-bypass (`0.0s`) sehingga eksekusi suite penuh tetap berjalan secepat kilat.

Untuk mencoba demo spotlight interaktif 7-langkah:
```bash
./rf_mobilebroadcast/run_poc_journey.sh
```

---

## 📊 Hasil Pengujian & Laporan

Setelah pengujian selesai dijalankan, hasil pengujian tersimpan secara otomatis pada:
- **`rf_mobilebroadcast/results/log.html`**: Log eksekusi detail per langkah, memuat snapshot data lengkap (*anti-truncation*). Buka file ini di browser untuk audit.
- **`rf_mobilebroadcast/results/report.html`**: Ringkasan visual eksekusi per suite dan test case.
- **`rf_mobilebroadcast/results/output.xml`**: Format XML standar untuk integrasi CI/CD.
- **`rf_mobilebroadcast/testcase.csv`**: Lembar tracking 12 kolom wajib yang otomatis terisi status `PASS`/`FAIL`, durasi eksekusi, dan timestamp aktual.

Contoh cara membuka log di browser lokal:
```bash
google-chrome rf_mobilebroadcast/results/log.html
# atau
xdg-open rf_mobilebroadcast/results/log.html
```

---

## ⚙️ Variabel Lingkungan Opsional (Environment Variables)

Suite otomasi sudah memiliki nilai default siap pakai untuk lingkungan SIT JNS7. Namun jika diperlukan, Anda dapat mengubah konfigurasi target melalui environment variable sebelum menjalankan runner:

```bash
export AF_BASE_URL="http://192.168.181.60/mobilebroadcast"  # URL portal CMS SUT
export AF_DB_HOST="192.168.181.63"                          # Host database MySQL
export AF_DB_USER="root"                                     # User database
export AF_DB_PASS="jatis123"                                 # Password database
export AF_MQ_HOST="192.168.181.51"                          # Host broker ActiveMQ
export AF_SSH_HOST="192.168.181.60"                         # Host SUT untuk pengecekan log
export AF_SSH_PASS="password"                               # Password SSH SUT
export DISPLAY=":0"                                          # Display server untuk headed mode
```

---

## 🛡️ Status Quality Gates
- **Gate 1 (Clean Architecture & Audits)**: **PASSED** (0 duplicate, 0 recursion, 0 missing keywords)
- **Gate 2 (Dry Run Validation)**: **PASSED** (30/30 tests parsed successfully)
- **Gate 3 (Proven Mutation Sensitivity)**: **PROVEN** (Fail-fast `AssertionError` terbukti sensitif saat data dimutasi)
- **Gate 4 (Full True Web UI Execution)**: **PASSED** (30 tests, 30 passed, 0 failed via Playwright)
- **Gate 5 (Standardized CSV Tracking)**: **100% PASS** (30/30 tersinkronisasi di `testcase.csv`)
- **SUT Source Code**: **READ-ONLY** (`git status` branch `SIT` 100% clean dan tidak dimodifikasi)
