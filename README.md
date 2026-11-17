# Robot Framework Automation Suite: Anti-Fraud JNS7 (PB082643640012YA)

Suite otomasi pengujian **Robot Framework V8** untuk fitur **Anti-Fraud CMS** pada aplikasi **MobileBroadcast (JNS7)**.

## 📌 Deskripsi Proyek
- **Tiket**: `PB082643640012YA`
- **SUT**: JNS7 Web CMS (`mobilebroadcast`) - Laravel & AdminLTE
- **Target URL**: `http://192.168.181.60/mobilebroadcast/`
- **Cakupan**: 30 Test Cases (TC-001 s/d TC-030)
- **Kaidah**: Clean BDD Murni (*Zero Dollar Signs* pada blok `*** Test Cases ***`), Zero False Positive Protocol, Transparent Logging dengan `_log_chunked`.

## 📂 Struktur Direktori
```
rf_mobilebroadcast/
├── automation/                 # Playwright CDP Engine, Spotlight Runner & HUD Overlay
│   ├── spotlight_hud_runner.py # Standalone 7-step interactive browser runner
│   └── screenshots/            # Visual snapshots E2E
├── libraries/                  # Custom Python Libraries & Listeners
│   ├── AntiFraudLibrary.py     # Core automation library (DB, ActiveMQ, HTTP, Playwright)
│   ├── CsvListener.py          # Auto-update listener untuk testcase.csv (12 kolom)
│   ├── LogHelper.py            # Anti-truncation logging helper via _log_chunked
│   ├── SutLogLibrary.py        # SUT delta log collector
│   └── mock_events_queue.py    # Thread-safe event queue
├── resources/
│   └── keywords/
│       └── anti_fraud_keywords.robot # Clean BDD Indonesian keyword definitions
├── scripts/
│   ├── run_tests.sh            # Standard runner (--maxassignlength 0, CsvListener)
│   ├── run_headed.sh           # Foreground Live Watch mode runner
│   ├── run_poc_journey.sh      # Full 7-step interactive POC runner
│   ├── check_duplicate_keywords.sh
│   ├── check_keyword_collision.sh
│   └── check_missing_keywords.sh
├── tests/
│   └── test_anti_fraud_cms.robot # Test suite covering TC-001 to TC-030
├── tools/
│   └── generate_summary_docx.py # Gate 6 Executive Summary generator
├── sut_profile.yaml            # SUT profile and regex specifications
└── testcase.csv                # Standardized 12-column QA tracking sheet
```

## 🚀 Cara Menjalankan

### 1. Mode Headless (Background Execution)
```bash
./scripts/run_tests.sh tests/test_anti_fraud_cms.robot
```

### 2. Mode Headed (Foreground Live Watch)
```bash
./scripts/run_headed.sh -t "TC-001*" tests/test_anti_fraud_cms.robot
```

### 3. Full 7-Step Interactive Spotlight & HUD POC Journey
```bash
./scripts/run_poc_journey.sh
```

## 📊 Quality Gates Status
- **Gate 1 (Audits)**: PASSED (0 duplicate, 0 collision risk, 0 missing keyword)
- **Gate 2 (Dry Run)**: PASSED (30/30)
- **Gate 3 (Mutation Sensitivity)**: PROVEN
- **Gate 4 (Full Execution)**: PASSED (30/30)
- **Gate 5 (CSV Tracking)**: 100% PASS (30/30 di `testcase.csv`)
