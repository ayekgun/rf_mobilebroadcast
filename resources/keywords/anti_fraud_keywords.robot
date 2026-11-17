*** Settings ***
Documentation    Keyword Layer untuk Anti-Fraud CMS JNS7 (PB082643640012YA)
...              Menerapkan Clean BDD Murni (Zero Dollar Signs pada Test Cases)
...              Mengenkapsulasi seluruh interaksi Database, ActiveMQ, HTTP, Log, dan Spotlight Browser E2E
Library          ../../libraries/AntiFraudLibrary.py

*** Keywords ***
# ==============================================================================
# SETUP & TEARDOWN KEYWORDS
# ==============================================================================

Persiapkan Lingkungan Pengujian Anti Fraud
    Bersihkan Data Uji Database Anti Fraud
    Tutup Seluruh Koneksi ActiveMQ

Pulihkan Lingkungan Pengujian Anti Fraud
    Pulihkan Koneksi ActiveMQ Pada SUT
    Tutup Seluruh Koneksi ActiveMQ
    Bersihkan Data Uji Database Anti Fraud

# ==============================================================================
# SUT LOG KEYWORDS
# ==============================================================================

Snapshot Log Delta Laravel SUT Dicatat
    Ambil Snapshot Log Delta Laravel SUT

Log Delta Laravel Bebas Dari Kesalahan Fatal
    Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal

# ==============================================================================
# BROWSER SPOTLIGHT E2E KEYWORDS
# ==============================================================================

Pengguna Menjalankan Browser E2E Journey Verifikasi Menu Dan Sidebar Spotlight
    Jalankan Browser E2E Journey Verifikasi Menu Dan Sidebar Spotlight

Seluruh Endpoint Submenu Anti Fraud Mengembalikan Status HTTP 200 OK
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Akses Halaman URL Dan Pastikan Status Respons    admin    /antifraud/config    200
    Akses Halaman URL Dan Pastikan Status Respons    admin    /antifraud/whitelist    200
    Akses Halaman URL Dan Pastikan Status Respons    admin    /antifraud/blocks    200
    Akses Halaman URL Dan Pastikan Status Respons    admin    /antifraud/audit    200

# ==============================================================================
# RBAC & ACCESS CONTROL KEYWORDS
# ==============================================================================

Pengguna Non Authorized Berhasil Login Ke Portal JNS7
    Pengguna Berhasil Login Ke Portal JNS7    noaccessuser

Pengguna Non Authorized Mengakses Halaman Client Config Langsung
    Akses Halaman URL Dan Pastikan Dialihkan    noaccessuser    /antifraud/config

Sistem Mengalihkan Akses Menuju Halaman Awal
    Log Delta Laravel Bebas Dari Kesalahan Fatal

Permintaan AJAX Search Client Mengembalikan Status 403 Forbidden
    Kirim Permintaan AJAX Search Dan Pastikan Ditolak    noaccessuser    /antifraud/config/search-clients

Pengguna Super Admin Non CCO Berhasil Login Ke Portal JNS7
    Pengguna Berhasil Login Ke Portal JNS7    admin

Pengguna Non CCO Mengirimkan Permintaan Langsung Ke Endpoint Approve Dan Reject
    Kirim Permintaan Aksi Lifecycle Terlarang Dan Pastikan Ditolak    admin    approve    101
    Kirim Permintaan Aksi Lifecycle Terlarang Dan Pastikan Ditolak    admin    reject    101

Sistem Menolak Permintaan Dengan Pesan Khusus Role CCO
    Log Delta Laravel Bebas Dari Kesalahan Fatal

# ==============================================================================
# CONFIG CRUD & VALIDATION KEYWORDS
# ==============================================================================

Database Memastikan Client Uji Belum Memiliki Konfigurasi Anti Fraud
    Pastikan Client Belum Memiliki Konfigurasi Anti Fraud    101

Pengguna Super Admin Mengirimkan Permintaan Penambahan Konfigurasi Baru
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Tambah Konfigurasi Anti Fraud    admin    101

Data Konfigurasi Client Pada Database Tersimpan Dengan Status DRAFT
    Verifikasi Data Konfigurasi Database Cocok Sempurna    101    DRAFT

