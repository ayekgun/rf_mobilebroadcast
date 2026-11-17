*** Settings ***
Documentation    Keyword Layer untuk Anti-Fraud CMS JNS7 (PB082643640012YA)
...              Menerapkan True Web UI Testing (Playwright Chromium) + Multi-Layer Observability
...              Sesuai Global QA SDET & Robot Framework Constitution (Clean BDD Murni)
Library          ../../libraries/AntiFraudLibrary.py

*** Keywords ***
# ==============================================================================
# SETUP & TEARDOWN KEYWORDS
# ==============================================================================

Persiapkan Lingkungan Pengujian Anti Fraud
    DB Bersihkan Data Uji Database Anti Fraud
    AMQ Tutup Seluruh Koneksi ActiveMQ

Pulihkan Lingkungan Pengujian Anti Fraud
    SSH Pulihkan Koneksi ActiveMQ Pada SUT
    AMQ Tutup Seluruh Koneksi ActiveMQ
    DB Bersihkan Data Uji Database Anti Fraud

# ==============================================================================
# SUT LOG KEYWORDS
# ==============================================================================

Snapshot Log Delta Laravel SUT Dicatat
    SSH Ambil Snapshot Log Delta Laravel SUT

Log Delta Laravel Bebas Dari Kesalahan Fatal
    SSH Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal

# ==============================================================================
# BROWSER SPOTLIGHT E2E KEYWORDS (TC-001)
# ==============================================================================

Pengguna Menjalankan Browser E2E Journey Verifikasi Menu Dan Sidebar Spotlight
    Jalankan Browser E2E Journey Verifikasi Menu Dan Sidebar Spotlight

Seluruh Endpoint Submenu Anti Fraud Mengembalikan Status HTTP 200 OK
    UI Verifikasi Seluruh Submenu Anti Fraud 200 OK

# ==============================================================================
# RBAC & ACCESS CONTROL KEYWORDS (TC-002 & TC-009)
# ==============================================================================

Pengguna Non Authorized Berhasil Login Ke Portal JNS7
    UI Buka Portal Dan Login Sebagai Pengguna    noaccessuser

Pengguna Non Authorized Mengakses Halaman Client Config Langsung
    UI Navigasi Halaman Langsung Melalui Browser    /antifraud/config

Sistem Mengalihkan Akses Menuju Halaman Awal
    UI Verifikasi Akses Dialihkan Dari Halaman Rahasia

Permintaan AJAX Search Client Mengembalikan Status 403 Forbidden
    UI Verifikasi In Page Fetch AJAX Mengembalikan 403

Pengguna Super Admin Non CCO Berhasil Login Ke Portal JNS7
    UI Buka Portal Dan Login Sebagai Pengguna    admin

Pengguna Non CCO Mengirimkan Permintaan Langsung Ke Endpoint Approve Dan Reject
    UI Verifikasi Tombol Approval Tidak Tersedia Untuk Non CCO    101

Sistem Menolak Permintaan Dengan Pesan Khusus Role CCO
    SSH Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal

# ==============================================================================
# CONFIG CRUD & VALIDATION KEYWORDS (TC-003 s/d TC-007)
# ==============================================================================

Database Memastikan Client Uji Belum Memiliki Konfigurasi Anti Fraud
    DB Pastikan Client Belum Memiliki Konfigurasi Anti Fraud    101

Pengguna Super Admin Mengirimkan Permintaan Penambahan Konfigurasi Baru
    UI Tambah Konfigurasi Client Baru    101

Data Konfigurasi Client Pada Database Tersimpan Dengan Status DRAFT
    DB Verifikasi Data Konfigurasi Cocok Sempurna    101    DRAFT

Seluruh Kolom Parameter Rule Sesuai Sempurna Dengan Payload
    DB Verifikasi Data Konfigurasi Cocok Sempurna    101    DRAFT

Audit Log CONFIG_INSERT Tercatat Pada Database
    DB Verifikasi Audit Log Tercatat    101    CONFIG_INSERT    admin

Database Memiliki Konfigurasi Anti Fraud Aktif Untuk Client Uji
    DB Sisipkan Data Konfigurasi Uji Dengan Status    101    APPROVED    admin

Pengguna Super Admin Mengirimkan Permintaan Penambahan Konfigurasi Duplikat
    UI Tambah Konfigurasi Duplikat Dan Pastikan Ditolak    101

Sistem Menolak Permintaan Duplikasi Dengan Pesan Kesalahan Valid
    UI Verifikasi Penolakan Duplikasi Tertampil

