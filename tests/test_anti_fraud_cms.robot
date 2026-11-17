*** Settings ***
Documentation    Suite Pengujian Otomasi E2E & Backend Anti-Fraud CMS JNS7
...              Tiket: PB082643640012YA | SUT: MobileBroadcast JNS7
...              Menerapkan Clean BDD Murni, Zero False Positive & Transparent Logging
Resource         ../resources/keywords/anti_fraud_keywords.robot
Test Setup       Persiapkan Lingkungan Pengujian Anti Fraud
Test Teardown    Pulihkan Lingkungan Pengujian Anti Fraud

*** Test Cases ***
TC-001 Verifikasi Menu Anti Fraud Dan Empat Submenu Tampil Di Sidebar Portal JNS7
    [Tags]    P0    TC-001    cms    sidebar    rbac    happy_path
    Given Snapshot Log Delta Laravel SUT Dicatat
    When Pengguna Menjalankan Browser E2E Journey Verifikasi Menu Dan Sidebar Spotlight
    Then Seluruh Endpoint Submenu Anti Fraud Mengembalikan Status HTTP 200 OK
    And Log Delta Laravel Bebas Dari Kesalahan Fatal

TC-002 Validasi Penolakan Akses Ke Rute Anti Fraud Bagi Akun Tanpa Permission
    [Tags]    P1    TC-002    cms    security    rbac    negative
    Given Snapshot Log Delta Laravel SUT Dicatat
    And Pengguna Non Authorized Berhasil Login Ke Portal JNS7
    When Pengguna Non Authorized Mengakses Halaman Client Config Langsung
    Then Sistem Mengalihkan Akses Menuju Halaman Awal
    And Permintaan AJAX Search Client Mengembalikan Status 403 Forbidden
    And Log Delta Laravel Bebas Dari Kesalahan Fatal

TC-003 Tambah Konfigurasi Anti Fraud Client Baru Dengan Status Awal DRAFT
    [Tags]    P0    TC-003    cms    config    lifecycle    happy_path
    Given Database Memastikan Client Uji Belum Memiliki Konfigurasi Anti Fraud
    When Pengguna Super Admin Mengirimkan Permintaan Penambahan Konfigurasi Baru
    Then Data Konfigurasi Client Pada Database Tersimpan Dengan Status DRAFT
    And Seluruh Kolom Parameter Rule Sesuai Sempurna Dengan Payload
    And Audit Log CONFIG_INSERT Tercatat Pada Database

TC-004 Validasi Penolakan Penambahan Konfigurasi Duplikat Untuk Client Yang Sama
    [Tags]    P1    TC-004    cms    config    validation    negative
    Given Database Memiliki Konfigurasi Anti Fraud Aktif Untuk Client Uji
    When Pengguna Super Admin Mengirimkan Permintaan Penambahan Konfigurasi Duplikat
    Then Sistem Menolak Permintaan Duplikasi Dengan Pesan Kesalahan Valid

TC-005 Validasi Penolakan Nilai Parameter Threshold Warn Dan Crit Tidak Valid
    [Tags]    P1    TC-005    cms    config    validation    negative
    Given Database Memastikan Client Uji Belum Memiliki Konfigurasi Anti Fraud
    When Pengguna Super Admin Mengirimkan Form Konfigurasi Dengan Nilai Threshold Tidak Valid
    Then Sistem Menolak Penyimpanan Konfigurasi Serta Menampilkan Validasi Error

TC-006 Edit Konfigurasi Berstatus DRAFT Dan Verifikasi Snapshot Kolom Tidak Berubah
    [Tags]    P1    TC-006    cms    config    snapshot    regression
    Given Database Memiliki Konfigurasi Anti Fraud Berstatus DRAFT Untuk Client Uji
    And Snapshot Baseline Konfigurasi Client Telah Disimpan
    When Pengguna Super Admin Mengirimkan Permintaan Pembaruan Parameter Konfigurasi
    Then Parameter Konfigurasi Yang Diperbarui Terbukti Berubah Sesuai Ekspektasi
    And Seluruh Kolom Konfigurasi Lainnya Terbukti Tidak Berubah Dari Baseline