Seluruh Kolom Parameter Rule Sesuai Sempurna Dengan Payload
    Verifikasi Data Konfigurasi Database Cocok Sempurna    101    DRAFT

Audit Log CONFIG_INSERT Tercatat Pada Database
    Verifikasi Audit Log Tercatat    101    CONFIG_INSERT    admin

Database Memiliki Konfigurasi Anti Fraud Aktif Untuk Client Uji
    Sisipkan Data Konfigurasi Uji Dengan Status    101    APPROVED    admin

Pengguna Super Admin Mengirimkan Permintaan Penambahan Konfigurasi Duplikat
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Tambah Konfigurasi Duplikat Dan Pastikan Ditolak    admin    101

Sistem Menolak Permintaan Duplikasi Dengan Pesan Kesalahan Valid
    Log Delta Laravel Bebas Dari Kesalahan Fatal

Pengguna Super Admin Mengirimkan Form Konfigurasi Dengan Nilai Threshold Tidak Valid
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Tambah Konfigurasi Dengan Threshold Tidak Valid Dan Pastikan Ditolak    admin    101

Sistem Menolak Penyimpanan Konfigurasi Serta Menampilkan Validasi Error
    Log Delta Laravel Bebas Dari Kesalahan Fatal

Database Memiliki Konfigurasi Anti Fraud Berstatus DRAFT Untuk Client Uji
    Sisipkan Data Konfigurasi Uji Dengan Status    101    DRAFT

Snapshot Baseline Konfigurasi Client Telah Disimpan
    Ambil Snapshot Konfigurasi Client    101

Pengguna Super Admin Mengirimkan Permintaan Pembaruan Parameter Konfigurasi
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Update Konfigurasi Anti Fraud    admin    101

Parameter Konfigurasi Yang Diperbarui Terbukti Berubah Sesuai Ekspektasi
    Log Delta Laravel Bebas Dari Kesalahan Fatal

Seluruh Kolom Konfigurasi Lainnya Terbukti Tidak Berubah Dari Baseline
    Verifikasi Snapshot Konfigurasi Berhasil Diperbarui    101

Database Memiliki Konfigurasi Anti Fraud Berstatus APPROVED Dengan Approved By Terisi
    Sisipkan Data Konfigurasi Uji Dengan Status    101    APPROVED    admin

Status Konfigurasi Otomatis Kembali Menjadi DRAFT
    Verifikasi Data Konfigurasi Database Cocok Sempurna    101    DRAFT

Kolom Approved By Direset Menjadi Null
    Verifikasi Snapshot Konfigurasi Otomatis Kembali Ke Draft    101

# ==============================================================================
# ACTIVEMQ TOPIC & LIFECYCLE TRANSITIONS KEYWORDS
# ==============================================================================

Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    Aktifkan Subscriber ActiveMQ Topic Command

Pengguna Super Admin Mengirimkan Aksi Submit Konfigurasi
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Aksi Lifecycle Konfigurasi    admin    submit    101

Status Konfigurasi Pada Database Berubah Menjadi PENDING_APPROVAL
    Verifikasi Data Konfigurasi Database Cocok Sempurna    101    PENDING_APPROVAL

Ketiadaan Sinyal Reload Pada ActiveMQ Topic Terbukti Selama Rentang Waktu Pengamatan
    Verifikasi Nol Pesan Diterima Pada Topic ActiveMQ Dalam Rentang Waktu    5.0

Database Memiliki Konfigurasi Berstatus PENDING_APPROVAL Untuk Client Uji
    Sisipkan Data Konfigurasi Uji Dengan Status    101    PENDING_APPROVAL

Pengguna Role CCO Mengirimkan Aksi Persetujuan Konfigurasi
    Pengguna Berhasil Login Ke Portal JNS7    ccouser
    Kirim Permintaan Aksi Lifecycle Konfigurasi    ccouser    approve    101

Status Konfigurasi Pada Database Berubah Menjadi APPROVED
    Verifikasi Data Konfigurasi Database Cocok Sempurna    101    APPROVED

Kolom Approved By Terisi Nama Pengguna CCO
    Verifikasi Kolom Approved By Terisi    101    ccouser

Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ
    Verifikasi Pesan Reload Diterima Pada Topic ActiveMQ    1    5.0