Pengguna Super Admin Mengirimkan Form Konfigurasi Dengan Nilai Threshold Tidak Valid
    UI Tambah Konfigurasi Threshold Tidak Valid Dan Pastikan Ditolak    101

Sistem Menolak Penyimpanan Konfigurasi Serta Menampilkan Validasi Error
    SSH Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal

Database Memiliki Konfigurasi Anti Fraud Berstatus DRAFT Untuk Client Uji
    DB Sisipkan Data Konfigurasi Uji Dengan Status    101    DRAFT    None

Snapshot Baseline Konfigurasi Client Telah Disimpan
    DB Ambil Snapshot Konfigurasi Client    101

Pengguna Super Admin Mengirimkan Permintaan Pembaruan Parameter Konfigurasi
    UI Update Parameter Konfigurasi Client    101

Parameter Konfigurasi Yang Diperbarui Terbukti Berubah Sesuai Ekspektasi
    DB Verifikasi Snapshot Konfigurasi Berhasil Diperbarui    101

Seluruh Kolom Konfigurasi Lainnya Terbukti Tidak Berubah Dari Baseline
    DB Verifikasi Snapshot Konfigurasi Berhasil Diperbarui    101

Database Memiliki Konfigurasi Anti Fraud Berstatus APPROVED Dengan Approved By Terisi
    DB Sisipkan Data Konfigurasi Uji Dengan Status    101    APPROVED    admin

Status Konfigurasi Otomatis Kembali Menjadi DRAFT
    DB Verifikasi Snapshot Konfigurasi Otomatis Kembali Ke Draft    101

Kolom Approved By Direset Menjadi Null
    DB Verifikasi Snapshot Konfigurasi Otomatis Kembali Ke Draft    101

# ==============================================================================
# ACTIVEMQ TOPIC & LIFECYCLE TRANSITIONS KEYWORDS (TC-008 s/d TC-017)
# ==============================================================================

Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    AMQ Aktifkan Subscriber ActiveMQ Topic Command

Pengguna Super Admin Mengirimkan Aksi Submit Konfigurasi
    UI Eksekusi Aksi Lifecycle Pada Baris Datatable    admin    submit    101

Status Konfigurasi Pada Database Berubah Menjadi PENDING_APPROVAL
    DB Verifikasi Data Konfigurasi Cocok Sempurna    101    PENDING_APPROVAL

Ketiadaan Sinyal Reload Pada ActiveMQ Topic Terbukti Selama Rentang Waktu Pengamatan
    AMQ Verifikasi Nol Pesan Diterima Pada Topic ActiveMQ Dalam Rentang Waktu    3.0

Database Memiliki Konfigurasi Berstatus PENDING_APPROVAL Untuk Client Uji
    DB Sisipkan Data Konfigurasi Uji Dengan Status    101    PENDING_APPROVAL    None

Pengguna Role CCO Mengirimkan Aksi Persetujuan Konfigurasi
    UI Eksekusi Aksi Lifecycle Pada Baris Datatable    ccouser    approve    101

Status Konfigurasi Pada Database Berubah Menjadi APPROVED
    DB Verifikasi Data Konfigurasi Cocok Sempurna    101    APPROVED

Kolom Approved By Terisi Nama Pengguna CCO
    DB Verifikasi Kolom Approved By Terisi    101    ccouser

Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ
    AMQ Verifikasi Pesan Reload Diterima Pada Topic ActiveMQ    1    6.0

Pengguna Role CCO Mengirimkan Aksi Penolakan Konfigurasi
    UI Eksekusi Aksi Lifecycle Pada Baris Datatable    ccouser    reject    101

Status Konfigurasi Pada Database Berubah Menjadi REJECTED
    DB Verifikasi Data Konfigurasi Cocok Sempurna    101    REJECTED

Database Memiliki Konfigurasi Berstatus REJECTED Untuk Client Uji
    DB Sisipkan Data Konfigurasi Uji Dengan Status    101    REJECTED    None

Pengguna Super Admin Mengirimkan Aksi Reopen Konfigurasi
    UI Eksekusi Aksi Lifecycle Pada Baris Datatable    admin    reopen    101

Database Memiliki Konfigurasi Berstatus APPROVED Untuk Client Uji
    DB Sisipkan Data Konfigurasi Uji Dengan Status    101    APPROVED    admin

Pengguna Role CCO Mengirimkan Aksi Deaktivasi Konfigurasi
    UI Eksekusi Aksi Lifecycle Pada Baris Datatable    ccouser    deactivate    101