TC-007 Edit Konfigurasi APPROVED Mengakibatkan Status Kembali Ke DRAFT Dan Reset Approver
    [Tags]    P0    TC-007    cms    config    lifecycle    regression
    Given Database Memiliki Konfigurasi Anti Fraud Berstatus APPROVED Dengan Approved By Terisi
    And Snapshot Baseline Konfigurasi Client Telah Disimpan
    When Pengguna Super Admin Mengirimkan Permintaan Pembaruan Parameter Konfigurasi
    Then Status Konfigurasi Otomatis Kembali Menjadi DRAFT
    And Kolom Approved By Direset Menjadi Null

TC-008 Submit Konfigurasi DRAFT Menjadi PENDING_APPROVAL Dan Buktikan Nol Reload ActiveMQ
    [Tags]    P0    TC-008    cms    config    activemq    negative
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    And Database Memiliki Konfigurasi Anti Fraud Berstatus DRAFT Untuk Client Uji
    When Pengguna Super Admin Mengirimkan Aksi Submit Konfigurasi
    Then Status Konfigurasi Pada Database Berubah Menjadi PENDING_APPROVAL
    And Ketiadaan Sinyal Reload Pada ActiveMQ Topic Terbukti Selama Rentang Waktu Pengamatan

TC-009 Verifikasi Restriksi Hak Akses Approval Bagi Pengguna Non CCO
    [Tags]    P0    TC-009    cms    security    rbac    negative
    Given Pengguna Super Admin Non CCO Berhasil Login Ke Portal JNS7
    And Database Memiliki Konfigurasi Berstatus PENDING_APPROVAL Untuk Client Uji
    When Pengguna Non CCO Mengirimkan Permintaan Langsung Ke Endpoint Approve Dan Reject
    Then Sistem Menolak Permintaan Dengan Pesan Khusus Role CCO

TC-010 CCO Menyetujui Konfigurasi PENDING_APPROVAL Menjadi APPROVED
    [Tags]    P0    TC-010    cms    config    approval    activemq    happy_path
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    And Database Memiliki Konfigurasi Berstatus PENDING_APPROVAL Untuk Client Uji
    When Pengguna Role CCO Mengirimkan Aksi Persetujuan Konfigurasi
    Then Status Konfigurasi Pada Database Berubah Menjadi APPROVED
    And Kolom Approved By Terisi Nama Pengguna CCO
    And Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ

TC-011 CCO Menolak Konfigurasi PENDING_APPROVAL Menjadi REJECTED
    [Tags]    P1    TC-011    cms    config    approval    activemq
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    And Database Memiliki Konfigurasi Berstatus PENDING_APPROVAL Untuk Client Uji
    When Pengguna Role CCO Mengirimkan Aksi Penolakan Konfigurasi
    Then Status Konfigurasi Pada Database Berubah Menjadi REJECTED
    And Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ

TC-012 Reopen Konfigurasi Berstatus REJECTED Kembali Menjadi PENDING_APPROVAL
    [Tags]    P1    TC-012    cms    config    lifecycle    reopen
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    And Database Memiliki Konfigurasi Berstatus REJECTED Untuk Client Uji
    When Pengguna Super Admin Mengirimkan Aksi Reopen Konfigurasi
    Then Status Konfigurasi Pada Database Berubah Menjadi PENDING_APPROVAL
    And Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ

TC-013 CCO Menonaktifkan Konfigurasi APPROVED Menjadi INACTIVE
    [Tags]    P1    TC-013    cms    config    lifecycle    deactivate
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    And Database Memiliki Konfigurasi Berstatus APPROVED Untuk Client Uji
    When Pengguna Role CCO Mengirimkan Aksi Deaktivasi Konfigurasi
    Then Status Konfigurasi Pada Database Berubah Menjadi INACTIVE
    And Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ

TC-014 Reopen Konfigurasi Berstatus INACTIVE Kembali Menjadi PENDING_APPROVAL
    [Tags]    P1    TC-014    cms    config    lifecycle    reopen
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    And Database Memiliki Konfigurasi Berstatus INACTIVE Untuk Client Uji
    When Pengguna Super Admin Mengirimkan Aksi Reopen Konfigurasi
    Then Status Konfigurasi Pada Database Berubah Menjadi PENDING_APPROVAL
    And Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ

TC-015 Validasi Penolakan Transisi Status Ilegal Pada State Machine Konfigurasi
    [Tags]    P1    TC-015    cms    config    state_machine    negative
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    And Database Memiliki Konfigurasi Anti Fraud Berstatus DRAFT Untuk Client Uji
    And Snapshot Baseline Konfigurasi Client Telah Disimpan
    When Pengguna Super Admin Mengirimkan Aksi Transisi Ilegal Ke Approved
    Then Sistem Menolak Transisi Status Ilegal Tersebut
    And Seluruh Kolom Konfigurasi Baseline Terbukti Tidak Mengalami Perubahan
    And Ketiadaan Sinyal Reload Pada ActiveMQ Topic Terbukti Selama Rentang Waktu Pengamatan

TC-016 Eksekusi Tombol SYNC Menyiarkan Sinyal Reload Anti Fraud Ke ActiveMQ Topic
    [Tags]    P0    TC-016    cms    activemq    sync    happy_path
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    When Pengguna Super Admin Mengeksekusi Tombol SYNC Konfigurasi
    Then Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ
    And Audit Log SYNC_CONFIG Tercatat Pada Database

TC-017 Pengujian Independen Transisi Siklus Approval Memicu Pesan Reload Ke ActiveMQ Topic
    [Tags]    P0    TC-017    cms    approval    activemq    exclusive
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    And Database Memiliki Konfigurasi Berstatus PENDING_APPROVAL Untuk Client Uji
    When Pengguna Role CCO Menjalankan Transisi Siklus Approval Pada Lingkungan Eksklusif
    Then Sinyal Reload Anti Fraud Diterima Tepat Satu Kali Pada Topic ActiveMQ

TC-018 Tambah Whitelist MSISDN Berhasil Disimpan Dan Menyiarkan Reload ActiveMQ
    [Tags]    P0    TC-018    cms    whitelist    msisdn    activemq    happy_path
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    When Pengguna Super Admin Mengirimkan Permintaan Penambahan Whitelist MSISDN
    Then Data Whitelist MSISDN Tersimpan Pada Database Dengan Status Aktif
    And Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ

TC-019 Tambah Whitelist Prefix Berhasil Disimpan Dan Menyiarkan Reload ActiveMQ
    [Tags]    P0    TC-019    cms    whitelist    prefix    activemq    happy_path
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    When Pengguna Super Admin Mengirimkan Permintaan Penambahan Whitelist Prefix
    Then Data Whitelist Prefix Tersimpan Pada Database Dengan Status Aktif
    And Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ

TC-020 Validasi Penolakan Format MSISDN Dan Prefix Tidak Sesuai Aturan
    [Tags]    P1    TC-020    cms    whitelist    validation    negative
    Given Database Memastikan Data Uji Whitelist Bersih
    When Pengguna Super Admin Mengirimkan Penambahan Whitelist Dengan Format Tidak Sesuai Aturan
    Then Sistem Menolak Penambahan Whitelist Tersebut Dengan Pesan Validasi

TC-021 Validasi Penolakan Duplikasi Target Aktif Dan Reaktivasi Target Nonaktif
    [Tags]    P1    TC-021    cms    whitelist    reactivation    regression
    Given Database Memiliki Data Whitelist Nonaktif Untuk Client Uji
    When Pengguna Super Admin Mengirimkan Penambahan Whitelist Untuk Target Yang Sama
    Then Status Whitelist Pada Database Berubah Kembali Menjadi Aktif
    When Pengguna Super Admin Mengirimkan Kembali Penambahan Whitelist Target Yang Telah Aktif
    Then Sistem Menolak Duplikasi Target Whitelist Aktif

TC-022 Deaktivasi Dan Reaktivasi Entri Whitelist Serta Verifikasi Reload ActiveMQ
    [Tags]    P1    TC-022    cms    whitelist    toggle    activemq
    Given Subscriber ActiveMQ Topic Command Telah Aktif Dan Siap Menerima Pesan
    And Database Memiliki Data Whitelist MSISDN Aktif Untuk Client Uji
    When Pengguna Super Admin Mengirimkan Aksi Deaktivasi Whitelist
    Then Status Whitelist Pada Database Berubah Menjadi Nonaktif
    And Sinyal Reload Anti Fraud Diterima Pada Topic ActiveMQ