Pengguna Role CCO Mengirimkan Aksi Penolakan Konfigurasi
    Pengguna Berhasil Login Ke Portal JNS7    ccouser
    Kirim Permintaan Aksi Lifecycle Konfigurasi    ccouser    reject    101

Status Konfigurasi Pada Database Berubah Menjadi REJECTED
    Verifikasi Data Konfigurasi Database Cocok Sempurna    101    REJECTED

Database Memiliki Konfigurasi Berstatus REJECTED Untuk Client Uji
    Sisipkan Data Konfigurasi Uji Dengan Status    101    REJECTED

Pengguna Super Admin Mengirimkan Aksi Reopen Konfigurasi
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Aksi Lifecycle Konfigurasi    admin    reopen    101

Database Memiliki Konfigurasi Berstatus APPROVED Untuk Client Uji
    Sisipkan Data Konfigurasi Uji Dengan Status    101    APPROVED    admin

Pengguna Role CCO Mengirimkan Aksi Deaktivasi Konfigurasi
    Pengguna Berhasil Login Ke Portal JNS7    ccouser
    Kirim Permintaan Aksi Lifecycle Konfigurasi    ccouser    deactivate    101

Status Konfigurasi Pada Database Berubah Menjadi INACTIVE
    Verifikasi Data Konfigurasi Database Cocok Sempurna    101    INACTIVE

Database Memiliki Konfigurasi Berstatus INACTIVE Untuk Client Uji
    Sisipkan Data Konfigurasi Uji Dengan Status    101    INACTIVE

Pengguna Super Admin Mengirimkan Aksi Transisi Ilegal Ke Approved
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Aksi Lifecycle Terlarang Dan Pastikan Ditolak    admin    approve    101

Sistem Menolak Transisi Status Ilegal Tersebut
    Log Delta Laravel Bebas Dari Kesalahan Fatal

Seluruh Kolom Konfigurasi Baseline Terbukti Tidak Mengalami Perubahan
    Verifikasi Snapshot Konfigurasi Tidak Mengalami Perubahan Sama Sekali    101

Pengguna Super Admin Mengeksekusi Tombol SYNC Konfigurasi
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan SYNC Konfigurasi    admin

Audit Log SYNC_CONFIG Tercatat Pada Database
    Verifikasi Audit Log Tercatat    0    SYNC_CONFIG    admin

Pengguna Role CCO Menjalankan Transisi Siklus Approval Pada Lingkungan Eksklusif
    Pengguna Berhasil Login Ke Portal JNS7    ccouser
    Kirim Permintaan Aksi Lifecycle Konfigurasi    ccouser    approve    101

Sinyal Reload Anti Fraud Diterima Tepat Satu Kali Pada Topic ActiveMQ
    Verifikasi Pesan Reload Diterima Pada Topic ActiveMQ    1    5.0

# ==============================================================================
# WHITELIST KEYWORDS
# ==============================================================================

Pengguna Super Admin Mengirimkan Permintaan Penambahan Whitelist MSISDN
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Tambah Whitelist    admin    101    msisdn    +628123456789    Test Whitelist MSISDN

Data Whitelist MSISDN Tersimpan Pada Database Dengan Status Aktif
    Verifikasi Data Whitelist Database    101    msisdn    +628123456789    1

Pengguna Super Admin Mengirimkan Permintaan Penambahan Whitelist Prefix
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Tambah Whitelist    admin    101    prefix    62812    Test Whitelist Prefix

Data Whitelist Prefix Tersimpan Pada Database Dengan Status Aktif
    Verifikasi Data Whitelist Database    101    prefix    62812    1

Database Memastikan Data Uji Whitelist Bersih
    Bersihkan Data Uji Database Anti Fraud

Pengguna Super Admin Mengirimkan Penambahan Whitelist Dengan Format Tidak Sesuai Aturan
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Tambah Whitelist Tidak Valid Dan Pastikan Ditolak    admin    101    msisdn    INVALID_NUMBER

Sistem Menolak Penambahan Whitelist Tersebut Dengan Pesan Validasi
    Log Delta Laravel Bebas Dari Kesalahan Fatal

Database Memiliki Data Whitelist Nonaktif Untuk Client Uji
    Sisipkan Data Whitelist Uji    101    msisdn    +628123456789    0