Status Konfigurasi Pada Database Berubah Menjadi INACTIVE
    DB Verifikasi Data Konfigurasi Cocok Sempurna    101    INACTIVE

Database Memiliki Konfigurasi Berstatus INACTIVE Untuk Client Uji
    DB Sisipkan Data Konfigurasi Uji Dengan Status    101    INACTIVE    None

Pengguna Super Admin Mengirimkan Aksi Transisi Ilegal Ke Approved
    UI Verifikasi Matriks Aksi Ketersediaan State Machine    101

Sistem Menolak Transisi Status Ilegal Tersebut
    SSH Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal

Seluruh Kolom Konfigurasi Baseline Terbukti Tidak Mengalami Perubahan
    DB Verifikasi Data Konfigurasi Cocok Sempurna    101    DRAFT

Pengguna Super Admin Mengeksekusi Tombol SYNC Konfigurasi
    UI Eksekusi Tombol SYNC Konfigurasi

Audit Log SYNC_CONFIG Tercatat Pada Database
    DB Verifikasi Audit Log Tercatat    0    SYNC_CONFIG    admin

Pengguna Role CCO Menjalankan Transisi Siklus Approval Pada Lingkungan Eksklusif
    UI Eksekusi Aksi Lifecycle Pada Baris Datatable    ccouser    approve    101

Sinyal Reload Anti Fraud Diterima Tepat Satu Kali Pada Topic ActiveMQ
    AMQ Verifikasi Pesan Reload Diterima Pada Topic ActiveMQ    1    6.0

# ==============================================================================
# WHITELIST KEYWORDS (TC-018 s/d TC-022)
# ==============================================================================

Pengguna Super Admin Mengirimkan Permintaan Penambahan Whitelist MSISDN
    UI Tambah Whitelist Target    msisdn    101    +628123456789    Whitelist MSISDN E2E

Data Whitelist MSISDN Tersimpan Pada Database Dengan Status Aktif
    DB Verifikasi Data Whitelist Database    101    msisdn    +628123456789    1

Pengguna Super Admin Mengirimkan Permintaan Penambahan Whitelist Prefix
    UI Tambah Whitelist Target    prefix    101    0812999    Whitelist Prefix E2E

Data Whitelist Prefix Tersimpan Pada Database Dengan Status Aktif
    DB Verifikasi Data Whitelist Database    101    prefix    0812999    1

Database Memastikan Data Uji Whitelist Bersih
    DB Bersihkan Data Uji Database Anti Fraud

Pengguna Super Admin Mengirimkan Penambahan Whitelist Dengan Format Tidak Sesuai Aturan
    UI Tambah Whitelist Format Tidak Valid Dan Pastikan Ditolak

Sistem Menolak Penambahan Whitelist Tersebut Dengan Pesan Validasi
    UI Verifikasi Penolakan Form Whitelist Tertampil

Database Memiliki Data Whitelist Nonaktif Untuk Client Uji
    DB Sisipkan Data Whitelist Uji    101    msisdn    +628123456789    0

Pengguna Super Admin Mengirimkan Penambahan Whitelist Untuk Target Yang Sama
    UI Tambah Whitelist Target    msisdn    101    +628123456789    Reaktivasi Whitelist Target

Status Whitelist Pada Database Berubah Kembali Menjadi Aktif
    DB Verifikasi Data Whitelist Database    101    msisdn    +628123456789    1

Pengguna Super Admin Mengirimkan Kembali Penambahan Whitelist Target Yang Telah Aktif
    UI Tambah Whitelist Target    msisdn    101    +628123456789    Duplikasi Target Aktif

Sistem Menolak Duplikasi Target Whitelist Aktif
    SSH Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal

Database Memiliki Data Whitelist MSISDN Aktif Untuk Client Uji
    DB Sisipkan Data Whitelist Uji    101    msisdn    +628123456789    1

Pengguna Super Admin Mengirimkan Aksi Deaktivasi Whitelist
    UI Toggle Status Whitelist Pada Datatable    +628123456789    deactivate

Status Whitelist Pada Database Berubah Menjadi Nonaktif
    DB Verifikasi Data Whitelist Database    101    msisdn    +628123456789    0

# ==============================================================================
# BLOCKLIST & UNBLOCK KEYWORDS (TC-023 s/d TC-026)
# ==============================================================================

Database Memiliki Data Block State Aktif Untuk Client Uji
    DB Sisipkan Data Block State Uji    101    6281200000001    MSISDN    ACTIVE

