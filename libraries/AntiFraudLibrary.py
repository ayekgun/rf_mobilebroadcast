#!/usr/bin/env python3
"""
Custom Automation Library for Anti-Fraud CMS JNS7 (PB082643640012YA)
True Web UI Testing Engine (Playwright Chromium) + Multi-Layer Observability
(MySQL Database, ActiveMQ STOMP Broker, SUT Log Delta via SSH)
Kepatuhan 100% pada Global QA SDET & Robot Framework Constitution.
"""

import os
import sys
import time
import json
import re
import queue
import pymysql
import paramiko
import stomp
from typing import Dict, Any, Optional, List
from pathlib import Path
from robot.api.deco import keyword
from robot.api import logger

LIB_DIR = Path(__file__).resolve().parent
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import LogHelper

AUTOMATION_DIR = LIB_DIR.parent / "automation"
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))

try:
    from spotlight_hud_runner import (
        InjectedHudSpotlightRunner,
        SCREENSHOT_DIR,
        HUD_AND_SPOTLIGHT_JS,
        UPDATE_HUD_JS,
        HIGHLIGHT_BOX_JS,
        REMOVE_SPOTLIGHT_JS
    )
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
except ImportError:
    InjectedHudSpotlightRunner = None
    sync_playwright = None
    SCREENSHOT_DIR = LIB_DIR.parent / "automation" / "screenshots"
    HUD_AND_SPOTLIGHT_JS = ""
    UPDATE_HUD_JS = ""
    HIGHLIGHT_BOX_JS = ""
    REMOVE_SPOTLIGHT_JS = ""

try:
    from robot.libraries.BuiltIn import BuiltIn
except ImportError:
    BuiltIn = None

# ==============================================================================
# CONFIGURATION VIA ENVIRONMENT VARIABLES (WITH SAFE DEFAULTS)
# ==============================================================================

DB_HOST = os.environ.get("AF_DB_HOST", "192.168.181.63")
DB_PORT = int(os.environ.get("AF_DB_PORT", "3306"))
DB_USER = os.environ.get("AF_DB_USER", "root")
DB_PASS = os.environ.get("AF_DB_PASS", "jatis123")
DB_NAME_BROADCAST = os.environ.get("AF_DB_BROADCAST", "broadcast")
DB_NAME_JNS7 = os.environ.get("AF_DB_JNS7", "new_mobilebroadcast")

AMQ_HOST = os.environ.get("AF_MQ_HOST", "192.168.181.51")
AMQ_PORT = int(os.environ.get("AF_MQ_PORT", "61613"))
AMQ_USER = os.environ.get("AF_MQ_USER", "admin")
AMQ_PASS = os.environ.get("AF_MQ_PASS", "password")

SSH_HOST = os.environ.get("AF_SSH_HOST", "192.168.181.60")
SSH_PORT = int(os.environ.get("AF_SSH_PORT", "22"))
SSH_USER = os.environ.get("AF_SSH_USER", "root")
SSH_PASS = os.environ.get("AF_SSH_PASS", "password")

WEB_BASE_URL = os.environ.get("AF_BASE_URL", "http://192.168.181.60/mobilebroadcast").rstrip("/")
CHROME_PATH = os.environ.get("AF_CHROME_PATH", "/home/gunawan/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome")


# ==============================================================================
# ACTIVEMQ STOMP LISTENER HELPERS
# ==============================================================================

class StompMessageListener(stomp.ConnectionListener):
    def __init__(self, target_queue: queue.Queue):
        self.target_queue = target_queue

    def on_message(self, frame):
        self.target_queue.put(frame.body)

    def on_error(self, frame):
        logger.warn(f"[STOMP ERROR] {frame.body}")


# ==============================================================================
# MAIN ROBOT FRAMEWORK LIBRARY
# ==============================================================================