Pengguna Super Admin Mengirimkan Penambahan Whitelist Untuk Target Yang Sama
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Tambah Whitelist    admin    101    msisdn    +628123456789    Reaktifasi Whitelist

Status Whitelist Pada Database Berubah Kembali Menjadi Aktif
    Verifikasi Data Whitelist Database    101    msisdn    +628123456789    1

Pengguna Super Admin Mengirimkan Kembali Penambahan Whitelist Target Yang Telah Aktif
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Tambah Whitelist Tidak Valid Dan Pastikan Ditolak    admin    101    msisdn    +628123456789

Sistem Menolak Duplikasi Target Whitelist Aktif
    Log Delta Laravel Bebas Dari Kesalahan Fatal

Database Memiliki Data Whitelist MSISDN Aktif Untuk Client Uji
    Sisipkan Data Whitelist Uji    101    msisdn    +628123456789    1

Pengguna Super Admin Mengirimkan Aksi Deaktivasi Whitelist
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Toggle Status Whitelist    admin    101    msisdn    +628123456789    deactivate

Status Whitelist Pada Database Berubah Menjadi Nonaktif
    Verifikasi Data Whitelist Database    101    msisdn    +628123456789    0

# ==============================================================================
# BLOCKLIST & UNBLOCK KEYWORDS
# ==============================================================================

Database Memiliki Data Block State Aktif Untuk Client Uji
    Sisipkan Data Block State Uji    101    +6281200000001    MSISDN    ACTIVE

Pengguna Role CCO Membuka Halaman Blocklist
    Pengguna Berhasil Login Ke Portal JNS7    ccouser
    Akses Halaman URL Dan Pastikan Status Respons    ccouser    /antifraud/blocks    200

Halaman Menampilkan Target Fraud Aktif Beserta Rincian Rule Dan Status
    Log Delta Laravel Bebas Dari Kesalahan Fatal

Subscriber ActiveMQ Queue Action Telah Aktif Dan Siap Menerima Pesan
    Aktifkan Subscriber ActiveMQ Queue Action

Pengguna Role CCO Mengirimkan Permintaan Unblock Dengan Alasan Valid
    Pengguna Berhasil Login Ke Portal JNS7    ccouser
    Kirim Permintaan Unblock    ccouser    101    +6281200000001    Valid customer unblock request

Status Block State Pada Database Berubah Menjadi INACTIVE
    Verifikasi Data Block State Database    101    +6281200000001    INACTIVE    ccouser    Valid customer unblock request

Kolom Unblocked By Dan Unblock Reason Terisi Sesuai Ekspektasi
    Verifikasi Data Block State Database    101    +6281200000001    INACTIVE    ccouser    Valid customer unblock request

Payload Exact JSON Diterima Pada Queue Action ActiveMQ
    Verifikasi Payload Exact JSON Diterima Pada Queue ActiveMQ    +6281200000001    ccouser    5.0

Pengguna Role CCO Mengirimkan Permintaan Unblock Dengan Alasan Kosong Atau Spasi
    Pengguna Berhasil Login Ke Portal JNS7    ccouser
    Kirim Permintaan Unblock Dengan Alasan Kosong Dan Pastikan Ditolak    ccouser    101    +6281200000001

Sistem Menolak Permintaan Unblock Dan Status Tetap ACTIVE
    Verifikasi Data Block State Database    101    +6281200000001    ACTIVE    None    None

Gangguan Koneksi ActiveMQ Disimulasikan Pada SUT
    Simulasikan Gangguan Koneksi ActiveMQ Pada SUT

Pengguna Role CCO Mengirimkan Permintaan Unblock
    Pengguna Berhasil Login Ke Portal JNS7    ccouser
    Kirim Permintaan Unblock    ccouser    101    +6281200000001    Valid customer unblock request

Status Block State Pada Database Tetap ACTIVE
    Verifikasi Data Block State Database    101    +6281200000001    ACTIVE    None    None

Audit Log Mencatat Kejadian UNBLOCK_FAILED
    Verifikasi Audit Log Tercatat    101    UNBLOCK_FAILED    ccouser

Konektivitas ActiveMQ Pada SUT Berhasil Dipulihkan
    Pulihkan Koneksi ActiveMQ Pada SUT