Pengguna Role CCO Membuka Halaman Blocklist
    UI Buka Halaman Blocklist Dan Observasi Otorisasi    cco

Halaman Menampilkan Target Fraud Aktif Beserta Rincian Rule Dan Status
    UI Buka Halaman Blocklist Dan Observasi Otorisasi    non_cco

Subscriber ActiveMQ Queue Action Telah Aktif Dan Siap Menerima Pesan
    AMQ Aktifkan Subscriber ActiveMQ Queue Action

Pengguna Role CCO Mengirimkan Permintaan Unblock Dengan Alasan Valid
    UI Eksekusi Unblock Target Dengan Alasan    6281200000001    Valid customer unblock request

Status Block State Pada Database Berubah Menjadi INACTIVE
    DB Verifikasi Data Block State Database    101    6281200000001    INACTIVE    ccouser    Valid customer unblock request

Kolom Unblocked By Dan Unblock Reason Terisi Sesuai Ekspektasi
    DB Verifikasi Data Block State Database    101    6281200000001    INACTIVE    ccouser    Valid customer unblock request

Payload Exact JSON Diterima Pada Queue Action ActiveMQ
    AMQ Verifikasi Payload Exact JSON Diterima Pada Queue ActiveMQ    6281200000001    ccouser    6.0

Pengguna Role CCO Mengirimkan Permintaan Unblock Dengan Alasan Kosong Atau Spasi
    UI Eksekusi Unblock Dengan Alasan Spasi Dan Pastikan Ditolak    6281200000001

Sistem Menolak Permintaan Unblock Dan Status Tetap ACTIVE
    DB Verifikasi Data Block State Database    101    6281200000001    ACTIVE    None    None

Gangguan Koneksi ActiveMQ Disimulasikan Pada SUT
    SSH Simulasikan Gangguan Koneksi ActiveMQ Pada SUT

Pengguna Role CCO Mengirimkan Permintaan Unblock
    UI Eksekusi Unblock Target Dengan Alasan    6281200000001    Unblock Broker Disconnect Test

Status Block State Pada Database Tetap ACTIVE
    DB Verifikasi Data Block State Database    101    6281200000001    ACTIVE    None    None

Audit Log Mencatat Kejadian UNBLOCK_FAILED
    DB Verifikasi Audit Log Tercatat    101    UNBLOCK_FAILED    ccouser

Konektivitas ActiveMQ Pada SUT Berhasil Dipulihkan
    SSH Pulihkan Koneksi ActiveMQ Pada SUT

# ==============================================================================
# AUDIT TRAIL KEYWORDS (TC-027 s/d TC-028)
# ==============================================================================

Database Memastikan Riwayat Audit Log Client Uji Bersih
    DB Bersihkan Data Uji Database Anti Fraud

Pengguna Menjalankan Siklus Penuh Konfigurasi Client Uji
    UI Eksekusi Siklus Penuh Konfigurasi    101

Seluruh Jejak Audit Trail Konfigurasi Terverifikasi Lengkap Pada Database
    DB Verifikasi Audit Log Tercatat    101    CONFIG_INSERT    admin

Pengguna Menjalankan Siklus Operasi Whitelist Dan Unblock
    UI Eksekusi Siklus Whitelist Dan Unblock    101

Seluruh Jejak Audit Trail Whitelist Dan Unblock Terverifikasi Lengkap Pada Database
    DB Verifikasi Audit Log Tercatat    101    WHITELIST_ADD    admin

# ==============================================================================
# MULTI-TENANT KEYWORDS (TC-029 s/d TC-030)
# ==============================================================================

Pengguna Super Admin JATIS Berhasil Login Ke Portal JNS7
    UI Buka Portal Dan Login Sebagai Pengguna    admin

Pengguna Mengakses Seluruh Menu Anti Fraud
    UI Akses Seluruh Menu Anti Fraud Lintas Tenant

Seluruh Data Lintas Tenant Dapat Dilihat Dan Dikelola Secara Penuh
    SSH Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal

Fixture Data Multi Tenant Client Sepuluh Dan Dua Puluh Tersedia Di Database
    DB Siapkan Fixture Multi Tenant Client Sepuluh Dan Dua Puluh

Pengguna Non JATIS Client Sepuluh Mengakses Endpoint DataTables AJAX
    UI Observasi Isolasi Multi Tenant Pada Seluruh Datatable    client10user    10    20

Respons Hanya Menampilkan Data Milik Client Sepuluh
    SSH Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal

Data Milik Client Dua Puluh Terbukti Tidak Bocor Sama Sekali
    SSH Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal
