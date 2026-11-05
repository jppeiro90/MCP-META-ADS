import asyncio
import importlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from starlette.testclient import TestClient
from mcp_common import BearerAuth, Proposals, make_mcp, numeric_id, save_json

class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.plans = Proposals(self.tmp.name)
    def test_confirmation_required(self):
        p = self.plans.prepare({"account": "123"})
        with self.assertRaises(ValueError): self.plans.load(p["proposal_id"], False)
    def test_activation_requires_separate_authorization(self):
        p = self.plans.prepare({"status": "ACTIVE"}, activation=True)
        with self.assertRaises(ValueError): self.plans.claim(p["proposal_id"], True)
        self.assertEqual(self.plans.claim(p["proposal_id"], True, True)["payload"]["status"], "ACTIVE")
    def test_sent_cannot_be_reused(self):
        p = self.plans.prepare({"test": 1})
        self.plans.claim(p["proposal_id"], True)
        with self.assertRaises(ValueError): self.plans.claim(p["proposal_id"], True)
    def test_expiry(self):
        p = self.plans.prepare({"test": 1})
        with patch("mcp_common.time.time", return_value=time.time()+2000):
            with self.assertRaises(ValueError): self.plans.load(p["proposal_id"], True)
    def test_exact_content_preserved(self):
        data = {"account": "123", "fields": {"name": "Campaña de prueba", "daily_budget": 1000}}
        p = self.plans.prepare(data)
        self.assertEqual(self.plans.load(p["proposal_id"], True)["payload"], data)
    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError): self.plans.load("../../token", True)
    def test_concurrent_claim_once(self):
        p = self.plans.prepare({"test": 1})
        results = []
        def claim():
            try: self.plans.claim(p["proposal_id"], True); results.append("ok")
            except ValueError: results.append("blocked")
        threads = [threading.Thread(target=claim) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sorted(results), ["blocked", "ok"])

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.mcp = make_mcp("Test Ads")
        @self.mcp.tool()
        def status() -> dict: return {"configured": False}
        self.app = BearerAuth(self.mcp.streamable_http_app(), "x"*64, "test-ads")
    def test_fail_closed(self):
        with self.assertRaises(ValueError): BearerAuth(None, "", "test")
    def test_auth_health(self):
        with TestClient(self.app) as http:
            self.assertEqual(http.get("/health").status_code, 401)
            self.assertEqual(http.get("/health",headers={"Authorization":"Bearer wrong"}).status_code,401)
            self.assertEqual(http.get("/health",headers={"Authorization":"Bearer "+"x"*64}).json()["status"],"ok")
    def test_mcp_protocol(self):
        h = {"Authorization":"Bearer "+"x"*64, "Accept":"application/json, text/event-stream","Host":"localhost:8000"}
        with TestClient(self.app) as http:
            r = http.post("/mcp",headers=h,json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1"}}})
            self.assertEqual(r.status_code,200)
            r=http.post("/mcp",headers=h,json={"jsonrpc":"2.0","id":2,"method":"tools/list"})
            self.assertEqual(r.json()["result"]["tools"][0]["name"],"status")
    def test_untrusted_host_blocked(self):
        with TestClient(self.app) as http:
            r=http.post("/mcp",headers={"Authorization":"Bearer "+"x"*64,"Host":"evil.test"},json={"jsonrpc":"2.0","id":1,"method":"tools/list"})
            self.assertEqual(r.status_code,421)