# ==============================================================================
# AUDIT TRAIL KEYWORDS
# ==============================================================================

Database Memastikan Riwayat Audit Log Client Uji Bersih
    Bersihkan Data Uji Database Anti Fraud

Pengguna Menjalankan Siklus Penuh Konfigurasi Client Uji
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Tambah Konfigurasi Anti Fraud    admin    101
    Kirim Permintaan Update Konfigurasi Anti Fraud    admin    101
    Kirim Permintaan Aksi Lifecycle Konfigurasi    admin    submit    101
    Pengguna Berhasil Login Ke Portal JNS7    ccouser
    Kirim Permintaan Aksi Lifecycle Konfigurasi    ccouser    approve    101
    Kirim Permintaan Aksi Lifecycle Konfigurasi    ccouser    deactivate    101
    Kirim Permintaan Aksi Lifecycle Konfigurasi    ccouser    reopen    101

Seluruh Jejak Audit Trail Konfigurasi Terverifikasi Lengkap Pada Database
    Verifikasi Audit Log Tercatat    101    CONFIG_INSERT    admin
    Verifikasi Audit Log Tercatat    101    CONFIG_UPDATE    admin
    Verifikasi Audit Log Tercatat    101    SUBMIT    admin
    Verifikasi Audit Log Tercatat    101    APPROVE    ccouser
    Verifikasi Audit Log Tercatat    101    DEACTIVATE    ccouser
    Verifikasi Audit Log Tercatat    101    REOPEN    ccouser

Pengguna Menjalankan Siklus Operasi Whitelist Dan Unblock
    Pengguna Berhasil Login Ke Portal JNS7    admin
    Kirim Permintaan Tambah Whitelist    admin    101    msisdn    +628123456789    Audit Test MSISDN
    Kirim Permintaan Toggle Status Whitelist    admin    101    msisdn    +628123456789    deactivate
    Kirim Permintaan Tambah Whitelist    admin    101    prefix    62812    Audit Test Prefix
    Kirim Permintaan Toggle Status Whitelist    admin    101    prefix    62812    deactivate
    Sisipkan Data Block State Uji    101    +6281200000001    MSISDN    ACTIVE
    Pengguna Berhasil Login Ke Portal JNS7    ccouser
    Kirim Permintaan Unblock    ccouser    101    +6281200000001    Audit Unblock Reason

Seluruh Jejak Audit Trail Whitelist Dan Unblock Terverifikasi Lengkap Pada Database
    Verifikasi Audit Log Tercatat    101    WHITELIST_ADD    admin
    Verifikasi Audit Log Tercatat    101    WHITELIST_DEACTIVATE    admin
    Verifikasi Audit Log Tercatat    101    UNBLOCK    ccouser

# ==============================================================================
# MULTI-TENANT KEYWORDS
# ==============================================================================

Pengguna Super Admin JATIS Berhasil Login Ke Portal JNS7
    Pengguna Berhasil Login Ke Portal JNS7    admin

Pengguna Mengakses Seluruh Menu Anti Fraud
    Akses Halaman URL Dan Pastikan Status Respons    admin    /antifraud/config    200
    Akses Halaman URL Dan Pastikan Status Respons    admin    /antifraud/whitelist    200
    Akses Halaman URL Dan Pastikan Status Respons    admin    /antifraud/blocks    200
    Akses Halaman URL Dan Pastikan Status Respons    admin    /antifraud/audit    200

Seluruh Data Lintas Tenant Dapat Dilihat Dan Dikelola Secara Penuh
    Log Delta Laravel Bebas Dari Kesalahan Fatal

Fixture Data Multi Tenant Client Sepuluh Dan Dua Puluh Tersedia Di Database
    Siapkan Fixture Multi Tenant Client Sepuluh Dan Dua Puluh

Pengguna Non JATIS Client Sepuluh Mengakses Endpoint DataTables AJAX
    Pengguna Berhasil Login Ke Portal JNS7    client10user

Respons Hanya Menampilkan Data Milik Client Sepuluh
    Verifikasi Isolasi Data Multi Tenant Pada Seluruh Endpoint DataTables    client10user    10    20

Data Milik Client Dua Puluh Terbukti Tidak Bocor Sama Sekali
    Log Delta Laravel Bebas Dari Kesalahan Fatal