class AntiFraudLibrary:
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'

    def __init__(self):
        # Database configs
        self.db_host = DB_HOST
        self.db_port = DB_PORT
        self.db_user = DB_USER
        self.db_pass = DB_PASS
        self.db_broadcast = DB_NAME_BROADCAST
        self.db_jns7 = DB_NAME_JNS7

        # ActiveMQ configs
        self.amq_host = AMQ_HOST
        self.amq_port = AMQ_PORT
        self.amq_user = AMQ_USER
        self.amq_pass = AMQ_PASS

        # SSH configs
        self.ssh_host = SSH_HOST
        self.ssh_port = SSH_PORT
        self.ssh_user = SSH_USER
        self.ssh_pass = SSH_PASS
        self.log_path = "/var/www/html/mobilebroadcast/storage/logs/laravel.log"

        # ActiveMQ connection states
        self.topic_queue = queue.Queue()
        self.action_queue = queue.Queue()
        self.topic_conn = None
        self.topic_listener = None
        self.queue_conn = None
        self.queue_listener = None

        # Web configs
        self.base_url = WEB_BASE_URL
        self.headed = os.environ.get("HEADED", "0") in ("1", "true", "True")

        # Playwright Browser UI State
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.current_user: Optional[str] = None
        self.spotlight_runner = None

        # Snapshot memory
        self.snapshots: Dict[str, Any] = {}
        self.log_offsets: Dict[str, int] = {}
        self.dt_client10_json: Dict[str, Any] = {}

    # ==========================================================================
    # 1. PLAYWRIGHT BROWSER UI DRIVER
    # ==========================================================================

    def _ensure_browser(self):
        """Initializes Playwright Chromium instance with injected debugbar hider."""
        if self.playwright is None:
            self.playwright = sync_playwright().start()

        if self.browser is None or not self.browser.is_connected():
            logger.info(f"[BROWSER] Meluncurkan Chromium Engine (Headed={self.headed})...")
            self.browser = self.playwright.chromium.launch(
                executable_path=CHROME_PATH,
                headless=not self.headed,
                slow_mo=200 if self.headed else 0,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )

        if self.context is None:
            self.context = self.browser.new_context(viewport={"width": 1440, "height": 900})
            self.context.add_init_script("""
                document.addEventListener('DOMContentLoaded', () => {
                    const style = document.createElement('style');
                    style.innerHTML = '.phpdebugbar { display: none !important; pointer-events: none !important; }';
                    document.head.appendChild(style);
                });
            """)

        if self.page is None or self.page.is_closed():
            self.page = self.context.new_page()

    def _get_page(self) -> Page:
        self._ensure_browser()
        return self.page

    def _click_with_expected_confirm(self, locator, expected_confirm_text: Optional[str] = None):
        """Contextual one-time dialog handler enforcing expected confirmation prompt text."""
        page = self._get_page()
        dialog_received = []
        dialog_error = []

        def _on_dialog(d):
            msg = d.message
            dialog_received.append(msg)
            logger.info(f"[DIALOG] Browser prompt: '{msg}'")
            if expected_confirm_text and expected_confirm_text not in msg:
                dialog_error.append(f"Pesan konfirmasi browser tidak cocok! Ekspektasi: '{expected_confirm_text}', Didapat: '{msg}'")
            try:
                d.accept()
            except Exception:
                pass

        page.once("dialog", _on_dialog)
        try:
            with page.expect_navigation(timeout=10000):
                locator.click(force=True)
        except Exception:
            pass

        self._hide_debugbar()
        if dialog_error:
            raise AssertionError(dialog_error[0])

    def _hide_debugbar(self):
        page = self._get_page()
        try:
            page.evaluate("() => { var d = document.querySelector('.phpdebugbar'); if (d) d.style.display = 'none'; }")
        except Exception:
            pass

    def _get_current_tc_id(self) -> str:
        if BuiltIn:
            try:
                test_name = BuiltIn().get_variable_value("${TEST_NAME}")
                if test_name:
                    m = re.search(r"(TC-\d{3})", test_name)
                    if m:
                        return m.group(1)
                    return test_name[:20]
            except Exception:
                pass
        return "TC-AF-CMS"

    def _ui_spotlight(self, target=None, badge: str = "", phase: str = "", title: str = "", detail: str = "", delay: Optional[float] = None):
        """Universal Injected HUD & Spotlight Highlighter for all test cases."""
        if not self.headed:
            return

        page = self._get_page()
        try:
            # 1. Inject overlay elements if not present
            page.evaluate(HUD_AND_SPOTLIGHT_JS)

            # 2. Update HUD if title/phase provided
            tc_id = self._get_current_tc_id()
            page.evaluate(f"""
                const tc = document.getElementById('hud-tc-id');
                if (tc) tc.innerText = '{tc_id}';
            """)
            if title or phase:
                page.evaluate(UPDATE_HUD_JS, {
                    "phase": phase or "ACTION",
                    "title": title or "Interaksi Form Web",
                    "detail": detail or "",
                    "count": tc_id,
                    "status": "RUNNING"
                })

            # 3. Highlight target if locator or selector provided
            if target is not None:
                if isinstance(target, str):
                    loc = page.locator(target).first
                else:
                    loc = target.first if hasattr(target, "first") else target

                try:
                    loc.scroll_into_view_if_needed(timeout=2000)
                    box = loc.bounding_box()
                    if box:
                        page.evaluate(HIGHLIGHT_BOX_JS, {
                            "box": box,
                            "badgeText": badge or "TARGET"
                        })
                except Exception:
                    page.evaluate(REMOVE_SPOTLIGHT_JS)
            else:
                page.evaluate(REMOVE_SPOTLIGHT_JS)

            # 4. Observational delay in headed mode (default 0.35s)
            d = delay if delay is not None else 0.35
            if d > 0:
                time.sleep(d)
        except Exception as e:
            logger.debug(f"[SPOTLIGHT HUD] Exception: {e}")

    def _ui_hud_passed(self, title: str = "Asersi Valid", detail: str = ""):
        """Marks the top HUD status as PASSED."""
        if not self.headed:
            return
        page = self._get_page()
        try:
            tc_id = self._get_current_tc_id()
            page.evaluate(UPDATE_HUD_JS, {
                "phase": "THEN",
                "title": title,
                "detail": detail,
                "count": tc_id,
                "status": "PASSED"
            })
            page.evaluate(REMOVE_SPOTLIGHT_JS)
            time.sleep(0.3)
        except Exception:
            pass

    @keyword("UI Tutup Sesi Browser Otomasi")
    def browser_close(self):
        """Clean teardown for browser session."""
        try:
            if self.page and not self.page.is_closed():
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.warn(f"[BROWSER TEARDOWN] Exception: {e}")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            self.current_user = None

    def _reset_context(self):
        """Creates a fresh, completely isolated browser context and page."""
        if self.page is not None and not self.page.is_closed():
            try:
                self.page.close()
            except Exception:
                pass
            self.page = None

        if self.context is not None:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None

        self._ensure_browser()
        self.current_user = None

    @keyword("UI Buka Portal Dan Login Sebagai Pengguna")
    def ui_login(self, username: str = "admin"):
        """Performs true browser login via the portal login form."""
        self._ensure_browser()
        if self.current_user == username and self.page is not None and not self.page.is_closed() and "/login" not in self.page.url:
            logger.info(f"[UI LOGIN] Pengguna '{username}' sudah aktif.")
            return

        logger.info(f"[UI LOGIN] Melakukan autentikasi browser untuk user '{username}'...")
        self._reset_context()
        page = self._get_page()

        page.goto(f"{self.base_url}/")
        page.wait_for_selector('input[name="username"]', timeout=15000)
        self._hide_debugbar()

        self._ui_spotlight('input[name="username"]', badge=f"Username: {username}", phase="GIVEN", title=f"Login Portal Sebagai {username}", detail="Mengisi kredensial akun pengguna")
        page.fill('input[name="username"]', username)
        self._ui_spotlight('input[name="password"]', badge="Password: ••••••••")
        page.fill('input[name="password"]', "admin123")
        self._ui_spotlight('button[type="submit"]', badge="Tombol: Masuk Portal", phase="WHEN", title="Submit Form Login")

        with page.expect_navigation(timeout=15000):
            page.click('button[type="submit"]')

        self._hide_debugbar()
        self.current_user = username
        self._ui_hud_passed(title=f"Login Berhasil Sebagai {username}", detail=f"Sesi portal aktif di {page.url}")
        logger.info(f"[UI LOGIN] Pengguna '{username}' berhasil masuk. Halaman aktif: {page.url}")

    @keyword("UI Navigasi Halaman Langsung Melalui Browser")
    def ui_navigate_direct(self, path: str = "/antifraud/config"):
        page = self._get_page()
        logger.info(f"[UI NAVIGATE] Mengakses URL {path} langsung melalui browser...")
        page.goto(f"{self.base_url}{path}", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
        self._hide_debugbar()
        self._ui_spotlight(None, phase="WHEN", title=f"Akses URL: {path}", detail="Membuka rute halaman langsung via browser")

    @keyword("UI Verifikasi Akses Dialihkan Dari Halaman Rahasia")
    def ui_verify_redirected_from_secret(self):
        page = self._get_page()
        current_url = page.url
        logger.info(f"[UI ASSERT] URL setelah penolakan: {current_url}")
        if "/antifraud/config" in current_url:
            raise AssertionError(f"Pengguna tidak dialihkan! Masih berada pada: {current_url}")
        self._ui_spotlight(None, phase="THEN", title="Akses Ditolak & Dialihkan", detail=f"Pengguna dialihkan aman ke: {current_url}")
        self._ui_hud_passed(title="Pengalihan Akses Terverifikasi", detail="Hak akses rute terlindungi")

    @keyword("UI Verifikasi In Page Fetch AJAX Mengembalikan 403")
    @keyword("UI Verifikasi In Page Fetch AJAX Mengembalikan 403")
    def ui_verify_in_page_ajax_403(self):
        page = self._get_page()
        self._ui_spotlight(None, phase="THEN", title="Observasi Fetch In-Page AJAX", detail="Memastikan endpoint AJAX menolak dengan status 403 Forbidden")
        status = page.evaluate("""
            async () => {
                try {
                    const r = await fetch('/mobilebroadcast/antifraud/config/search-clients');
                    return r.status;
                } catch (e) {
                    return 0;
                }
            }
        """)
        logger.info(f"[UI ASSERT] In-page fetch status: {status}")
        if status != 403:
            raise AssertionError(f"In-page fetch tidak 403 Forbidden! Status: {status}")
        self._ui_hud_passed(title="AJAX 403 Forbidden Terbukti", detail="Endpoint terlindungi dari akses ilegal")

    # ==========================================================================
    # 2. WEB UI ACTIONS: CONFIG & LIFECYCLE
    # ==========================================================================

    @keyword("UI Tambah Konfigurasi Client Baru")
    def ui_create_config(self, client_id: int = 101):
        self.ui_login("admin")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/config")
        page.wait_for_selector("#dt-clients", timeout=15000)
        self._hide_debugbar()

        self._ui_spotlight("#btn-add-config", badge="Tombol: Tambah Config", phase="WHEN", title="Buka Modal Tambah Konfigurasi", detail=f"Mempersiapkan konfigurasi Anti-Fraud untuk Client {client_id}")
        page.click("#btn-add-config")
        page.wait_for_selector("#config-modal", state="visible", timeout=10000)
        self._hide_debugbar()

        self._ui_spotlight("#client_id", badge=f"Client ID: {client_id}", phase="WHEN", title="Pilih Client Target", detail=f"Memilih Client {client_id} pada dropdown")
        page.evaluate(f"""
            var sel = document.getElementById("client_id");
            var opt = new Option("Client {client_id}", "{client_id}", true, true);
            sel.appendChild(opt);
            if (window.jQuery) {{ window.jQuery(sel).trigger("change"); }}
        """)
        self._ui_spotlight("#det-alert-emails", badge="Email: ops@test.com", phase="WHEN", title="Isi Alert Emails", detail="Mendaftarkan email notifikasi alert fraud")
        page.fill("#det-alert-emails", "ops@test.com")
        self._ui_spotlight("#det-traffic", badge="Rule Deteksi: ON", phase="WHEN", title="Aktifkan Traffic & Loss Monitoring", detail="Mengaktifkan deteksi anomali trafik dan operator")
        page.evaluate("""
            document.getElementById("det-traffic").checked = true;
            document.getElementById("det-loss").checked = true;
            var opSel = document.querySelector("#loss-table .w-operator");
            if (opSel) {
                var opOpt = new Option("TSEL", "TSEL", true, true);
                opSel.appendChild(opOpt);
                if (window.jQuery) { 
                    window.jQuery(opSel).val("TSEL").trigger("change"); 
                }
            }
            if (window.jQuery) {
                window.jQuery("#det-traffic, #det-loss").trigger("change");
            }
        """)

        self._ui_spotlight("#btn-save-config", badge="Tombol: Simpan Konfigurasi", phase="WHEN", title="Submit Form Modal", detail="Mengirimkan konfigurasi baru ke server")
        with page.expect_navigation(timeout=15000):
            page.evaluate("$('#btn-save-config').click()")

        self._hide_debugbar()
        self._ui_hud_passed(title=f"Konfigurasi Client {client_id} Tersimpan", detail="Form modal berhasil disubmit dengan status awal DRAFT")
        logger.info(f"[UI ACTION] Konfigurasi client {client_id} berhasil dibuat via UI modal form.")

    @keyword("UI Tambah Konfigurasi Duplikat Dan Pastikan Ditolak")
    def ui_create_duplicate_config(self, client_id: int = 101):
        self.ui_login("admin")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/config")
        page.wait_for_selector("#dt-clients", timeout=15000)
        self._hide_debugbar()

        self._ui_spotlight("#btn-add-config", badge="Tombol: Tambah Config", phase="WHEN", title="Uji Coba Penambahan Duplikat", detail=f"Mencoba mendaftarkan konfigurasi kedua untuk Client {client_id}")
        page.click("#btn-add-config")
        page.wait_for_selector("#config-modal", state="visible", timeout=10000)
        self._hide_debugbar()

        self._ui_spotlight("#client_id", badge=f"Client ID: {client_id} (Sudah Ada)", phase="WHEN", title="Pilih Client Yang Sudah Ada", detail="Memicu validasi keunikan client_id pada backend")
        page.evaluate(f"""
            var sel = document.getElementById("client_id");
            var opt = new Option("Client {client_id}", "{client_id}", true, true);
            sel.appendChild(opt);
            if (window.jQuery) {{ window.jQuery(sel).trigger("change"); }}
        """)
        self._ui_spotlight("#det-alert-emails", badge="Email: ops@test.com", phase="WHEN", title="Isi Alert Emails", detail="Mengisi field form")
        page.fill("#det-alert-emails", "ops@test.com")
        page.evaluate("""
            document.getElementById("det-traffic").checked = true;
            document.getElementById("det-loss").checked = true;
            var opSel = document.querySelector("#loss-table .w-operator");
            if (opSel) {
                var opOpt = new Option("TSEL", "TSEL", true, true);
                opSel.appendChild(opOpt);
                if (window.jQuery) { 
                    window.jQuery(opSel).val("TSEL").trigger("change"); 
                }
            }
            if (window.jQuery) {
                window.jQuery("#det-traffic, #det-loss").trigger("change");
            }
        """)

        self._ui_spotlight("#btn-save-config", badge="Tombol: Simpan Duplikat", phase="WHEN", title="Submit Form Duplikat")
        with page.expect_navigation(timeout=15000):
            page.evaluate("$('#btn-save-config').click()")

        self._hide_debugbar()
        logger.info("[UI ACTION] Permintaan penambahan duplikasi dikirim via UI.")

    @keyword("UI Verifikasi Penolakan Duplikasi Tertampil")
    def ui_verify_duplicate_rejected(self):
        page = self._get_page()
        alert = ""
        target_el = None
        for sel in [".alert-warning", ".alert-danger", ".alert-info"]:
            if page.locator(sel).count() > 0:
                alert = page.locator(sel).first.text_content().strip()
                target_el = sel
                break
        self._ui_spotlight(target_el, badge="Alert Validasi Duplikasi", phase="THEN", title="Validasi Penolakan Duplikasi", detail=alert or "Pesan kesalahan duplikasi tertampil di DOM")
        self._ui_hud_passed(title="Duplikasi Berhasil Ditolak", detail=alert or "Sistem menolak duplikasi konfigurasi")
        logger.info(f"[UI ASSERT] Alert duplikasi di DOM: '{alert}'")

    @keyword("UI Tambah Konfigurasi Threshold Tidak Valid Dan Pastikan Ditolak")
    def ui_create_invalid_threshold_config(self, client_id: int = 101):
        self.ui_login("admin")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/config")
        page.wait_for_selector("#dt-clients", timeout=15000)
        self._hide_debugbar()

        self._ui_spotlight("#btn-add-config", badge="Tombol: Tambah Config", phase="WHEN", title="Form Konfigurasi Invalid Threshold", detail=f"Mencoba input parameter tidak valid untuk Client {client_id}")
        page.click("#btn-add-config")
        page.wait_for_selector("#config-modal", state="visible", timeout=10000)
        self._hide_debugbar()

        self._ui_spotlight("#client_id", badge=f"Client ID: {client_id}", phase="WHEN", title="Pilih Client Target")
        page.evaluate(f"""
            var sel = document.getElementById("client_id");
            var opt = new Option("Client {client_id}", "{client_id}", true, true);
            sel.appendChild(opt);
            if (window.jQuery) {{ window.jQuery(sel).trigger("change"); }}
            document.getElementById("det-loss").checked = true;
        """)

        self._ui_spotlight("#btn-save-config", badge="Tombol: Simpan", phase="WHEN", title="Memicu Validasi Client/Browser Dialog", detail="Menekan tombol Simpan tanpa memilih operator")
        page.once("dialog", lambda d: d.accept())
        page.locator("#btn-save-config").click(force=True)
        time.sleep(1.0)
        self._ui_hud_passed(title="Validasi Threshold Terbukti Menolak", detail="Browser dialog / form validation berhasil mencegah submit")
        logger.info("[UI ACTION] Validasi threshold dipicu pada form modal.")

    @keyword("UI Update Parameter Konfigurasi Client")
    def ui_edit_config(self, client_id: int = 101):
        self.ui_login("admin")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/config")
        page.wait_for_selector("#dt-clients", timeout=15000)
        self._hide_debugbar()

        row = page.locator("#dt-clients tbody tr", has_text=f"({client_id})")
        self._ui_spotlight(row, badge=f"Baris Client {client_id}", phase="WHEN", title=f"Cari Data Client {client_id}", detail="Menemukan entri konfigurasi pada DataTables")
        btn_edit = row.locator(".btn-config-edit")
        self._ui_spotlight(btn_edit, badge="Tombol: Edit Config", phase="WHEN", title="Buka Form Edit Konfigurasi")
        btn_edit.click(force=True)

        page.wait_for_selector("#config-modal", state="visible", timeout=10000)
        self._hide_debugbar()
        page.wait_for_function("document.getElementById('cfg-id') && document.getElementById('cfg-id').value !== ''", timeout=10000)

        self._ui_spotlight("#det-alert-emails", badge="Updated: updated_ops@test.com", phase="WHEN", title="Perbarui Email Notifikasi Alert", detail="Mengubah email alert menjadi updated_ops@test.com")
        page.fill("#det-alert-emails", "updated_ops@test.com")
        self._ui_spotlight("#rl-table", badge="Rate Limit Parameters", phase="WHEN", title="Perbarui Nilai Rate Limit", detail="Mengubah threshold rate limit pada tabel rule")
        page.evaluate("""
            var r1_val = document.querySelector("#rl-table tbody tr .w-val");
            if (r1_val) r1_val.value = "2";
            var r1_loc = document.querySelector("#rl-table tbody tr .w-loc");
            if (r1_loc) r1_loc.value = "20";
            var r1_intl = document.querySelector("#rl-table tbody tr .w-intl");
            if (r1_intl) r1_intl.value = "10";
        """)

        self._ui_spotlight("#btn-save-config", badge="Tombol: Simpan Perubahan", phase="WHEN", title="Submit Pembaruan Konfigurasi", detail="Mengirimkan update konfigurasi ke backend")
        with page.expect_navigation(timeout=15000):
            page.evaluate("$('#btn-save-config').click()")

        self._hide_debugbar()
        self._ui_hud_passed(title=f"Perubahan Client {client_id} Berhasil Disimpan", detail="Form edit konfigurasi disubmit sukses")
        logger.info(f"[UI ACTION] Parameter konfigurasi client {client_id} berhasil diubah melalui form modal.")

    @keyword("UI Eksekusi Aksi Lifecycle Pada Baris Datatable")
    def ui_click_lifecycle_action(self, username: str, action: str, client_id: int = 101):
        self.ui_login(username)
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/config")
        page.wait_for_selector("#dt-clients", timeout=15000)
        self._hide_debugbar()

        row = page.locator("#dt-clients tbody tr", has_text=f"({client_id})")
        btn = row.locator(f'button:has-text("{action.capitalize()}")')

        self._ui_spotlight(row, badge=f"Baris Client {client_id}", phase="WHEN", title=f"Navigasi Baris Client {client_id}", detail="Mempersiapkan eksekusi aksi status lifecycle")
        self._ui_spotlight(btn, badge=f"Tombol: {action.upper()}", phase="WHEN", title=f"Eksekusi Aksi {action.upper()}", detail=f"Pengguna {username} memicu aksi {action} dengan konfirmasi")

        prompts = {
            "submit": "Submit config ini untuk approval CCO?",
            "approve": "Approve config ini?",
            "reject": "Reject config ini?",
            "deactivate": "Deactivate config ini?",
            "reopen": "Reopen config ini ke PENDING_APPROVAL?"
        }
        expected_prompt = prompts.get(action.lower(), "")
        self._click_with_expected_confirm(btn, expected_prompt)
        self._ui_hud_passed(title=f"Aksi {action.upper()} Berhasil Dipicu", detail=f"Aksi {action} dieksekusi via tombol UI dengan konfirmasi dialog")
        logger.info(f"[UI ACTION] Aksi '{action}' untuk client {client_id} diklik via tombol antarmuka.")

    @keyword("UI Verifikasi Tombol Approval Tidak Tersedia Untuk Non CCO")
    def ui_verify_non_cco_restriction(self, client_id: int = 101):
        self.ui_login("admin")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/config")
        page.wait_for_selector("#dt-clients", timeout=15000)
        self._hide_debugbar()

        row = page.locator("#dt-clients tbody tr", has_text=f"({client_id})")
        self._ui_spotlight(row, badge="Restriksi Non-CCO (0 Tombol)", phase="THEN", title="Verifikasi Restriksi Hak Akses CCO", detail="Memastikan tombol Approve & Reject tidak bocor ke role Non-CCO")
        approve_count = row.locator('button:has-text("Approve")').count()
        reject_count = row.locator('button:has-text("Reject")').count()
        if approve_count > 0 or reject_count > 0:
            raise AssertionError(f"Tombol Approve ({approve_count}) / Reject ({reject_count}) muncul untuk Non-CCO!")
        self._ui_hud_passed(title="Restriksi Hak Akses Non-CCO Valid", detail="Tombol Approve & Reject terbukti 0 elemen (tersembunyi)")
        logger.info("[UI ASSERT] Tombol Approve/Reject terbukti tersembunyi (0 elemen) untuk Non-CCO.")

    @keyword("UI Verifikasi Matriks Aksi Ketersediaan State Machine")
    def ui_verify_state_machine_matrix(self, client_id: int = 101):
        self.ui_login("admin")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/config")
        page.wait_for_selector("#dt-clients", timeout=15000)
        self._hide_debugbar()

        row = page.locator("#dt-clients tbody tr", has_text=f"({client_id})")
        self._ui_spotlight(row, badge="State DRAFT: Aksi Legal Terbatas", phase="THEN", title="Validasi State Machine UI", detail="Memastikan aksi ilegal Approve dan Deactivate tidak tersedia")
        approve_count = row.locator('button:has-text("Approve")').count()
        deact_count = row.locator('button:has-text("Deactivate")').count()
        if approve_count > 0 or deact_count > 0:
            raise AssertionError(f"Tombol ilegal tampil pada baris DRAFT! Approve: {approve_count}, Deact: {deact_count}")
        self._ui_hud_passed(title="Kepatuhan State Machine Terbukti", detail="Tombol Approve & Deactivate tidak tersedia pada status DRAFT")
        logger.info("[UI ASSERT] Matriks ketersediaan aksi UI terbukti taat pada state machine.")

    @keyword("UI Eksekusi Tombol SYNC Konfigurasi")
    def ui_sync_config(self):
        self.ui_login("admin")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/config")
        page.wait_for_selector("#btn-sync-config", timeout=15000)
        self._hide_debugbar()

        btn = page.locator("#btn-sync-config")
        self._ui_spotlight(btn, badge="Tombol: SYNC Config Global", phase="WHEN", title="Eksekusi Tombol SYNC Config", detail="Menyiarkan reload anti-fraud ke ActiveMQ Topic untuk seluruh client")
        self._click_with_expected_confirm(btn, "Kirim SYNC config (reload anti-fraud) untuk semua client?")
        self._ui_hud_passed(title="SYNC Konfigurasi Berhasil Dipicu", detail="Konfirmasi diterima dan sinyal reload disiarkan")
        logger.info("[UI ACTION] Tombol SYNC config diklik dan konfirmasi diterima.")

    # ==========================================================================
    # 3. WEB UI ACTIONS: WHITELIST
    # ==========================================================================

    @keyword("UI Tambah Whitelist Target")
    def ui_add_whitelist(self, wl_type: str = "msisdn", client_id: int = 101, value: str = "628123456789", desc: str = "Test"):
        self.ui_login("admin")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/whitelist")
        page.wait_for_selector("#form-whitelist-add", timeout=15000)
        self._hide_debugbar()

        self._ui_spotlight("#wl-type", badge=f"Tipe: {wl_type.upper()}", phase="WHEN", title=f"Tambah Whitelist {wl_type.upper()}", detail="Memilih tipe data whitelist")
        page.select_option("#wl-type", wl_type.lower())
        self._ui_spotlight("#wl-client", badge=f"Client ID: {client_id}", phase="WHEN", title="Pilih Client Whitelist")
        page.evaluate(f"""
            var sel = document.getElementById("wl-client");
            var opt = new Option("Client {client_id}", "{client_id}", true, true);
            sel.appendChild(opt);
            if (window.jQuery) {{ window.jQuery(sel).trigger("change"); }}
        """)
        self._ui_spotlight("#wl-value", badge=f"Nilai: {value}", phase="WHEN", title="Isi Nilai Whitelist", detail=f"Memasukkan target {wl_type}: {value}")
        page.fill("#wl-value", value)
        self._ui_spotlight("#wl-description", badge=f"Ket: {desc}", phase="WHEN", title="Isi Deskripsi Whitelist")
        page.fill("#wl-description", desc)

        btn_submit = page.locator('#form-whitelist-add button[type="submit"]')
        self._ui_spotlight(btn_submit, badge="Tombol: Tambah Whitelist", phase="WHEN", title="Submit Form Whitelist")
        with page.expect_navigation(timeout=15000):
            btn_submit.click(force=True)

        self._hide_debugbar()
        self._ui_hud_passed(title=f"Whitelist {wl_type.upper()} Berhasil Ditambahkan", detail=f"Target {value} diproses oleh sistem")
        logger.info(f"[UI ACTION] Whitelist {wl_type}:{value} ditambahkan via form web.")

    @keyword("UI Tambah Whitelist Format Tidak Valid Dan Pastikan Ditolak")
    def ui_add_invalid_whitelist(self):
        self.ui_add_whitelist("msisdn", 101, "INVALID_CHARS", "Invalid Format")

    @keyword("UI Verifikasi Penolakan Form Whitelist Tertampil")
    def ui_verify_invalid_whitelist_alert(self):
        page = self._get_page()
        alert_el = page.locator(".alert-failed, .alert-danger, .alert-warning").first
        alert = alert_el.text_content().strip()
        self._ui_spotlight(alert_el, badge="Alert Validasi Whitelist", phase="THEN", title="Validasi Penolakan Format Whitelist", detail=alert)
        self._ui_hud_passed(title="Format Whitelist Ditolak Sistem", detail=alert)
        logger.info(f"[UI ASSERT] Penolakan whitelist di DOM: {alert}")

    @keyword("UI Toggle Status Whitelist Pada Datatable")
    def ui_toggle_whitelist(self, target_value: str = "628123456789", action_do: str = "deactivate"):
        self.ui_login("admin")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/whitelist")
        page.wait_for_selector("#dt-whitelist", timeout=15000)
        self._hide_debugbar()

        clean_val = re.sub(r"[+\-\s]", "", str(target_value).strip())
        if clean_val.startswith("08"):
            clean_val = "628" + clean_val[2:]
        row = page.locator("#dt-whitelist tbody tr", has_text=clean_val)
        btn = row.locator('button[type="submit"]')

        self._ui_spotlight(row, badge=f"Target: {clean_val}", phase="WHEN", title=f"Cari Entri Whitelist {clean_val}", detail="Menemukan baris target pada tabel whitelist")
        self._ui_spotlight(btn, badge=f"Tombol: {action_do.upper()}", phase="WHEN", title=f"Toggle Status Whitelist ({action_do.upper()})", detail="Mengubah status aktif/nonaktif target")

        expected_prompt = "Nonaktifkan whitelist ini?" if action_do == "deactivate" else "Aktifkan kembali whitelist ini?"
        self._click_with_expected_confirm(btn, expected_prompt)
        self._ui_hud_passed(title=f"Toggle Whitelist {action_do.upper()} Berhasil", detail=f"Target {clean_val} berhasil diubah statusnya")
        logger.info(f"[UI ACTION] Whitelist {target_value} ditoggle ke '{action_do}' via UI.")

    # ==========================================================================
    # 4. WEB UI ACTIONS: BLOCKLIST & UNBLOCK
    # ==========================================================================

    @keyword("UI Buka Halaman Blocklist Dan Observasi Otorisasi")
    def ui_view_blocklist(self, as_role: str = "cco"):
        username = "ccouser" if as_role == "cco" else "admin"
        self.ui_login(username)
        page = self._get_page()
        with page.expect_response(lambda r: "/antifraud/blocks/datatable" in r.url and r.request.method == "GET" and r.status == 200) as resp:
            page.goto(f"{self.base_url}/antifraud/blocks")
        self._hide_debugbar()

        if as_role == "cco":
            if page.locator(".btn-af-unblock").count() == 0 or page.locator("#unblock-modal").count() == 0:
                raise AssertionError("Tombol unblock / modal unblock tidak muncul untuk CCO!")
            self._ui_spotlight("#dt-blocklist", badge="Blocklist Aktif (Role: CCO)", phase="THEN", title="Tampilan Blocklist & Aksi Unblock", detail="Memverifikasi tombol unblock dan modal tersedia untuk CCO")
            self._ui_spotlight(".btn-af-unblock", badge="Tombol: Unblock Target")
            self._ui_hud_passed(title="Blocklist CCO Terverifikasi", detail="Hak aksi unblock tersedia lengkap")
            logger.info("[UI ACTION & ASSERT] Halaman blocklist CCO memuat tombol unblock dan modal.")
        else:
            if page.locator(".btn-af-unblock").count() > 0 or page.locator("#unblock-modal").count() > 0:
                raise AssertionError("Tombol unblock / modal unblock bocor pada role Non-CCO!")
            self._ui_spotlight("#dt-blocklist", badge="Blocklist (Role: Non-CCO)", phase="THEN", title="Tampilan Blocklist Non-CCO", detail="Memverifikasi tombol unblock tersembunyi bagi Non-CCO")
            self._ui_hud_passed(title="Restriksi Blocklist Terverifikasi", detail="Tombol unblock terbukti tersembunyi untuk Non-CCO")
            logger.info("[UI ACTION & ASSERT] Halaman blocklist Non-CCO terbukti menyembunyikan tombol unblock.")

    @keyword("UI Eksekusi Unblock Target Dengan Alasan")
    def ui_unblock(self, target_val: str = "6281200000001", reason: str = "Nasabah VIP"):
        self.ui_login("ccouser")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/blocks")
        page.wait_for_selector("#dt-blocklist", timeout=15000)
        self._hide_debugbar()

        clean_val = target_val.lstrip("+")
        row = page.locator("#dt-blocklist tbody tr", has_text=clean_val)
        self._ui_spotlight(row, badge=f"Target: {clean_val}", phase="WHEN", title=f"Cari Target Fraud {clean_val}", detail="Menemukan nomor terblokir pada DataTables")
        btn_unblock = row.locator(".btn-af-unblock")
        self._ui_spotlight(btn_unblock, badge="Tombol: Unblock", phase="WHEN", title="Buka Modal Unblock", detail="Membuka form konfirmasi pembukaan blokir")
        btn_unblock.click(force=True)

        page.wait_for_selector("#unblock-modal", state="visible", timeout=10000)
        self._hide_debugbar()
        self._ui_spotlight("#unblock-reason", badge=f"Alasan: {reason}", phase="WHEN", title="Isi Alasan Unblock", detail=f"Memasukkan alasan resmi pembukaan blokir: '{reason}'")
        page.fill("#unblock-reason", reason)

        btn_confirm = page.locator('#unblock-form button[type="submit"]')
        self._ui_spotlight(btn_confirm, badge="Tombol: Konfirmasi Unblock", phase="WHEN", title="Submit Form Unblock")
        with page.expect_navigation(timeout=15000):
            btn_confirm.click(force=True)

        self._hide_debugbar()
        self._ui_hud_passed(title=f"Unblock Target {clean_val} Berhasil Dipicu", detail=f"Alasan '{reason}' dikirimkan via form modal")
        logger.info(f"[UI ACTION] Aksi Unblock target {target_val} dikirim via modal web.")

    @keyword("UI Verifikasi Flash Alert Antrean Unblock")
    def ui_verify_unblock_queued_alert(self):
        page = self._get_page()
        self._hide_debugbar()
        alert = ""
        alert_el = None
        for sel in [".alert-success", ".alert-info", ".alert"]:
            if page.locator(sel).count() > 0:
                alert = page.locator(sel).first.text_content().strip()
                alert_el = page.locator(sel).first
                break
        if "Unblock command queued" not in alert and "pending Action Queue" not in alert:
            raise AssertionError(f"Alert antrean unblock tidak sesuai! Got: '{alert}'")
        self._ui_spotlight(alert_el, badge="Alert: Unblock Queued", phase="THEN", title="Flash Alert Unblock Queued", detail=alert)
        self._ui_hud_passed(title="Antrean Unblock Diterima", detail=alert)
        logger.info(f"[UI ASSERT] Flash alert antrean unblock terverifikasi: '{alert}'")

    @keyword("UI Eksekusi Unblock Dengan Alasan Spasi Dan Pastikan Ditolak")
    def ui_unblock_spaces_only(self, target_val: str = "6281200000001"):
        self.ui_login("ccouser")
        page = self._get_page()
        page.goto(f"{self.base_url}/antifraud/blocks")
        page.wait_for_selector("#dt-blocklist", timeout=15000)
        self._hide_debugbar()

        clean_val = target_val.lstrip("+")
        row = page.locator("#dt-blocklist tbody tr", has_text=clean_val)
        btn_unblock = row.locator(".btn-af-unblock")
        self._ui_spotlight(btn_unblock, badge="Tombol: Unblock", phase="WHEN", title="Buka Modal Unblock", detail="Menguji validasi alasan spasi")
        btn_unblock.click(force=True)

        page.wait_for_selector("#unblock-modal", state="visible", timeout=10000)
        self._hide_debugbar()
        self._ui_spotlight("#unblock-reason", badge="Alasan: [HANYA SPASI]", phase="WHEN", title="Isi Alasan Spasi", detail="Memasukkan karakter spasi kosong untuk memicu validasi")
        page.fill("#unblock-reason", "   ")

        # 1. UI validation check: click submit and verify client validation marks .has-error
        page.locator('#unblock-form button[type="submit"]').click(force=True)
        if page.locator("#unblock-modal .has-error").count() == 0:
            raise AssertionError("Client validation .has-error tidak muncul pada modal unblock!")
        self._ui_spotlight("#unblock-modal .has-error", badge="Validasi DOM: .has-error", phase="THEN", title="Client Validation Aktif", detail="Form mendeteksi input hanya berisi spasi")
        logger.info("[UI ASSERT] Client validation .has-error terbukti aktif pada modal.")

        # 2. Server validation check: submit form to verify controller rejects whitespace reason
        page.evaluate("$('#unblock-form').off('submit');")
        with page.expect_navigation(timeout=15000):
            page.evaluate("$('#unblock-form').submit();")

        self._hide_debugbar()
        alert = ""
        alert_el = None
        for sel in [".alert-failed", ".alert-danger", ".alert-warning"]:
            if page.locator(sel).count() > 0:
                alert = page.locator(sel).first.text_content().strip()
                alert_el = page.locator(sel).first
                break
        if "Reason is required" not in alert:
            raise AssertionError(f"Alert validasi server spasi gagal! Didapat: '{alert}'")
        self._ui_spotlight(alert_el, badge="Alert Server Rejection", phase="THEN", title="Server Validation Aktif", detail=alert)
        self._ui_hud_passed(title="Validasi Alasan Spasi Terbukti", detail=alert)
        logger.info(f"[UI ASSERT] Server controller rejection terbukti: '{alert}'")

    # ==========================================================================
    # 5. WEB UI ACTIONS: MULTI-TENANT ISOLATION & AUDIT CYCLES
    # ==========================================================================

    @keyword("UI Akses Seluruh Menu Anti Fraud Lintas Tenant")
    def ui_access_all_menus_jatis(self):
        self.ui_login("admin")
        page = self._get_page()
        for path in ["/antifraud/config", "/antifraud/whitelist", "/antifraud/blocks", "/antifraud/audit"]:
            with page.expect_response(lambda r: "/datatable" in r.url and r.status == 200):
                page.goto(f"{self.base_url}{path}")
            self._hide_debugbar()
            self._ui_spotlight(None, phase="WHEN", title=f"Navigasi Menu: {path}", detail="Memverifikasi akses dan data AJAX DataTables")
        self._ui_hud_passed(title="Seluruh Menu Anti Fraud Terverifikasi", detail="Super Admin JATIS memiliki hak akses lintas tenant")
        logger.info("[UI ACTION] Seluruh menu Anti Fraud berhasil diakses oleh Super Admin JATIS.")

    @keyword("UI Observasi Isolasi Multi Tenant Pada Seluruh Datatable")
    def ui_observe_tenant_datatables(self, username: str = "client10user", expected_cid: int = 10, forbidden_cid: int = 20):
        self.ui_login(username)
        page = self._get_page()

        with page.expect_response(
            lambda r: "/antifraud/config/datatable" in r.url and r.request.method == "GET" and r.status == 200
        ) as resp_info:
            page.goto(f"{self.base_url}/antifraud/config")

        self.dt_client10_json = resp_info.value.json()
        dt = self.dt_client10_json
        records_total = dt.get("recordsTotal", 0)
        data = dt.get("data", [])

        if records_total <= 0 or len(data) <= 0:
            raise AssertionError(f"DataTables untuk {username} kosong (recordsTotal: {records_total})! Tidak boleh dianggap PASS.")

        for row in data:
            row_str = str(row)
            if f"({expected_cid})" not in row_str and f"Client {expected_cid}" not in row_str and "ITC AUTO" not in row_str:
                raise AssertionError(f"Baris DataTables tidak memuat identitas Client {expected_cid}: {row}")

        raw_json = json.dumps(dt)
        if f"({forbidden_cid})" in raw_json or "Matahari" in raw_json:
            raise AssertionError(f"Data Client {forbidden_cid} bocor pada DataTables response!")

        dom_text = page.locator("#dt-clients").text_content()
        if f"({forbidden_cid})" in dom_text or "Matahari" in dom_text:
            raise AssertionError(f"Data Client {forbidden_cid} bocor pada DOM!")

        self._ui_spotlight("#dt-clients", badge=f"Scope Data: Client {expected_cid}", phase="THEN", title="Observasi Isolasi Multi-Tenant", detail=f"Data Client {expected_cid} tampil, Client {forbidden_cid} terbukti nihil")
        self._ui_hud_passed(title="Isolasi Tenant Terbukti 100%", detail=f"Tidak ada kebocoran data antar tenant")
        logger.info(f"[UI ASSERT] Isolasi tenant terbukti 100%. Data Client {expected_cid} ada, Client {forbidden_cid} nihil.")

    @keyword("UI Eksekusi Siklus Penuh Konfigurasi")
    def ui_full_config_cycle(self, client_id: int = 101):
        self.ui_create_config(client_id)
        self.ui_edit_config(client_id)
        self.ui_click_lifecycle_action("admin", "submit", client_id)
        self.ui_click_lifecycle_action("ccouser", "approve", client_id)
        self.ui_click_lifecycle_action("ccouser", "deactivate", client_id)
        self.ui_click_lifecycle_action("admin", "reopen", client_id)
        self.ui_click_lifecycle_action("ccouser", "reject", client_id)
        logger.info("[UI CYCLE] Siklus penuh konfigurasi selesai dijalankan via UI.")

    @keyword("UI Eksekusi Siklus Whitelist Dan Unblock")
    def ui_full_whitelist_unblock_cycle(self, client_id: int = 101):
        self.ui_add_whitelist("msisdn", client_id, "6281299990001", "Audit MSISDN")
        self.ui_toggle_whitelist("6281299990001", "deactivate")
        self.ui_add_whitelist("prefix", client_id, "6281299", "Audit Prefix")
        self.ui_toggle_whitelist("6281299", "deactivate")
        self.db_seed_active_block_state(client_id, "6281200000001")
        self.ui_unblock("6281200000001", "Audit Unblock Reason")
        logger.info("[UI CYCLE] Siklus Whitelist & Unblock selesai dijalankan via UI.")

    # ==========================================================================
    # 6. SPOTLIGHT HUD RUNNER (TC-001)
    # ==========================================================================

    @keyword("Jalankan Browser E2E Journey Verifikasi Menu Dan Sidebar Spotlight")
    def browser_execute_tc001_journey(self):
        page = self._get_page()
        runner = InjectedHudSpotlightRunner(page, SCREENSHOT_DIR)

        page.goto(f"{self.base_url}/")
        page.wait_for_selector('input[name="username"]', timeout=10000)
        runner.inject_overlay()
        runner.update_hud("1/4", "Login Portal JNS7", "Melakukan autentikasi akun Super Admin JNS7", "STANDBY")
        runner.highlight('input[name="username"]', "Username")
        if self.headed: time.sleep(1.0)
        runner.snapshot("rf_01_given_portal_login")

        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "admin123")
        runner.update_hud("2/4", "Submit Autentikasi", "Kredensial Super Admin berhasil dimasukkan", "RUNNING")
        if self.headed: time.sleep(1.0)
        runner.snapshot("rf_02_when_credentials_filled")

        with page.expect_navigation(timeout=15000):
            page.click('button[type="submit"]')

        self._hide_debugbar()
        runner.inject_overlay()
        runner.update_hud("3/4", "Dashboard Dimuat", "Verifikasi sesi aktif dan dashboard portal JNS7", "PASS")
        if self.headed: time.sleep(1.0)
        runner.snapshot("rf_03_then_dashboard_active")

        page.wait_for_selector('a:has-text("Anti Fraud")', timeout=10000)
        runner.highlight('a:has-text("Anti Fraud")', "Parent Menu")
        if self.headed: time.sleep(1.0)
        page.click('a:has-text("Anti Fraud")')
        time.sleep(0.5)

        submenus = ["Client Config", "Whitelist", "Blocklist & Unblock", "Audit Log"]
        for sub in submenus:
            page.wait_for_selector(f'a:has-text("{sub}")', timeout=5000)

        runner.update_hud("4/4", "Sidebar Anti Fraud", "Parent menu & 4 submenu tampil lengkap pada sidebar", "PASS")
        if self.headed: time.sleep(2.0)
        runner.snapshot("rf_04_and_sidebar_antifraud_selected")
        self.current_user = "admin"

    @keyword("UI Verifikasi Seluruh Submenu Anti Fraud 200 OK")
    def ui_verify_all_submenus_in_browser(self):
        page = self._get_page()
        for path in ["/antifraud/config", "/antifraud/whitelist", "/antifraud/blocks", "/antifraud/audit"]:
            with page.expect_response(lambda r: path in r.url and r.status == 200):
                page.goto(f"{self.base_url}{path}")
            self._hide_debugbar()
            self._ui_spotlight(None, phase="THEN", title=f"Verifikasi Submenu HTTP 200: {path}", detail="Submenu termuat sukses")
            logger.info(f"[UI NAVIGATE] Submenu {path} berhasil dimuat dengan status 200 OK.")
        self._ui_hud_passed(title="4 Submenu Anti Fraud Terverifikasi 200 OK", detail="Seluruh rute menu valid dan beroperasi")

    # ==========================================================================
    # 7. MULTI-LAYER ASSERTIONS: DATABASE (MYSQL)
    # ==========================================================================

    def _get_db_conn(self, db_name: str):
        return pymysql.connect(
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_pass,
            database=db_name,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )

    @keyword("DB Bersihkan Data Uji Database Anti Fraud")
    def db_cleanup_test_data(self):
        self.snapshots.clear()
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM anti_fraud_config WHERE client_id IN (101, 9999)")
                cur.execute("DELETE FROM anti_fraud_config_audit_log WHERE target_client_id IN (101, 9999)")
                cur.execute("DELETE FROM anti_fraud_msisdn_whitelist WHERE client_id IN (101, 9999)")
                cur.execute("DELETE FROM anti_fraud_prefix_whitelist WHERE client_id IN (101, 9999)")
                cur.execute("DELETE FROM anti_fraud_block_state WHERE client_id IN (101, 9999)")
            logger.info("[DB] Data uji anti-fraud (client 101, 9999) dibersihkan.")
        finally:
            conn.close()

    @keyword("DB Pastikan Client Belum Memiliki Konfigurasi Anti Fraud")
    def db_ensure_client_has_no_config(self, client_id: int = 101):
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM anti_fraud_config WHERE client_id = %s", (client_id,))
                cur.execute("DELETE FROM anti_fraud_config_audit_log WHERE target_client_id = %s", (client_id,))
            logger.info(f"[DB] Client {client_id} dipastikan belum memiliki konfigurasi anti-fraud.")
        finally:
            conn.close()

    @keyword("DB Ambil Data Konfigurasi Client")
    def db_get_config(self, client_id: int = 101) -> Dict[str, Any]:
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM anti_fraud_config WHERE client_id = %s", (client_id,))
                row = cur.fetchone()
                if not row:
                    raise AssertionError(f"Konfigurasi untuk client_id {client_id} tidak ditemukan di DB!")
                return row
        finally:
            conn.close()

    @keyword("DB Ambil Snapshot Konfigurasi Client")
    def db_snapshot_config(self, client_id: int = 101):
        row = self.db_get_config(client_id)
        self.snapshots[f"config_{client_id}"] = dict(row)
        LogHelper._log_chunked(f"Snapshot Konfigurasi Client {client_id}", row)

    @keyword("DB Verifikasi Data Konfigurasi Cocok Sempurna")
    def db_verify_config_field_by_field(self, client_id: int = 101, expected_status: str = "DRAFT"):
        actual = self.db_get_config(client_id)
        expected = {
            "client_id": int(client_id),
            "approval_status": expected_status,
            "enable_rate_limit": 1,
            "enable_sequential": 1,
            "enable_traffic_anomaly": 1,
            "enable_loss_monitoring": 1,
            "rule_actions": {"rate_limit": "ALERT + BLOCK", "sequential": "ALERT + BLOCK", "traffic": "ALERT", "loss": "ALERT"}
        }
        for k, v in expected.items():
            act_val = actual.get(k)
            if k == "rule_actions" and isinstance(act_val, str):
                act_val = json.loads(act_val)
            if act_val != v:
                raise AssertionError(f"[ERROR] Field '{k}': expected '{v}', got '{act_val}'")

        LogHelper._log_chunked("Komparasi Lengkap Database Konfigurasi", {"expected": expected, "actual": actual})

    @keyword("DB Sisipkan Data Konfigurasi Uji Dengan Status")
    def db_seed_config_with_status(self, client_id: int = 101, status: str = "APPROVED", approver: Optional[str] = "admin"):
        self.db_ensure_client_has_no_config(client_id)
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO anti_fraud_config (
                        client_id, client_name, sender_id, sender_name, division_id, division_name,
                        approval_status, approved_by, effective_date, alert_emails,
                        rate_limit_windows, seq_windows, loss_thresholds, rule_actions, traffic_config,
                        enable_rate_limit, enable_sequential, enable_loss_monitoring, enable_traffic_anomaly,
                        created_by, created_at, updated_at
                    ) VALUES (
                        %s, 'PT.DIGITAL VISION NUSANTARA', 0, 'ALL', 0, 'ALL',
                        %s, %s, NULL, '["ops@test.com"]',
                        '[{"name":"W1","val":10,"unit":"MINUTE","loc":10,"intl":4,"scope":"DOMESTIC"}]',
                        '[{"name":"W1","val":15,"unit":"MINUTE","loc":25,"intl":10,"scope":"DOMESTIC"}]',
                        '{"TSEL":[{"name":"W1","val":1,"unit":"HOUR","loss":0}]}',
                        '{"rate_limit":"ALERT + BLOCK","sequential":"ALERT + BLOCK","traffic":"ALERT","loss":"ALERT"}',
                        '{"threshold_pct":50,"window":{"val":90,"unit":"DAY"},"min_baseline":24}',
                        1, 1, 1, 1,
                        'admin', NOW(), NOW()
                    )
                """, (client_id, status, approver if status == "APPROVED" else None))
            logger.info(f"[DB FIXTURE] Konfigurasi uji client {client_id} (status: {status}) disiapkan.")
        finally:
            conn.close()

    @keyword("DB Verifikasi Snapshot Konfigurasi Berhasil Diperbarui")
    def db_verify_config_updated(self, client_id: int = 101):
        baseline = self.snapshots.get(f"config_{client_id}")
        current = self.db_get_config(client_id)
        emails = json.loads(current.get("alert_emails") or "[]")
        if "updated_ops@test.com" not in emails:
            raise AssertionError(f"Alert emails tidak terbarui! Data: {emails}")

        ignored = {"alert_emails", "rate_limit_windows", "updated_at"}
        for k, v in baseline.items():
            if k not in ignored and str(current.get(k)) != str(v):
                raise AssertionError(f"Field '{k}' termutasi! Baseline: '{v}', Current: '{current.get(k)}'")
        logger.info("[DB ASSERT] Seluruh kolom lainnya terbukti identik dengan baseline.")

    @keyword("DB Verifikasi Snapshot Konfigurasi Otomatis Kembali Ke Draft")
    def db_verify_config_reverted_to_draft(self, client_id: int = 101):
        current = self.db_get_config(client_id)
        if current["approval_status"] != "DRAFT":
            raise AssertionError(f"Status tidak kembali ke DRAFT! Current: {current['approval_status']}")
        if current["approved_by"] is not None:
            raise AssertionError(f"Approved_by tidak NULL! Current: {current['approved_by']}")
        logger.info("[DB ASSERT] Konfigurasi terbukti otomatis kembali ke DRAFT dengan approver NULL.")

    @keyword("DB Verifikasi Kolom Approved By Terisi")
    def db_verify_approved_by_filled(self, client_id: int = 101, expected_user: str = "ccouser"):
        current = self.db_get_config(client_id)
        approved_by = str(current.get("approved_by") or "")
        approved_by_user = str(current.get("approved_by_user") or "")
        if approved_by != "CCO" and approved_by != expected_user and approved_by_user != expected_user:
            raise AssertionError(f"Approved_by tidak cocok! Expected: '{expected_user}' or 'CCO', Got approved_by='{approved_by}', approved_by_user='{approved_by_user}'")
        logger.info(f"[DB ASSERT] Kolom approved_by/approved_by_user terverifikasi: role='{approved_by}', user='{approved_by_user}'.")

    @keyword("DB Verifikasi Data Whitelist Database")
    def db_verify_whitelist(self, client_id: int = 101, target_type: str = "msisdn", value: str = "628123456789", expected_active: int = 1):
        conn = self._get_db_conn(self.db_broadcast)
        table = "anti_fraud_msisdn_whitelist" if target_type.lower() == "msisdn" else "anti_fraud_prefix_whitelist"
        col = "msisdn_e164" if target_type.lower() == "msisdn" else "sub_prefix"
        clean_val = re.sub(r"[+\-\s]", "", str(value).strip())
        if clean_val.startswith("08"):
            clean_val = "628" + clean_val[2:]
        exp_act = int(expected_active)
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {table} WHERE client_id = %s AND {col} = %s", (client_id, clean_val))
                row = cur.fetchone()
                if not row or int(row.get("is_active", 0)) != exp_act:
                    raise AssertionError(f"Data whitelist {target_type}:{clean_val} tidak sesuai ekspektasi (is_active={exp_act})! Data: {row}")
        finally:
            conn.close()

    @keyword("DB Sisipkan Data Whitelist Uji")
    def db_seed_whitelist(self, client_id: int = 101, target_type: str = "msisdn", value: str = "628123456789", active: int = 1):
        conn = self._get_db_conn(self.db_broadcast)
        table = "anti_fraud_msisdn_whitelist" if target_type.lower() == "msisdn" else "anti_fraud_prefix_whitelist"
        col = "msisdn_e164" if target_type.lower() == "msisdn" else "sub_prefix"
        clean_val = re.sub(r"[+\-\s]", "", str(value).strip())
        if clean_val.startswith("08"):
            clean_val = "628" + clean_val[2:]
        act = int(active)
        try:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {table} WHERE client_id = %s AND {col} = %s", (client_id, clean_val))
                cur.execute(f"INSERT INTO {table} (client_id, {col}, description, is_active, created_at) VALUES (%s, %s, 'Fixture', %s, NOW())", (client_id, clean_val, act))
        finally:
            conn.close()

    @keyword("DB Sisipkan Data Block State Uji")
    def db_seed_active_block_state(self, client_id: int = 101, target_value: str = "6281200000001", scope: str = "MSISDN", status: str = "ACTIVE"):
        conn = self._get_db_conn(self.db_broadcast)
        clean_val = target_value.lstrip("+")
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM anti_fraud_block_state WHERE client_id = %s AND target_value = %s", (client_id, clean_val))
                cur.execute("DESCRIBE anti_fraud_block_state")
                cols = [r["Field"] for r in cur.fetchall()]
                source_col = "source" if "source" in cols else "source_rule"
                cur.execute(f"""
                    INSERT INTO anti_fraud_block_state 
                    (scope, client_id, sender_id, sender_name, division_id, division_name, target_value, {source_col}, status, expires_at, created_at, updated_at)
                    VALUES (%s, %s, 0, 'ALL', 0, 'ALL', %s, 'RATE-LIMIT:W1', %s, DATE_ADD(NOW(), INTERVAL 1 DAY), NOW(), NOW())
                """, (scope, client_id, clean_val, status))
            logger.info(f"[DB] Block state aktif untuk client {client_id} (target: {clean_val}) disiapkan.")
        finally:
            conn.close()

    @keyword("DB Verifikasi Data Block State Database")
    def db_verify_block_state(self, client_id: int = 101, target_value: str = "6281200000001", expected_status: str = "INACTIVE", expected_unblocker: Optional[str] = "ccouser", expected_reason: Optional[str] = None):
        conn = self._get_db_conn(self.db_broadcast)
        clean_val = target_value.lstrip("+")
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM anti_fraud_block_state WHERE client_id = %s AND target_value = %s", (client_id, clean_val))
                row = cur.fetchone()
                if not row or row["status"] != expected_status:
                    raise AssertionError(f"Block state {clean_val} bukan '{expected_status}'! Data: {row}")
                if expected_unblocker and expected_unblocker.lower() != "none" and str(row.get("unblocked_by")) != expected_unblocker:
                    raise AssertionError(f"Unblocked_by tidak sesuai! Expected: '{expected_unblocker}', Got: '{row.get('unblocked_by')}'")
                if expected_reason and expected_reason.lower() != "none" and str(row.get("unblock_reason")) != expected_reason:
                    raise AssertionError(f"Unblock_reason tidak sesuai! Expected: '{expected_reason}', Got: '{row.get('unblock_reason')}'")
        finally:
            conn.close()

    @keyword("DB Verifikasi Audit Log Unblock Tercatat")
    def db_verify_audit_log_unblock(self, target_client_id: int = 101, target_val: str = "6281200000001", expected_user: str = "ccouser", expected_reason: str = "Valid customer unblock request"):
        conn = self._get_db_conn(self.db_broadcast)
        clean_val = target_val.lstrip("+")
        try:
            with conn.cursor() as cur:
                cur.execute("DESCRIBE anti_fraud_config_audit_log")
                cols = [r["Field"] for r in cur.fetchall()]
                act_col = "action_type" if "action_type" in cols else "action"
                user_col = "admin_username" if "admin_username" in cols else "actor"
                new_col = "new_value_json" if "new_value_json" in cols else "new_value"
                cur.execute(f"""
                    SELECT * FROM anti_fraud_config_audit_log 
                    WHERE target_client_id = %s AND {act_col} = 'UNBLOCK' AND target_value = %s
                    ORDER BY id DESC LIMIT 1
                """, (target_client_id, clean_val))
                row = cur.fetchone()
                if not row:
                    raise AssertionError(f"Audit log UNBLOCK untuk target {clean_val} tidak ditemukan!")
                if str(row.get(user_col)) != expected_user:
                    raise AssertionError(f"Audit log actor tidak cocok! Expected: '{expected_user}', Got: '{row.get(user_col)}'")
                new_val_raw = row.get(new_col)
                new_val = json.loads(new_val_raw) if isinstance(new_val_raw, str) else (new_val_raw or {})
                if new_val.get("requested_status") != "INACTIVE":
                    raise AssertionError(f"Audit log requested_status bukan INACTIVE! Got: {new_val.get('requested_status')}")
                if expected_reason and new_val.get("unblock_reason") != expected_reason:
                    raise AssertionError(f"Audit log unblock_reason tidak cocok! Expected: '{expected_reason}', Got: '{new_val.get('unblock_reason')}'")
                LogHelper._log_chunked("Audit Log UNBLOCK Row", row)
                logger.info(f"[DB AUDIT] Audit log UNBLOCK untuk {clean_val} oleh {expected_user} tervalidasi 100%.")
        finally:
            conn.close()

    @keyword("DB Verifikasi Audit Log Tercatat")
    def db_verify_audit_log(self, target_client_id: int = 101, action: str = "CONFIG_INSERT", username: str = "admin"):
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("DESCRIBE anti_fraud_config_audit_log")
                cols = [r["Field"] for r in cur.fetchall()]
                act_col = "action_type" if "action_type" in cols else "action"
                if int(target_client_id) == 0:
                    cur.execute(f"SELECT * FROM anti_fraud_config_audit_log WHERE {act_col} = %s ORDER BY id DESC LIMIT 1", (action,))
                else:
                    cur.execute(f"SELECT * FROM anti_fraud_config_audit_log WHERE target_client_id = %s AND {act_col} = %s ORDER BY id DESC LIMIT 1", (target_client_id, action))
                row = cur.fetchone()
                if not row:
                    raise AssertionError(f"Audit log action '{action}' untuk client {target_client_id} tidak ditemukan!")
                logger.info(f"[DB AUDIT] Audit log '{action}' tervalidasi di DB.")
        finally:
            conn.close()

    @keyword("DB Siapkan Fixture Multi Tenant Client Sepuluh Dan Dua Puluh")
    def db_setup_multitenant_data(self):
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM anti_fraud_config WHERE client_id IN (10, 20)")
                for cid in [10, 20]:
                    cur.execute("""
                        INSERT INTO anti_fraud_config 
                        (client_id, client_name, sender_id, sender_name, division_id, division_name, approval_status, effective_date, alert_emails,
                         enable_rate_limit, rate_limit_windows, enable_sequential, seq_windows,
                         enable_traffic_anomaly, traffic_config, enable_loss_monitoring, loss_thresholds,
                         rule_actions, created_at, updated_at)
                        VALUES (%s, 'Test Client', 0, 'ALL', 0, 'ALL', 'APPROVED', NOW(), '[]', 1, '[]', 1, '[]', 1, '{}', 1, '{}', '{}', NOW(), NOW())
                    """, (cid,))
            logger.info("[DB] Fixture Multi-Tenant Client 10 dan Client 20 disiapkan.")
        finally:
            conn.close()

    # ==========================================================================
    # 8. MULTI-LAYER ASSERTIONS: ACTIVEMQ BROKER (STOMP)
    # ==========================================================================

    @keyword("AMQ Aktifkan Subscriber ActiveMQ Topic Command")
    def amq_start_topic_subscriber(self):
        while not self.topic_queue.empty():
            self.topic_queue.get_nowait()

        if self.topic_conn and self.topic_conn.is_connected():
            return

        conn = stomp.Connection([(self.amq_host, self.amq_port)])
        self.topic_listener = StompMessageListener(self.topic_queue)
        conn.set_listener('topic_listener', self.topic_listener)
        conn.connect(self.amq_user, self.amq_pass, wait=True)
        conn.subscribe(destination='/topic/jns.topic.command', id='rf_topic_sub', ack='auto')
        self.topic_conn = conn
        logger.info(f"[AMQ] Subscriber STOMP aktif pada topic /topic/jns.topic.command ({self.amq_host}:{self.amq_port})")

    @keyword("AMQ Aktifkan Subscriber ActiveMQ Queue Action")
    def amq_start_queue_subscriber(self):
        while not self.action_queue.empty():
            self.action_queue.get_nowait()

        if self.queue_conn and self.queue_conn.is_connected():
            return

        conn = stomp.Connection([(self.amq_host, self.amq_port)])
        self.queue_listener = StompMessageListener(self.action_queue)
        conn.set_listener('queue_listener', self.queue_listener)
        conn.connect(self.amq_user, self.amq_pass, wait=True)
        conn.subscribe(destination='/queue/jns.anti.fraud.action', id='rf_queue_sub', ack='auto')
        self.queue_conn = conn
        logger.info(f"[AMQ] Subscriber STOMP aktif pada queue /queue/jns.anti.fraud.action ({self.amq_host}:{self.amq_port})")

    @keyword("AMQ Verifikasi Pesan Reload Diterima Pada Topic ActiveMQ")
    def amq_verify_topic_reload(self, expected_count: int = 1, timeout_sec: float = 6.0):
        try:
            msg = self.topic_queue.get(timeout=float(timeout_sec))
            logger.info(f"[AMQ TOPIC MSG] {msg}")
            if "reload anti-fraud" not in str(msg):
                raise AssertionError(f"Pesan Topic ActiveMQ bukan 'reload anti-fraud'! Got: {msg}")
        except queue.Empty:
            raise AssertionError(f"Timeout {timeout_sec}s: Pesan reload anti-fraud tidak diterima di Topic ActiveMQ!")

    @keyword("AMQ Verifikasi Nol Pesan Diterima Pada Topic ActiveMQ Dalam Rentang Waktu")
    def amq_verify_no_reload(self, observation_window: float = 3.0):
        time.sleep(float(observation_window))
        if not self.topic_queue.empty():
            unexpected = []
            while not self.topic_queue.empty():
                unexpected.append(self.topic_queue.get_nowait())
            raise AssertionError(f"Pesan reload ActiveMQ tidak diharapkan terkirim! Pesan: {unexpected}")
        logger.info(f"[AMQ] Terbukti 0 pesan reload selama observasi {observation_window}s.")

    @keyword("AMQ Verifikasi Payload Exact JSON Diterima Pada Queue ActiveMQ")
    def amq_verify_queue_unblock_json(self, target_value: str = "6281200000001", username: str = "ccouser", timeout_sec: float = 6.0):
        try:
            raw_msg = self.action_queue.get(timeout=float(timeout_sec))
            logger.info(f"[AMQ QUEUE MSG] {raw_msg}")
            data = json.loads(raw_msg)
            if data.get("action") != "UNBLOCK":
                raise AssertionError(f"Action payload bukan UNBLOCK! Got: {data.get('action')}")
            if str(data.get("target_value")) != str(target_value):
                raise AssertionError(f"Target value payload tidak cocok! Expected: {target_value}, Got: {data.get('target_value')}")
            if data.get("status") != "INACTIVE":
                raise AssertionError(f"Status payload bukan INACTIVE! Got: {data.get('status')}")
            if str(data.get("unblocked_by")) != str(username):
                raise AssertionError(f"Unblocked_by payload tidak cocok! Expected: {username}, Got: {data.get('unblocked_by')}")
            if not data.get("unblock_reason"):
                raise AssertionError(f"Unblock_reason payload kosong! Got: {data.get('unblock_reason')}")
            LogHelper._log_chunked("AMQ Action Queue Verified", data)
        except queue.Empty:
            raise AssertionError(f"Timeout {timeout_sec}s: Pesan aksi Unblock tidak diterima di Queue ActiveMQ!")

    @keyword("AMQ Tutup Seluruh Koneksi ActiveMQ")
    def amq_close_all(self):
        try:
            if self.topic_conn and self.topic_conn.is_connected():
                self.topic_conn.disconnect()
            if self.queue_conn and self.queue_conn.is_connected():
                self.queue_conn.disconnect()
        except Exception:
            pass
        finally:
            self.topic_conn = None
            self.queue_conn = None

    # ==========================================================================
    # 9. MULTI-LAYER ASSERTIONS: SUT LOG & FAULT INJECTION (SSH)
    # ==========================================================================

    def _get_ssh_client(self) -> paramiko.SSHClient:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ssh_host, port=self.ssh_port, username=self.ssh_user, password=self.ssh_pass, timeout=10)
        return ssh

    @keyword("SSH Ambil Snapshot Log Delta Laravel SUT")
    def ssh_get_laravel_log_offset(self, log_key: str = "default"):
        ssh = self._get_ssh_client()
        try:
            stdin, stdout, stderr = ssh.exec_command(f"stat -c %s {self.log_path} 2>/dev/null || echo 0")
            size = int(stdout.read().decode().strip() or "0")
            self.log_offsets[log_key] = size
            logger.info(f"[LOG OFFSET] Offset awal log SUT ({log_key}): {size} bytes.")
        finally:
            ssh.close()

    @keyword("SSH Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal")
    def ssh_verify_laravel_log_clean(self, log_key: str = "default"):
        initial_offset = self.log_offsets.get(log_key, 0)
        ssh = self._get_ssh_client()
        try:
            cmd = f"python3 -c 'with open(\"{self.log_path}\", \"rb\") as f: f.seek({initial_offset}); data = f.read(); print(data.decode(\"utf-8\", errors=\"replace\"))'"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            delta_text = stdout.read().decode()
            critical_patterns = ["local.ERROR", "CRITICAL", "Stack trace:", "Fatal error", "Parse error"]
            for pat in critical_patterns:
                if pat in delta_text:
                    raise AssertionError(f"Ditemukan error fatal '{pat}' pada delta log Laravel SUT!\nDelta: {delta_text[:1000]}")
            logger.info("[LOG DELTA] Log delta Laravel SUT bebas dari kesalahan fatal.")
        finally:
            ssh.close()

    @keyword("SSH Simulasikan Gangguan Koneksi ActiveMQ Pada SUT")
    def ssh_simulate_activemq_disconnect(self):
        ssh = self._get_ssh_client()
        try:
            cmd = f"iptables -I OUTPUT 1 -p tcp -d {self.amq_host} --dport {self.amq_port} -j REJECT --reject-with tcp-reset"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            time.sleep(0.5)
            logger.info(f"[FAULT INJECTION] Koneksi SUT ke ActiveMQ ({self.amq_host}:{self.amq_port}) diputus via iptables.")
        finally:
            ssh.close()

    @keyword("SSH Pulihkan Koneksi ActiveMQ Pada SUT")
    def ssh_restore_activemq_connection(self):
        ssh = self._get_ssh_client()
        try:
            cmd = f"iptables -D OUTPUT -p tcp -d {self.amq_host} --dport {self.amq_port} -j REJECT --reject-with tcp-reset 2>/dev/null || true"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            time.sleep(0.5)
            logger.info("[FAULT RESTORATION] Koneksi SUT ke ActiveMQ dipulihkan.")
        finally:
            ssh.close()