TC-023 Verifikasi Tampilan Daftar Blocklist Aktif Beserta Rincian Rule Fraud
    [Tags]    P0    TC-023    cms    blocklist    monitoring    happy_path
    Given Database Memiliki Data Block State Aktif Untuk Client Uji
    When Pengguna Role CCO Membuka Halaman Blocklist
    Then Halaman Menampilkan Target Fraud Aktif Beserta Rincian Rule Dan Status

TC-024 CCO Melakukan Unblock Target Aktif Dan Verifikasi Exact JSON Pada ActiveMQ Queue
    [Tags]    P0    TC-024    cms    blocklist    unblock    activemq    happy_path
    Given Subscriber ActiveMQ Queue Action Telah Aktif Dan Siap Menerima Pesan
    And Database Memiliki Data Block State Aktif Untuk Client Uji
    When Pengguna Role CCO Mengirimkan Permintaan Unblock Dengan Alasan Valid
    Then Status Block State Pada Database Berubah Menjadi INACTIVE
    And Kolom Unblocked By Dan Unblock Reason Terisi Sesuai Ekspektasi
    And Payload Exact JSON Diterima Pada Queue Action ActiveMQ

TC-025 Validasi Penolakan Aksi Unblock Tanpa Alasan Atau Hanya Spasi
    [Tags]    P1    TC-025    cms    blocklist    validation    negative
    Given Database Memiliki Data Block State Aktif Untuk Client Uji
    When Pengguna Role CCO Mengirimkan Permintaan Unblock Dengan Alasan Kosong Atau Spasi
    Then Sistem Menolak Permintaan Unblock Dan Status Tetap ACTIVE

TC-026 Verifikasi Fail Safe Di Mana Update Database Dilewati Dan Dicatat UNBLOCK_FAILED
    [Tags]    P0    TC-026    cms    blocklist    fail_safe    activemq    resilience
    Given Database Memiliki Data Block State Aktif Untuk Client Uji
    And Gangguan Koneksi ActiveMQ Disimulasikan Pada SUT
    When Pengguna Role CCO Mengirimkan Permintaan Unblock
    Then Status Block State Pada Database Tetap ACTIVE
    And Audit Log Mencatat Kejadian UNBLOCK_FAILED
    And Konektivitas ActiveMQ Pada SUT Berhasil Dipulihkan

TC-027 Verifikasi Jejak Audit Trail Lengkap Untuk Seluruh Siklus Operasi Konfigurasi
    [Tags]    P1    TC-027    cms    audit    config    compliance
    Given Database Memastikan Riwayat Audit Log Client Uji Bersih
    When Pengguna Menjalankan Siklus Penuh Konfigurasi Client Uji
    Then Seluruh Jejak Audit Trail Konfigurasi Terverifikasi Lengkap Pada Database

TC-028 Verifikasi Jejak Audit Trail Lengkap Untuk Operasi Whitelist Dan Unblock
    [Tags]    P1    TC-028    cms    audit    whitelist    unblock    compliance
    Given Database Memastikan Riwayat Audit Log Client Uji Bersih
    When Pengguna Menjalankan Siklus Operasi Whitelist Dan Unblock
    Then Seluruh Jejak Audit Trail Whitelist Dan Unblock Terverifikasi Lengkap Pada Database

TC-029 Verifikasi Hak Akses Menyeluruh Multi Tenant Bagi Pengguna Super Tenant JATIS
    [Tags]    P0    TC-029    cms    multitenant    super_tenant    rbac
    Given Pengguna Super Admin JATIS Berhasil Login Ke Portal JNS7
    When Pengguna Mengakses Seluruh Menu Anti Fraud
    Then Seluruh Data Lintas Tenant Dapat Dilihat Dan Dikelola Secara Penuh

TC-030 Verifikasi Isolasi Data Pengguna Non JATIS Pada Seluruh Endpoint DataTables AJAX
    [Tags]    P0    TC-030    cms    multitenant    isolation    security
    Given Fixture Data Multi Tenant Client Sepuluh Dan Dua Puluh Tersedia Di Database
    When Pengguna Non JATIS Client Sepuluh Mengakses Endpoint DataTables AJAX
    Then Respons Hanya Menampilkan Data Milik Client Sepuluh
    And Data Milik Client Dua Puluh Terbukti Tidak Bocor Sama Sekali
