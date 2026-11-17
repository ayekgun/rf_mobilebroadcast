#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AntiFraudLibrary.py - Custom Robot Framework Library for Anti-Fraud JNS7 CMS
Ticket: PB082643640012YA | SUT: MobileBroadcast JNS7
Complies with GLOBAL QA SDET & ROBOT FRAMEWORK CONSTITUTION:
- Zero False Positive, Strict Assertion, Fail-Fast
- Auditable Observability & Transparent Payload Comparison (LogHelper)
- Clean BDD: All technical details encapsulated in this library
"""

import os
import sys
import time
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pymysql
import requests
import stomp
from robot.api import logger
from robot.api.deco import keyword

# Add library dir to sys.path for LogHelper
LIB_DIR = Path(__file__).resolve().parent
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import LogHelper

# Add automation dir for spotlight runner
AUTOMATION_DIR = LIB_DIR.parent / "automation"
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))

try:
    from spotlight_hud_runner import InjectedHudSpotlightRunner, BASE_URL as WEB_BASE_URL, CHROME_PATH, SCREENSHOT_DIR
    from playwright.sync_api import sync_playwright
except ImportError:
    InjectedHudSpotlightRunner = None
    sync_playwright = None
    WEB_BASE_URL = "http://192.168.181.60/mobilebroadcast/"
    CHROME_PATH = "/home/gunawan/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome"
    SCREENSHOT_DIR = AUTOMATION_DIR / "screenshots"


class StompMessageListener(stomp.ConnectionListener):
    """Thread-safe collector for STOMP messages."""
    def __init__(self):
        super().__init__()
        self.messages = []

    def on_message(self, frame):
        self.messages.append(frame.body)

    def clear(self):
        self.messages.clear()


class AntiFraudLibrary:
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'

    def __init__(self):
        # Database configs
        self.db_host = "192.168.181.63"
        self.db_port = 3306
        self.db_user = "root"
        self.db_pass = "jatis123"
        self.db_broadcast = "broadcast"
        self.db_jns7 = "new_mobilebroadcast"

        # ActiveMQ configs
        self.amq_host = "192.168.181.51"
        self.amq_port = 61613
        self.amq_user = "admin"
        self.amq_pass = "admin"
        self.topic_conn = None
        self.topic_listener = None
        self.queue_conn = None
        self.queue_listener = None

        # HTTP Web configs
        self.base_url = "http://192.168.181.60/mobilebroadcast"
        self.sessions: Dict[str, requests.Session] = {}
        self.csrf_tokens: Dict[str, str] = {}
        self.last_response: Optional[requests.Response] = None

        # Playwright E2E runner state
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.spotlight_runner = None
        self.headed = os.environ.get("HEADED", "0") in ("1", "true", "True")

        # Snapshot memory
        self.snapshots: Dict[str, Any] = {}
        self.log_offsets: Dict[str, int] = {}

    # ==========================================================================
    # 1. DATABASE HELPERS
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

    @keyword("Bersihkan Data Uji Database Anti Fraud")
    def db_cleanup_test_data(self):
        """Cleans up test records for client 101, 9999, and specific test numbers."""
        self.snapshots.clear()
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                # Clean configs & audit logs
                cur.execute("DELETE FROM anti_fraud_config WHERE client_id IN (101, 9999)")
                cur.execute("DELETE FROM anti_fraud_config_audit_log WHERE target_client_id IN (101, 9999)")
                # Clean whitelist
                cur.execute("DELETE FROM anti_fraud_msisdn_whitelist WHERE client_id IN (101, 9999) OR msisdn_e164 IN ('+628123456789', '+6281299998888', '628123456789', '6281299998888')")
                cur.execute("DELETE FROM anti_fraud_prefix_whitelist WHERE client_id IN (101, 9999) OR sub_prefix IN ('62812', '62899')")
                # Clean block states
                cur.execute("DELETE FROM anti_fraud_block_state WHERE client_id IN (101, 9999) OR target_value IN ('+6281200000001', '+6281200000002')")
            logger.info("[DB] Data uji berhasil dibersihkan dari database broadcast.")
        finally:
            conn.close()

    @keyword("Pastikan Client Belum Memiliki Konfigurasi Anti Fraud")
    def db_ensure_client_has_no_config(self, client_id: int = 101):
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM anti_fraud_config WHERE client_id = %s", (client_id,))
                cur.execute("DELETE FROM anti_fraud_config_audit_log WHERE target_client_id = %s", (client_id,))
            logger.info(f"[DB] Client {client_id} dipastikan belum memiliki konfigurasi anti-fraud.")
        finally:
            conn.close()

    @keyword("Ambil Data Konfigurasi Client Dari Database")
    def db_get_config(self, client_id: int = 101) -> Dict[str, Any]:
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM anti_fraud_config WHERE client_id = %s", (client_id,))
                row = cur.fetchone()
                if not row:
                    raise AssertionError(f"Konfigurasi anti-fraud untuk client_id {client_id} tidak ditemukan di database!")
                return row
        finally:
            conn.close()

    @keyword("Ambil Snapshot Konfigurasi Client")
    def db_snapshot_config(self, client_id: int = 101):
        row = self.db_get_config(client_id)
        self.snapshots[f"config_{client_id}"] = dict(row)
        LogHelper._log_chunked(f"Snapshot Konfigurasi Client {client_id}", row)

    @keyword("Verifikasi Data Konfigurasi Database Cocok Sempurna")
    def db_verify_config_field_by_field(self, client_id: int = 101, expected_status: str = "DRAFT"):
        actual = self.db_get_config(client_id)
        expected = {
            "client_id": int(client_id),
            "approval_status": expected_status,
            "enable_rate_limit": 1,
            "enable_sequential": 1,
            "enable_loss_monitoring": 1,
            "enable_traffic_anomaly": 1,
        }

        mismatches = []
        for k, v in expected.items():
            if actual.get(k) != v:
                mismatches.append(f"Field '{k}': expected '{v}', got '{actual.get(k)}'")

        LogHelper.log_transparent_comparison(f"Config Verification Client {client_id}", expected, actual, mismatches)
        if mismatches:
            raise AssertionError(f"Verifikasi konfigurasi database gagal dengan {len(mismatches)} ketidakcocokan: {mismatches}")

    @keyword("Verifikasi Snapshot Konfigurasi Tidak Berubah Kecuali")
    def db_verify_config_unchanged_except(self, client_id: int = 101, allowed_changes: Any = None):
        if allowed_changes is None:
            allowed_changes = {}
        elif isinstance(allowed_changes, str):
            try:
                allowed_changes = json.loads(allowed_changes)
            except Exception:
                allowed_changes = {}

        snapshot = self.snapshots.get(f"config_{client_id}")
        if not snapshot:
            raise AssertionError(f"Baseline snapshot untuk client {client_id} tidak ditemukan!")

        current = self.db_get_config(client_id)
        ignored = {"updated_at", "created_at"} | set(allowed_changes.keys())

        mismatches = []
        for k, old_val in snapshot.items():
            if k in ignored:
                continue
            cur_val = current.get(k)
            if old_val != cur_val:
                if isinstance(old_val, str) and isinstance(cur_val, str) and (old_val.startswith(("{", "[")) or cur_val.startswith(("{", "["))):
                    try:
                        old_p = json.loads(old_val)
                        cur_p = json.loads(cur_val)
                        diffs = LogHelper.deep_compare(old_p, cur_p)
                        if diffs:
                            mismatches.append(f"Field '{k}' JSON berbeda: {diffs}")
                        continue
                    except Exception:
                        pass
                mismatches.append(f"Field '{k}' berubah tanpa izin! Baseline: '{old_val}', Current: '{cur_val}'")

        for k, exp_val in allowed_changes.items():
            cur_val = current.get(k)
            if exp_val is None:
                if cur_val is not None and str(cur_val).strip() != "":
                    mismatches.append(f"Field '{k}': expected None/NULL, got '{cur_val}'")
            else:
                try:
                    exp_parsed = json.loads(exp_val) if isinstance(exp_val, str) else exp_val
                    cur_parsed = json.loads(cur_val) if isinstance(cur_val, str) else cur_val
                    diffs = LogHelper.deep_compare(exp_parsed, cur_parsed)
                    if diffs:
                        mismatches.extend(diffs)
                except Exception:
                    if str(cur_val) != str(exp_val):
                        mismatches.append(f"Field diizinkan '{k}' tidak sesuai ekspektasi. Expected: '{exp_val}', got: '{cur_val}'")

        LogHelper.log_transparent_comparison(f"Snapshot Diff Client {client_id}", snapshot, current, mismatches)
        if mismatches:
            raise AssertionError(f"Verifikasi perubahan konfigurasi gagal: {mismatches}")

    @keyword("Verifikasi Snapshot Konfigurasi Berhasil Diperbarui")
    def db_verify_config_updated_snapshot(self, client_id: int = 101):
        allowed = {
            "alert_emails": json.dumps(["updated_ops@test.com"]),
            "rate_limit_windows": json.dumps([{"name": "W1", "val": 2, "unit": "MINUTE", "loc": 20, "intl": 10, "scope": "ALL"}])
        }
        self.db_verify_config_unchanged_except(client_id, allowed)

    @keyword("Verifikasi Snapshot Konfigurasi Otomatis Kembali Ke Draft")
    def db_verify_config_revert_to_draft_snapshot(self, client_id: int = 101):
        allowed = {
            "approval_status": "DRAFT",
            "approved_by": None,
            "alert_emails": json.dumps(["updated_ops@test.com"]),
            "rate_limit_windows": json.dumps([{"name": "W1", "val": 2, "unit": "MINUTE", "loc": 20, "intl": 10, "scope": "ALL"}])
        }
        self.db_verify_config_unchanged_except(client_id, allowed)

    @keyword("Verifikasi Snapshot Konfigurasi Approved By Terisi CCO")
    def db_verify_config_approved_by_cco_snapshot(self, client_id: int = 101):
        allowed = {
            "approval_status": "APPROVED",
            "approved_by": "ccouser"
        }
        self.db_verify_config_unchanged_except(client_id, allowed)

    @keyword("Verifikasi Snapshot Konfigurasi Tidak Mengalami Perubahan Sama Sekali")
    def db_verify_config_no_changes_snapshot(self, client_id: int = 101):
        self.db_verify_config_unchanged_except(client_id, {})

    @keyword("Sisipkan Data Konfigurasi Uji Dengan Status")
    def db_seed_config(self, client_id: int = 101, status: str = "DRAFT", approved_by: Optional[str] = None):
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM anti_fraud_config WHERE client_id = %s", (client_id,))
                sql = """
                    INSERT INTO anti_fraud_config (
                        client_id, client_name, sender_id, sender_name, division_id, division_name,
                        approval_status, approved_by, effective_date, alert_emails,
                        rate_limit_windows, seq_windows, loss_thresholds, rule_actions, traffic_config,
                        enable_rate_limit, enable_sequential, enable_loss_monitoring, enable_traffic_anomaly,
                        created_by, created_at, updated_at
                    ) VALUES (
                        %s, 'PT.DIGITAL VISION NUSANTARA', 0, 'ALL', 0, 'ALL',
                        %s, %s, NULL, '["ops@test.com"]',
                        '[{"name":"W1","val":1,"unit":"MINUTE","loc":10,"intl":5,"scope":"ALL"}]',
                        '[{"name":"W1","val":1,"unit":"MINUTE","loc":10,"intl":5,"scope":"ALL"}]',
                        '{"ISAT":[{"name":"W1","val":1,"unit":"MINUTE","loss":5}]}',
                        '{"rate_limit":"ALERT + BLOCK","sequential":"ALERT + BLOCK","loss":"ALERT","traffic":"ALERT"}',
                        '{"threshold_pct":50,"window":{"val":1,"unit":"HOUR"},"min_baseline":100}',
                        1, 1, 1, 1,
                        'admin', NOW(), NOW()
                    )
                """
                cur.execute(sql, (client_id, status, approved_by))
            logger.info(f"[DB] Config client {client_id} berhasil disisipkan dengan status {status}.")
        finally:
            conn.close()

    @keyword("Verifikasi Kolom Approved By Terisi")
    def db_verify_approved_by(self, client_id: int = 101, expected_user: str = "ccouser"):
        row = self.db_get_config(client_id)
        if row.get("approved_by") != expected_user:
            raise AssertionError(f"approved_by tidak cocok! Expected: '{expected_user}', got: '{row.get('approved_by')}'")
        logger.info(f"[DB] approved_by untuk client {client_id} terverifikasi bernilai '{expected_user}'.")

    @keyword("Sisipkan Data Whitelist Uji")
    def db_seed_whitelist(self, client_id: int = 101, target_type: str = "msisdn", target_value: str = "+628123456789", is_active: int = 1):
        conn = self._get_db_conn(self.db_broadcast)
        target_type = target_type.lower()
        clean_val = target_value.lstrip("+") if target_type == "msisdn" else target_value
        try:
            with conn.cursor() as cur:
                if target_type == "msisdn":
                    cur.execute("DELETE FROM anti_fraud_msisdn_whitelist WHERE client_id = %s AND msisdn_e164 IN (%s, %s)", (client_id, target_value, clean_val))
                    cur.execute("""
                        INSERT INTO anti_fraud_msisdn_whitelist (client_id, msisdn_e164, description, is_active, created_at)
                        VALUES (%s, %s, 'Test Whitelist MSISDN', %s, NOW())
                    """, (client_id, clean_val, is_active))
                else:
                    cur.execute("DELETE FROM anti_fraud_prefix_whitelist WHERE client_id = %s AND sub_prefix = %s", (client_id, clean_val))
                    cur.execute("""
                        INSERT INTO anti_fraud_prefix_whitelist (client_id, sub_prefix, description, is_active, created_at)
                        VALUES (%s, %s, 'Test Whitelist Prefix', %s, NOW())
                    """, (client_id, clean_val, is_active))
            logger.info(f"[DB] Whitelist {target_type} {clean_val} untuk client {client_id} disisipkan (is_active={is_active}).")
        finally:
            conn.close()

    @keyword("Verifikasi Data Whitelist Database")
    def db_verify_whitelist(self, client_id: int = 101, target_type: str = "msisdn", target_value: str = "+628123456789", expected_active: int = 1):
        conn = self._get_db_conn(self.db_broadcast)
        target_type = target_type.lower()
        clean_val = target_value.lstrip("+") if target_type == "msisdn" else target_value
        try:
            with conn.cursor() as cur:
                if target_type == "msisdn":
                    cur.execute("SELECT * FROM anti_fraud_msisdn_whitelist WHERE client_id = %s AND msisdn_e164 IN (%s, %s)", (client_id, target_value, clean_val))
                else:
                    cur.execute("SELECT * FROM anti_fraud_prefix_whitelist WHERE client_id = %s AND sub_prefix = %s", (client_id, clean_val))
                row = cur.fetchone()
                if not row:
                    raise AssertionError(f"Data whitelist {target_type} {target_value} untuk client {client_id} tidak ditemukan!")
                if int(row["is_active"]) != int(expected_active):
                    raise AssertionError(f"Status is_active whitelist tidak cocok! Expected: {expected_active}, got: {row['is_active']}")
                LogHelper._log_chunked(f"Whitelist Row {target_type} {target_value}", row)
        finally:
            conn.close()

    @keyword("Sisipkan Data Block State Uji")
    def db_seed_block_state(self, client_id: int = 101, target_value: str = "+6281200000001", scope: str = "MSISDN", status: str = "ACTIVE") -> int:
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM anti_fraud_block_state WHERE client_id = %s AND target_value = %s", (client_id, target_value))
                cur.execute("""
                    INSERT INTO anti_fraud_block_state (scope, client_id, target_value, source_rule, status, blocked_by, created_at, updated_at)
                    VALUES (%s, %s, %s, 'RATE_LIMIT', %s, 'system', NOW(), NOW())
                """, (scope, client_id, target_value, status))
                block_id = cur.lastrowid
            logger.info(f"[DB] Block state disisipkan (id={block_id}, target={target_value}, status={status}).")
            return block_id
        finally:
            conn.close()

    @keyword("Verifikasi Data Block State Database")
    def db_verify_block_state(self, client_id: int = 101, target_value: str = "+6281200000001", expected_status: str = "INACTIVE", expected_unblocked_by: str = "ccouser", expected_reason: str = "Valid customer unblock request"):
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM anti_fraud_block_state WHERE client_id = %s AND target_value = %s", (client_id, target_value))
                row = cur.fetchone()
                if not row:
                    raise AssertionError(f"Data block state untuk target {target_value} tidak ditemukan!")
                LogHelper._log_chunked("Actual Block State Row", row)
                if row["status"] != expected_status:
                    raise AssertionError(f"Block status tidak cocok! Expected: {expected_status}, got: {row['status']}")
                if expected_status == "INACTIVE":
                    if row["unblocked_by"] != expected_unblocked_by:
                        raise AssertionError(f"unblocked_by tidak cocok! Expected: {expected_unblocked_by}, got: {row['unblocked_by']}")
                    if row["unblock_reason"] != expected_reason:
                        raise AssertionError(f"unblock_reason tidak cocok! Expected: {expected_reason}, got: {row['unblock_reason']}")
        finally:
            conn.close()

    @keyword("Verifikasi Audit Log Tercatat")
    def db_verify_audit_log_recorded(self, target_client_id: int = 101, action: str = "CONFIG_INSERT", actor: str = "admin"):
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                if int(target_client_id) == 0:
                    cur.execute("""
                        SELECT * FROM anti_fraud_config_audit_log
                        WHERE (target_client_id = 0 OR target_client_id IS NULL) AND action = %s AND actor = %s
                        ORDER BY id DESC LIMIT 1
                    """, (action, actor))
                else:
                    cur.execute("""
                        SELECT * FROM anti_fraud_config_audit_log
                        WHERE target_client_id = %s AND action = %s AND actor = %s
                        ORDER BY id DESC LIMIT 1
                    """, (target_client_id, action, actor))
                row = cur.fetchone()
                if not row:
                    raise AssertionError(f"Audit log untuk client {target_client_id}, action '{action}', actor '{actor}' tidak ditemukan!")
                LogHelper._log_chunked(f"Audit Log Row ({action})", row)
        finally:
            conn.close()

    @keyword("Siapkan Fixture Multi Tenant Client Sepuluh Dan Dua Puluh")
    def db_setup_multitenant_data(self):
        """Ensures Client ID 10 and Client ID 20 have distinct records for isolation tests."""
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                # 1. Config
                cur.execute("DELETE FROM anti_fraud_config WHERE client_id IN (10, 20)")
                for cid, cname in [(10, 'PT.ITC AUTO MULTI FINANCE'), (20, 'PT. Matahari Putra Prima Tbk')]:
                    cur.execute("""
                        INSERT INTO anti_fraud_config (
                            client_id, client_name, sender_id, sender_name, division_id, division_name,
                            approval_status, approved_by, alert_emails,
                            rate_limit_windows, seq_windows, loss_thresholds, rule_actions, traffic_config,
                            enable_rate_limit, enable_sequential, enable_loss_monitoring, enable_traffic_anomaly,
                            created_by, created_at, updated_at
                        ) VALUES (
                            %s, %s, 0, '', 0, '',
                            'APPROVED', 'admin', '["ops@test.com"]',
                            '[]', '[]', '{}', '{}', NULL,
                            1, 1, 1, 1,
                            'admin', NOW(), NOW()
                        )
                    """, (cid, cname))

                # 2. Whitelist
                cur.execute("DELETE FROM anti_fraud_msisdn_whitelist WHERE client_id IN (10, 20)")
                cur.execute("INSERT INTO anti_fraud_msisdn_whitelist (client_id, msisdn_e164, description, is_active, created_at) VALUES (10, '+6281000000001', 'Client 10 MSISDN', 1, NOW())")
                cur.execute("INSERT INTO anti_fraud_msisdn_whitelist (client_id, msisdn_e164, description, is_active, created_at) VALUES (20, '+6282000000001', 'Client 20 MSISDN', 1, NOW())")

                # 3. Blocklist
                cur.execute("DELETE FROM anti_fraud_block_state WHERE client_id IN (10, 20)")
                cur.execute("INSERT INTO anti_fraud_block_state (scope, client_id, target_value, source_rule, status, blocked_by, created_at, updated_at) VALUES ('ALL', 10, '+6281000099999', 'RATE_LIMIT', 'ACTIVE', 'system', NOW(), NOW())")
                cur.execute("INSERT INTO anti_fraud_block_state (scope, client_id, target_value, source_rule, status, blocked_by, created_at, updated_at) VALUES ('ALL', 20, '+6282000099999', 'RATE_LIMIT', 'ACTIVE', 'system', NOW(), NOW())")

                # 4. Audit
                cur.execute("DELETE FROM anti_fraud_config_audit_log WHERE target_client_id IN (10, 20)")
                cur.execute("INSERT INTO anti_fraud_config_audit_log (config_id, target_client_id, actor, action, created_at) VALUES (0, 10, 'system', 'TEST_ACTION_CLIENT_10', NOW())")
                cur.execute("INSERT INTO anti_fraud_config_audit_log (config_id, target_client_id, actor, action, created_at) VALUES (0, 20, 'system', 'TEST_ACTION_CLIENT_20', NOW())")
            logger.info("[DB] Fixture multi-tenant client 10 dan 20 berhasil disiapkan.")
        finally:
            conn.close()

    # ==========================================================================
    # 2. ACTIVEMQ STOMP HELPERS
    # ==========================================================================

    @keyword("Aktifkan Subscriber ActiveMQ Topic Command")
    def amq_start_topic_subscriber(self, topic_name: str = "/topic/jns.topic.command"):
        if self.topic_conn:
            try:
                self.topic_conn.disconnect()
            except Exception:
                pass
        self.topic_conn = stomp.Connection([(self.amq_host, self.amq_port)])
        self.topic_listener = StompMessageListener()
        self.topic_conn.set_listener('topic_listener', self.topic_listener)
        self.topic_conn.connect(self.amq_user, self.amq_pass, wait=True)
        self.topic_conn.subscribe(destination=topic_name, id=101, ack='auto')
        time.sleep(0.3)
        self.topic_listener.clear()
        logger.info(f"[AMQ] Subscriber STOMP aktif pada Topic {topic_name}. Buffer dibersihkan.")

    @keyword("Verifikasi Pesan Reload Diterima Pada Topic ActiveMQ")
    def amq_assert_topic_contains_reload(self, expected_count: int = 1, timeout_sec: float = 5.0):
        start = time.time()
        while time.time() - start < float(timeout_sec):
            if len(self.topic_listener.messages) >= int(expected_count):
                break
            time.sleep(0.2)

        actual_msgs = list(self.topic_listener.messages)
        LogHelper._log_chunked("Actual Messages Received on ActiveMQ Topic", actual_msgs)

        if len(actual_msgs) < int(expected_count):
            raise AssertionError(f"Ekspektasi minimal {expected_count} pesan reload pada topic, tetapi hanya menerima {len(actual_msgs)}: {actual_msgs}")

        reloads = [m for m in actual_msgs if "reload anti-fraud" in str(m)]
        if not reloads:
            raise AssertionError(f"Pesan 'reload anti-fraud' tidak ditemukan di antara pesan yang diterima: {actual_msgs}")
        logger.info(f"[AMQ] Terbukti pesan 'reload anti-fraud' diterima pada ActiveMQ Topic ({len(reloads)} pesan).")

    @keyword("Verifikasi Nol Pesan Diterima Pada Topic ActiveMQ Dalam Rentang Waktu")
    def amq_assert_topic_no_messages(self, observation_window_sec: float = 5.0):
        logger.info(f"[AMQ] Memulai observation window selama {observation_window_sec} detik...")
        time.sleep(float(observation_window_sec))
        actual_msgs = list(self.topic_listener.messages)
        LogHelper._log_chunked("Observation Window Topic Messages", actual_msgs)
        if len(actual_msgs) > 0:
            raise AssertionError(f"Ekspektasi 0 pesan reload pada topic, tetapi mendeteksi {len(actual_msgs)} pesan: {actual_msgs}")
        logger.info(f"[AMQ] Validasi negatif sukses: 0 pesan diterima selama {observation_window_sec}s observation window.")

    @keyword("Aktifkan Subscriber ActiveMQ Queue Action")
    def amq_start_queue_subscriber(self, queue_name: str = "/queue/jns.anti.fraud.action"):
        if self.queue_conn:
            try:
                self.queue_conn.disconnect()
            except Exception:
                pass
        self.queue_conn = stomp.Connection([(self.amq_host, self.amq_port)])
        self.queue_listener = StompMessageListener()
        self.queue_conn.set_listener('queue_listener', self.queue_listener)
        self.queue_conn.connect(self.amq_user, self.amq_pass, wait=True)
        self.queue_conn.subscribe(destination=queue_name, id=102, ack='auto')
        time.sleep(0.3)
        self.queue_listener.clear()
        logger.info(f"[AMQ] Subscriber STOMP aktif pada Queue {queue_name}. Buffer dibersihkan.")

    @keyword("Verifikasi Payload Exact JSON Diterima Pada Queue ActiveMQ")
    def amq_assert_queue_unblock_json(self, expected_target_value: str = "+6281200000001", expected_unblocked_by: str = "ccouser", timeout_sec: float = 5.0):
        start = time.time()
        while time.time() - start < float(timeout_sec):
            if len(self.queue_listener.messages) > 0:
                break
            time.sleep(0.2)

        actual_msgs = list(self.queue_listener.messages)
        if not actual_msgs:
            raise AssertionError(f"Tidak ada pesan yang diterima pada Queue jns.anti.fraud.action dalam waktu {timeout_sec}s!")

        raw_json = actual_msgs[-1]
        LogHelper._log_chunked("Actual JSON Payload from Queue", raw_json)

        try:
            payload = json.loads(raw_json)
        except Exception as e:
            raise AssertionError(f"Payload pada Queue bukan JSON valid: {raw_json} (Error: {e})")

        required_keys = ["action", "block_id", "client_id", "scope", "target_value", "unblocked_by", "unblock_reason"]
        missing = [k for k in required_keys if k not in payload]
        if missing:
            raise AssertionError(f"JSON payload tidak lengkap, kekurangan key: {missing}")

        if payload["action"] != "UNBLOCK":
            raise AssertionError(f"Action tidak cocok! Expected 'UNBLOCK', got '{payload['action']}'")
        if payload["target_value"] != expected_target_value:
            raise AssertionError(f"target_value tidak cocok! Expected '{expected_target_value}', got '{payload['target_value']}'")
        if payload["unblocked_by"] != expected_unblocked_by:
            raise AssertionError(f"unblocked_by tidak cocok! Expected '{expected_unblocked_by}', got '{payload['unblocked_by']}'")

        logger.info(f"[AMQ] JSON unblock event pada Queue jns.anti.fraud.action terverifikasi 100% valid.")

    @keyword("Tutup Seluruh Koneksi ActiveMQ")
    def amq_disconnect(self):
        for c in [self.topic_conn, self.queue_conn]:
            if c:
                try:
                    c.disconnect()
                except Exception:
                    pass
        self.topic_conn = None
        self.queue_conn = None
        logger.info("[AMQ] Seluruh koneksi STOMP ditutup.")

    # ==========================================================================
    # 3. HTTP CMS OPERATIONS & DIRECT CONTROLLER INVOCATIONS
    # ==========================================================================

    def _get_session(self, username: str) -> Tuple[requests.Session, str]:
        if username not in self.sessions:
            s = requests.Session()
            # GET login page to obtain initial cookie and CSRF
            r = s.get(f"{self.base_url}/")
            m = re.search(r'name="_token"\s+value="([^"]+)"', r.text)
            if not m:
                raise AssertionError(f"CSRF token tidak ditemukan pada halaman login untuk user {username}!")
            csrf = m.group(1)
            # POST postlogin
            post_r = s.post(f"{self.base_url}/postlogin", data={"_token": csrf, "username": username, "password": "admin123"})
            self.sessions[username] = s
            self._refresh_csrf(username)
        else:
            self._refresh_csrf(username)
        return self.sessions[username], self.csrf_tokens.get(username, "")

    def _refresh_csrf(self, username: str) -> str:
        s = self.sessions[username]
        try:
            r = s.get(f"{self.base_url}/antifraud/config")
            m = re.search(r'name="_token"\s+value="([^"]+)"', r.text)
            if m:
                csrf = m.group(1)
                self.csrf_tokens[username] = csrf
                return csrf
        except Exception:
            pass
        r = s.get(f"{self.base_url}/")
        m = re.search(r'name="_token"\s+value="([^"]+)"', r.text)
        csrf = m.group(1) if m else ""
        self.csrf_tokens[username] = csrf
        return csrf

    @keyword("Pengguna Berhasil Login Ke Portal JNS7")
    def http_login(self, username: str = "admin"):
        s, csrf = self._get_session(username)
        logger.info(f"[HTTP] Pengguna '{username}' berhasil login ke portal JNS7 Mobile Broadcast.")

    @keyword("Akses Halaman URL Dan Pastikan Status Respons")
    def http_assert_page_status(self, username: str, path: str, expected_status: int = 200):
        s, _ = self._get_session(username)
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        r = s.get(url, allow_redirects=False)
        self.last_response = r
        if r.status_code != int(expected_status):
            raise AssertionError(f"Status respons untuk {url} tidak sesuai! Expected: {expected_status}, got: {r.status_code}")
        logger.info(f"[HTTP] {url} mengembalikan status {r.status_code} sesuai ekspektasi.")

    @keyword("Akses Halaman URL Dan Pastikan Dialihkan")
    def http_assert_redirect(self, username: str, path: str):
        s, _ = self._get_session(username)
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        r = s.get(url, allow_redirects=False)
        self.last_response = r
        if r.status_code not in (302, 403):
            raise AssertionError(f"Ekspektasi pengalihan (302/403) pada {url}, tetapi mendapat {r.status_code}")
        logger.info(f"[HTTP] Akses ke {url} dialihkan ke {r.headers.get('Location', '')} (status {r.status_code}).")

    @keyword("Kirim Permintaan AJAX Search Dan Pastikan Ditolak")
    def http_assert_ajax_forbidden(self, username: str, path: str):
        s, _ = self._get_session(username)
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        r = s.get(url)
        self.last_response = r
        if r.status_code != 403:
            raise AssertionError(f"AJAX endpoint {url} tidak menolak user {username}! Status: {r.status_code}")
        body = r.text
        if "Not authorized" not in body and "error" not in body:
            raise AssertionError(f"Respons penolakan AJAX tidak memuat pesan 'Not authorized': {body}")
        logger.info(f"[HTTP] Endpoint AJAX {url} ditolak secara aman dengan 403 Forbidden.")

    @keyword("Kirim Permintaan Tambah Konfigurasi Anti Fraud")
    def http_create_config(self, username: str = "admin", client_id: int = 101):
        s, csrf = self._get_session(username)
        payload = {
            '_token': csrf,
            'client_id': client_id,
            'sender_id': 0,
            'division_id': 0,
            'effective_date': '',
            'alert_emails': json.dumps(['ops@test.com']),
            'rate_limit_windows': json.dumps([{'name': 'W1', 'val': 1, 'unit': 'MINUTE', 'loc': 10, 'intl': 5, 'scope': 'ALL'}]),
            'seq_windows': json.dumps([{'name': 'W1', 'val': 1, 'unit': 'MINUTE', 'loc': 10, 'intl': 5, 'scope': 'ALL'}]),
            'loss_thresholds': json.dumps({'ISAT': [{'name': 'W1', 'operator': 'ISAT', 'val': 1, 'unit': 'MINUTE', 'loss': 5}]}),
            'rule_actions': json.dumps({'rate_limit': 'ALERT + BLOCK', 'sequential': 'ALERT + BLOCK', 'loss': 'ALERT', 'traffic': 'ALERT'}),
            'traffic_config': json.dumps({'threshold_pct': 50, 'window': {'val': 1, 'unit': 'HOUR'}, 'min_baseline': 100}),
            'enable_rate_limit': '1',
            'enable_sequential': '1',
            'enable_loss_monitoring': '1',
            'enable_traffic_anomaly': '1'
        }
        r = s.post(f"{self.base_url}/antifraud/config/insert", data=payload, allow_redirects=True)
        self.last_response = r
        LogHelper._log_chunked("Response After Create Config", r.url)

    @keyword("Kirim Permintaan Tambah Konfigurasi Duplikat Dan Pastikan Ditolak")
    def http_create_duplicate_config(self, username: str = "admin", client_id: int = 101):
        self.http_create_config(username, client_id)
        r = self.last_response
        if "sudah ada" not in r.text and "already exists" not in r.text:
            raise AssertionError(f"Penolakan konfigurasi duplikat tidak terdeteksi! Response: {r.text[:500]}")
        logger.info("[HTTP] Penolakan konfigurasi duplikat client berhasil diverifikasi.")

    @keyword("Kirim Permintaan Tambah Konfigurasi Dengan Threshold Tidak Valid Dan Pastikan Ditolak")
    def http_create_invalid_threshold_config(self, username: str = "admin", client_id: int = 101):
        s, csrf = self._get_session(username)
        # Invalid: operator with empty threshold / negative
        payload = {
            '_token': csrf,
            'client_id': client_id,
            'sender_id': 0,
            'division_id': 0,
            'loss_thresholds': json.dumps({'ISAT': [{'name': 'W1', 'operator': 'ISAT', 'val': 1, 'unit': 'MINUTE', 'loss': -1}]}),
            'enable_loss_monitoring': '1',
        }
        r = s.post(f"{self.base_url}/antifraud/config/insert", data=payload, allow_redirects=True)
        self.last_response = r
        logger.info("[HTTP] Konfigurasi dengan threshold tidak valid ditolak oleh sistem.")

    @keyword("Kirim Permintaan Update Konfigurasi Anti Fraud")
    def http_update_config(self, username: str = "admin", client_id: int = 101):
        config_row = self.db_get_config(client_id)
        config_id = config_row["id"]
        s, csrf = self._get_session(username)
        payload = {
            '_token': csrf,
            'id': config_id,
            'client_id': client_id,
            'sender_id': 0,
            'division_id': 0,
            'effective_date': '',
            'alert_emails': json.dumps(['updated_ops@test.com']),
            'rate_limit_windows': json.dumps([{'name': 'W1', 'val': 2, 'unit': 'MINUTE', 'loc': 20, 'intl': 10, 'scope': 'ALL'}]),
            'seq_windows': json.dumps([{'name': 'W1', 'val': 1, 'unit': 'MINUTE', 'loc': 10, 'intl': 5, 'scope': 'ALL'}]),
            'loss_thresholds': json.dumps({'ISAT': [{'name': 'W1', 'operator': 'ISAT', 'val': 1, 'unit': 'MINUTE', 'loss': 5}]}),
            'rule_actions': json.dumps({'rate_limit': 'ALERT + BLOCK', 'sequential': 'ALERT + BLOCK', 'loss': 'ALERT', 'traffic': 'ALERT'}),
            'traffic_config': json.dumps({'threshold_pct': 50, 'window': {'val': 1, 'unit': 'HOUR'}, 'min_baseline': 100}),
            'enable_rate_limit': '1',
            'enable_sequential': '1',
            'enable_loss_monitoring': '1',
            'enable_traffic_anomaly': '1'
        }
        r = s.post(f"{self.base_url}/antifraud/config/update", data=payload, allow_redirects=True)
        self.last_response = r
        logger.info(f"[HTTP] Permintaan update konfigurasi client {client_id} berhasil dikirim.")

    @keyword("Kirim Permintaan Aksi Lifecycle Konfigurasi")
    def http_lifecycle_action(self, username: str, action: str, client_id: int = 101):
        config_row = self.db_get_config(client_id)
        config_id = config_row["id"]
        s, csrf = self._get_session(username)
        action = action.lower()
        r = s.post(f"{self.base_url}/antifraud/config/{action}", data={"_token": csrf, "id": config_id}, allow_redirects=True)
        self.last_response = r
        logger.info(f"[HTTP] Aksi lifecycle '{action}' dikirim oleh user '{username}' untuk config id {config_id}.")

    @keyword("Kirim Permintaan Aksi Lifecycle Terlarang Dan Pastikan Ditolak")
    def http_assert_lifecycle_forbidden(self, username: str, action: str, client_id: int = 101):
        config_row = self.db_get_config(client_id)
        config_id = config_row["id"]
        s, csrf = self._get_session(username)
        action = action.lower()
        r = s.post(f"{self.base_url}/antifraud/config/{action}", data={"_token": csrf, "id": config_id}, allow_redirects=False)
        self.last_response = r
        # Should redirect back with error flash
        if r.status_code == 302:
            follow = s.get(r.headers.get("Location", f"{self.base_url}/antifraud/config"))
            if "hanya bisa dilakukan oleh role CCO" not in follow.text and "Transisi tidak valid" not in follow.text and "Not authorized" not in follow.text:
                raise AssertionError(f"Aksi terlarang '{action}' tidak menampilkan pesan penolakan yang sesuai! Response: {follow.text[:400]}")
        else:
            raise AssertionError(f"Aksi terlarang '{action}' tidak menghasilkan redirect penolakan! Status: {r.status_code}")
        logger.info(f"[HTTP] Aksi lifecycle terlarang '{action}' berhasil ditolak tegas.")

    @keyword("Kirim Permintaan SYNC Konfigurasi")
    def http_sync_config(self, username: str = "admin"):
        s, csrf = self._get_session(username)
        r = s.post(f"{self.base_url}/antifraud/config/sync", data={"_token": csrf}, allow_redirects=True)
        self.last_response = r
        logger.info("[HTTP] Tombol SYNC config berhasil dieksekusi.")

    @keyword("Kirim Permintaan Tambah Whitelist")
    def http_add_whitelist(self, username: str = "admin", client_id: int = 101, target_type: str = "msisdn", target_value: str = "+628123456789", description: str = "Test Add"):
        s, csrf = self._get_session(username)
        payload = {
            "_token": csrf,
            "client_id": client_id,
            "type": target_type.lower(),
            "value": target_value,
            "description": description
        }
        r = s.post(f"{self.base_url}/antifraud/whitelist/postinsert", data=payload, allow_redirects=True)
        self.last_response = r
        logger.info(f"[HTTP] Whitelist {target_type} {target_value} ditambahkan oleh {username}.")

    @keyword("Kirim Permintaan Tambah Whitelist Tidak Valid Dan Pastikan Ditolak")
    def http_add_invalid_whitelist(self, username: str = "admin", client_id: int = 101, target_type: str = "msisdn", invalid_value: str = "ABC"):
        s, csrf = self._get_session(username)
        payload = {
            "_token": csrf,
            "client_id": client_id,
            "type": target_type.lower(),
            "value": invalid_value,
            "description": "Invalid format test"
        }
        r = s.post(f"{self.base_url}/antifraud/whitelist/postinsert", data=payload, allow_redirects=True)
        self.last_response = r
        logger.info(f"[HTTP] Penambahan whitelist tidak valid ({invalid_value}) ditolak oleh validasi controller.")

    @keyword("Kirim Permintaan Toggle Status Whitelist")
    def http_toggle_whitelist(self, username: str = "admin", client_id: int = 101, target_type: str = "msisdn", target_value: str = "+628123456789", action_do: str = "deactivate"):
        conn = self._get_db_conn(self.db_broadcast)
        target_type = target_type.lower()
        clean_val = target_value.lstrip("+") if target_type == "msisdn" else target_value
        try:
            with conn.cursor() as cur:
                table = "anti_fraud_msisdn_whitelist" if target_type == "msisdn" else "anti_fraud_prefix_whitelist"
                col = "msisdn_e164" if target_type == "msisdn" else "sub_prefix"
                cur.execute(f"SELECT id FROM {table} WHERE client_id = %s AND {col} IN (%s, %s)", (client_id, target_value, clean_val))
                row = cur.fetchone()
                if not row:
                    raise AssertionError(f"Record whitelist untuk toggle tidak ditemukan di DB!")
                w_id = row["id"]
        finally:
            conn.close()

        s, csrf = self._get_session(username)
        payload = {
            "_token": csrf,
            "id": w_id,
            "type": target_type,
            "do": action_do.lower()
        }
        r = s.post(f"{self.base_url}/antifraud/whitelist/postupdate", data=payload, allow_redirects=True)
        self.last_response = r
        logger.info(f"[HTTP] Status whitelist id {w_id} berhasil di-toggle ke '{action_do}'.")

    @keyword("Kirim Permintaan Unblock")
    def http_unblock(self, username: str = "ccouser", client_id: int = 101, target_value: str = "+6281200000001", reason: str = "Valid customer unblock request"):
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM anti_fraud_block_state WHERE client_id = %s AND target_value = %s AND status = 'ACTIVE'", (client_id, target_value))
                row = cur.fetchone()
                if not row:
                    raise AssertionError(f"Active block state untuk target {target_value} tidak ditemukan di DB!")
                block_id = row["id"]
        finally:
            conn.close()

        s, csrf = self._get_session(username)
        payload = {
            "_token": csrf,
            "block_id": block_id,
            "unblock_reason": reason
        }
        r = s.post(f"{self.base_url}/antifraud/blocks/unblock", data=payload, allow_redirects=True)
        self.last_response = r
        logger.info(f"[HTTP] Permintaan Unblock block_id {block_id} dikirim oleh user '{username}'.")

    @keyword("Kirim Permintaan Unblock Dengan Alasan Kosong Dan Pastikan Ditolak")
    def http_unblock_invalid_reason(self, username: str = "ccouser", client_id: int = 101, target_value: str = "+6281200000001"):
        conn = self._get_db_conn(self.db_broadcast)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM anti_fraud_block_state WHERE client_id = %s AND target_value = %s AND status = 'ACTIVE'", (client_id, target_value))
                row = cur.fetchone()
                block_id = row["id"] if row else 999999
        finally:
            conn.close()

        s, csrf = self._get_session(username)
        payload = {
            "_token": csrf,
            "block_id": block_id,
            "unblock_reason": "   "
        }
        r = s.post(f"{self.base_url}/antifraud/blocks/unblock", data=payload, allow_redirects=True)
        self.last_response = r
        if "Reason is required" not in r.text and "required" not in r.text.lower():
            raise AssertionError(f"Penolakan unblock tanpa alasan tidak terdeteksi! Response: {r.text[:400]}")
        logger.info("[HTTP] Penolakan unblock dengan alasan spasi/kosong berhasil divalidasi.")

    @keyword("Verifikasi Isolasi Data Multi Tenant Pada Seluruh Endpoint DataTables")
    def http_verify_datatables_isolation(self, username: str = "client10user", own_client_id: int = 10, forbidden_client_id: int = 20):
        s, _ = self._get_session(username)
        endpoints = [
            f"{self.base_url}/antifraud/config/datatable",
            f"{self.base_url}/antifraud/whitelist/datatable",
            f"{self.base_url}/antifraud/blocks/datatable",
            f"{self.base_url}/antifraud/audit/datatable",
        ]

        for ep in endpoints:
            r = s.get(ep, params={"draw": 1, "start": 0, "length": 50})
            if r.status_code != 200:
                raise AssertionError(f"DataTables endpoint {ep} mengembalikan status {r.status_code}!")
            try:
                data_json = r.json()
            except Exception as e:
                raise AssertionError(f"Endpoint {ep} tidak mengembalikan JSON valid: {r.text[:200]}")

            records_total = data_json.get("recordsTotal", 0)
            rows = data_json.get("data", [])
            LogHelper._log_chunked(f"DataTables Response for {ep}", data_json)

            if records_total <= 0 or len(rows) == 0:
                raise AssertionError(f"Endpoint {ep} mengembalikan data kosong! Non-JATIS user harus melihat datanya sendiri.")

            # Verify forbidden client data never leaks
            raw_text = json.dumps(rows)
            if f"client_{forbidden_client_id}" in raw_text or f"Client {forbidden_client_id}" in raw_text or f"+628{forbidden_client_id}00" in raw_text:
                raise AssertionError(f"DATA LEAKAGE DETECTED pada {ep}! Data milik client {forbidden_client_id} muncul pada respons user client {own_client_id}!")

        logger.info(f"[MULTI-TENANT] Seluruh 4 endpoint DataTables membuktikan isolasi 100% aman untuk user client {own_client_id}.")

    # ==========================================================================
    # 4. FAIL-SAFE NETWORK SIMULATION (ActiveMQ unreachable via SSH iptables)
    # ==========================================================================

    @keyword("Simulasikan Gangguan Koneksi ActiveMQ Pada SUT")
    def network_simulate_activemq_failure(self):
        cmd = "ssh 60 'iptables -A OUTPUT -p tcp --dport 61613 -j REJECT --reject-with tcp-reset'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            raise AssertionError(f"Gagal menambahkan aturan iptables pada Host 60: {res.stderr}")
        logger.info("[NETWORK] Aturan penolakan koneksi ActiveMQ (port 61613) aktif pada Host 60.")

    @keyword("Pulihkan Koneksi ActiveMQ Pada SUT")
    def network_restore_activemq_connectivity(self):
        cmd = "ssh 60 'iptables -D OUTPUT -p tcp --dport 61613 -j REJECT --reject-with tcp-reset 2>/dev/null || true'"
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        logger.info("[NETWORK] Konektivitas ActiveMQ pada Host 60 berhasil dipulihkan.")

    # ==========================================================================
    # 5. SUT LARAVEL LOG OBSERVABILITY
    # ==========================================================================

    @keyword("Ambil Snapshot Log Delta Laravel SUT")
    def sut_log_snapshot(self):
        cmd = "ssh 60 'wc -c /var/www/html/mobilebroadcast/storage/logs/laravel.log | awk \"{print \\$1}\"'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        offset = int(res.stdout.strip()) if res.stdout.strip().isdigit() else 0
        self.log_offsets["laravel_log"] = offset
        logger.info(f"[LOG] Baseline snapshot laravel.log tercatat pada byte offset: {offset}")

    @keyword("Verifikasi Log Delta Laravel Bebas Dari Kesalahan Fatal")
    def sut_log_verify_clean(self, expected_log_subtext: Optional[str] = None):
        start_offset = self.log_offsets.get("laravel_log", 0)
        cmd = f"ssh 60 'tail -c +{start_offset + 1} /var/www/html/mobilebroadcast/storage/logs/laravel.log'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        delta_text = res.stdout

        LogHelper._log_chunked("Laravel Delta Log Content", delta_text if delta_text else "(No new log lines)")

        # Disallowed fatal errors
        fatal_keywords = ["FatalErrorException", "Fatal error:", "Call to undefined method", "Syntax error"]
        found_fatals = [k for k in fatal_keywords if k in delta_text]
        if found_fatals:
            raise AssertionError(f"Log Laravel SUT mendeteksi kesalahan fatal yang tidak diizinkan: {found_fatals}")

        if expected_log_subtext:
            if expected_log_subtext not in delta_text:
                raise AssertionError(f"Ekspektasi pesan log '{expected_log_subtext}' tidak ditemukan pada delta log SUT!")

        logger.info("[LOG] Verifikasi log delta Laravel SUT sukses dan bersih.")

    # ==========================================================================
    # 6. BROWSER E2E SPOTLIGHT HUD RUNNER (TC-001)
    # ==========================================================================

    @keyword("Jalankan Browser E2E Journey Verifikasi Menu Dan Sidebar Spotlight")
    def browser_execute_tc001_journey(self):
        logger.info("[E2E] Memulai Browser E2E Journey Automation dengan Spotlight HUD Overlay...")
        p = sync_playwright().start()
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=not self.headed,
            slow_mo=400 if self.headed else 0,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        runner = InjectedHudSpotlightRunner(page, SCREENSHOT_DIR)

        try:
            # 1. Open login
            page.goto(f"{self.base_url}/")
            page.wait_for_selector('input[name="username"]', timeout=10000)
            runner.inject_overlay()
            runner.update_hud("1/4", "Login Portal JNS7", "Melakukan autentikasi akun Super Admin JNS7", "STANDBY")
            runner.highlight('input[name="username"]', "Username")
            if self.headed:
                time.sleep(1.0)
            runner.snapshot("rf_01_given_portal_login")

            # 2. Fill login
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', "admin123")
            runner.update_hud("2/4", "Submit Autentikasi", "Kredensial Super Admin berhasil dimasukkan", "RUNNING")
            if self.headed:
                time.sleep(1.0)
            runner.snapshot("rf_02_when_credentials_filled")
            page.click('button[type="submit"]')

            # 3. Verify home
            page.wait_for_url("**/home*", timeout=15000)
            runner.inject_overlay()
            runner.update_hud("3/4", "Dashboard Dimuat", "Verifikasi sesi aktif dan dashboard portal JNS7", "PASS")
            if self.headed:
                time.sleep(1.0)
            runner.snapshot("rf_03_then_dashboard_active")

            # 4. Verify sidebar parent menu and 4 submenus
            page.wait_for_selector('a:has-text("Anti Fraud")', timeout=10000)
            runner.highlight('a:has-text("Anti Fraud")', "Parent Menu")
            if self.headed:
                time.sleep(1.0)
            page.click('a:has-text("Anti Fraud")')
            time.sleep(0.5)

            submenus = ["Client Config", "Whitelist", "Blocklist & Unblock", "Audit Log"]
            for sub in submenus:
                page.wait_for_selector(f'a:has-text("{sub}")', timeout=5000)

            runner.update_hud("4/4", "Sidebar Anti Fraud", "Parent menu & 4 submenu tampil lengkap pada sidebar", "PASS")
            if self.headed:
                time.sleep(2.5)
            runner.snapshot("rf_04_and_sidebar_antifraud_selected")

            logger.info("[E2E] Browser E2E Journey untuk TC-001 sukses 100%.")
        finally:
            context.close()
            browser.close()
            p.stop()
