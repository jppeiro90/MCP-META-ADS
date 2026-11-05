import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server
from meta_ads_api import MetaAds, clean_result, prepare_payload
from mcp_common import Proposals, save_json

class MetaAdsTests(unittest.TestCase):
    def setUp(self):
        p=patch.object(server,"api");self.api=p.start();self.addCleanup(p.stop)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        p=patch.object(server,"plans",Proposals(self.tmp.name));p.start();self.addCleanup(p.stop)
    def test_default_paused(self):
        p=prepare_payload("123","campaign",{"name":"Test","objective":"OUTCOME_LEADS"})
        self.assertEqual(p["fields"]["status"],"PAUSED")
        self.assertEqual(p["path"],"act_123/campaigns")
    def test_deletion_blocked(self):
        with self.assertRaises(ValueError): prepare_payload("123","campaign",{"status":"DELETED"},"456")
    def test_credentials_and_billing_blocked(self):
        for fields in ({"access_token":"SECRET"},{"funding_source":"123"},{"account_status":1}):
            with self.assertRaises(ValueError): prepare_payload("123","campaign",fields)
    def test_budget_validation(self):
        for value in (-1,0,"12.5"):
            with self.assertRaises(ValueError): prepare_payload("123","adset",{"daily_budget":value})
    def test_pagination_never_leaks_token(self):
        result=clean_result({"data":[{"access_token":"SECRET","name":"Page"}],"paging":{"next":"https://graph.facebook.com?access_token=SECRET","cursors":{"after":"NEXT"}}})
        self.assertNotIn("SECRET",str(result));self.assertTrue(result["paging"]["has_next"])
        self.assertEqual(result["paging"]["cursors"]["after"],"NEXT")
    def test_all_portfolios_and_pagination(self):
        server.meta_ads_list_businesses("agency","CURSOR")
        self.assertEqual(self.api.request.call_args.kwargs["profile"],"agency")
        self.assertEqual(self.api.request.call_args.kwargs["params"]["after"],"CURSOR")
    def test_cross_account_update_blocked(self):
        self.api.request.side_effect=[{"account_id":"123"},{"account_id":"999"}]
        with self.assertRaises(ValueError): server.meta_ads_prepare_change("123","campaign",{"name":"Test"},"456")
    def test_no_confirmation_no_write(self):
        with self.assertRaises(ValueError): server.meta_ads_apply_proposal("a"*32)
        self.api.request.assert_not_called()
    def test_budget_update_requires_spend_authorization(self):
        self.api.request.side_effect=[{"account_id":"123"},{"account_id":"123"}]
        p=server.meta_ads_prepare_change("123","campaign",{"daily_budget":10000},"456")
        self.assertTrue(p["requires_spend_authorization"])
    def test_proposal_prepares_without_write(self):
        p=server.meta_ads_prepare_change("123","campaign",{"name":"Test","objective":"OUTCOME_LEADS"})
        self.assertFalse(p["requires_spend_authorization"])
        self.assertTrue(all(c.kwargs.get("method","GET")=="GET" for c in self.api.request.call_args_list))
    def test_apply_once_only_exact_plan(self):
        p=server.meta_ads_prepare_change("123","campaign",{"name":"Test","objective":"OUTCOME_LEADS"})
        self.api.request.reset_mock()
        server.meta_ads_apply_proposal(p["proposal_id"],True)
        self.assertEqual(self.api.request.call_args.args[0],"act_123/campaigns")
        self.assertEqual(self.api.request.call_args.kwargs["body"]["status"],"PAUSED")
        with self.assertRaises(ValueError): server.meta_ads_apply_proposal(p["proposal_id"],True)
        self.assertEqual(self.api.request.call_count,1)
    def test_profile_status_never_exposes_token(self):
        path=Path(self.tmp.name)/"config.json";save_json(path,{"profiles":{"agency":{"access_token":"TOP_SECRET"}}})
        self.assertNotIn("TOP_SECRET",str(MetaAds(path).status()))
    def test_unknown_endpoint_rejected(self):
        with self.assertRaises(ValueError): MetaAds(Path(self.tmp.name)/"absent").request("https://evil.test")
