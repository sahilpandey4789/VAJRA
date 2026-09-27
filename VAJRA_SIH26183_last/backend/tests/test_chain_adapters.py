import unittest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import chain_adapters as ca
from engine import cache as vajra_cache


class FakeProvider:
    """Stand-in for a real Live*Adapter - never touches the network."""
    def __init__(self, name, result=None, error=None):
        self.provider_name = name
        self._result = result
        self._error = error
        self.calls = 0

    def fetch_forward_transactions(self, address, max_hops=6):
        self.calls += 1
        if self._error:
            raise self._error
        return self._result


class TestMockAdapter(unittest.TestCase):
    def test_unknown_fixture_key_returns_empty_list(self):
        adapter = ca.MockAdapter("ETHEREUM", "no-such-fixture")
        self.assertEqual(adapter.fetch_forward_transactions("0xabc"), [])

    def test_provider_name_is_offline_fixture(self):
        adapter = ca.MockAdapter("ETHEREUM", "anything")
        self.assertEqual(adapter.provider_name, "offline-fixture")

    def test_returns_transactions_within_max_hops_only(self):
        from engine import fixtures
        # pick any real fixture key and confirm hop filtering actually filters
        any_key = next(iter(fixtures.FIXTURE_MAP))
        adapter = ca.MockAdapter("ETHEREUM", any_key)
        all_tx = fixtures.FIXTURE_MAP[any_key]["transactions"]
        max_hop_present = max(t["hop"] for t in all_tx)
        if max_hop_present > 1:
            limited = adapter.fetch_forward_transactions("addr", max_hops=1)
            self.assertTrue(all(t["hop"] <= 1 for t in limited))
            self.assertLess(len(limited), len(all_tx))

    def test_chain_name_is_set_from_constructor(self):
        adapter = ca.MockAdapter("TRON", "x")
        self.assertEqual(adapter.chain_name, "TRON")


class TestGetAdapter(unittest.TestCase):
    def setUp(self):
        self._orig = os.environ.get("VAJRA_LIVE_MODE")

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("VAJRA_LIVE_MODE", None)
        else:
            os.environ["VAJRA_LIVE_MODE"] = self._orig

    def test_live_mode_off_returns_mock_adapter(self):
        os.environ.pop("VAJRA_LIVE_MODE", None)
        adapter = ca.get_adapter("ETHEREUM", "fixture-key")
        self.assertIsInstance(adapter, ca.MockAdapter)

    def test_live_mode_on_for_known_chain_returns_failover_adapter(self):
        os.environ["VAJRA_LIVE_MODE"] = "1"
        adapter = ca.get_adapter("ETHEREUM", "fixture-key")
        self.assertIsInstance(adapter, ca.ChainFailoverAdapter)

    def test_live_mode_on_for_unknown_chain_falls_back_to_mock(self):
        os.environ["VAJRA_LIVE_MODE"] = "1"
        adapter = ca.get_adapter("DOGECOIN", "fixture-key")
        self.assertIsInstance(adapter, ca.MockAdapter)

    def test_chain_argument_is_case_insensitive(self):
        os.environ["VAJRA_LIVE_MODE"] = "1"
        adapter = ca.get_adapter("ethereum", "fixture-key")
        self.assertIsInstance(adapter, ca.ChainFailoverAdapter)

    def test_live_mode_value_other_than_one_is_treated_as_off(self):
        os.environ["VAJRA_LIVE_MODE"] = "true"  # only the literal "1" counts
        adapter = ca.get_adapter("ETHEREUM", "fixture-key")
        self.assertIsInstance(adapter, ca.MockAdapter)


class TestChainFailoverAdapter(unittest.TestCase):
    def setUp(self):
        # give every test a clean cache namespace so cache hits from one
        # test can't leak into another's assertions
        self.addr = f"test-addr-{time.monotonic_ns()}"

    def test_first_provider_success_returns_its_result_and_sets_last_provider(self):
        p1 = FakeProvider("first", result=[{"tx_hash": "a"}])
        adapter = ca.ChainFailoverAdapter("ETHEREUM", [p1])
        result = adapter.fetch_forward_transactions(self.addr)
        self.assertEqual(result, [{"tx_hash": "a"}])
        self.assertEqual(adapter.last_provider_used, "first")

    def test_first_provider_fails_second_succeeds(self):
        p1 = FakeProvider("first", error=ca.AdapterError("boom"))
        p2 = FakeProvider("second", result=[{"tx_hash": "b"}])
        adapter = ca.ChainFailoverAdapter("ETHEREUM", [p1, p2])
        result = adapter.fetch_forward_transactions(self.addr)
        self.assertEqual(result, [{"tx_hash": "b"}])
        self.assertEqual(adapter.last_provider_used, "second")
        self.assertEqual(p1.calls, 1)
        self.assertEqual(p2.calls, 1)

    def test_all_providers_failing_raises_adapter_error(self):
        p1 = FakeProvider("first", error=ca.AdapterError("boom1"))
        p2 = FakeProvider("second", error=ca.AdapterError("boom2"))
        adapter = ca.ChainFailoverAdapter("ETHEREUM", [p1, p2])
        with self.assertRaises(ca.AdapterError):
            adapter.fetch_forward_transactions(self.addr)

    def test_successful_result_is_cached_so_second_call_skips_providers(self):
        p1 = FakeProvider("first", result=[{"tx_hash": "cached"}])
        adapter = ca.ChainFailoverAdapter("ETHEREUM", [p1])
        adapter.fetch_forward_transactions(self.addr)
        self.assertEqual(p1.calls, 1)
        # second call for the same address should hit the cache, not the provider again
        result2 = adapter.fetch_forward_transactions(self.addr)
        self.assertEqual(result2, [{"tx_hash": "cached"}])
        self.assertEqual(p1.calls, 1)
        self.assertEqual(adapter.last_provider_used, "cache")

    def test_different_max_hops_are_different_cache_keys(self):
        p1 = FakeProvider("first", result=[{"tx_hash": "x"}])
        adapter = ca.ChainFailoverAdapter("ETHEREUM", [p1])
        adapter.fetch_forward_transactions(self.addr, max_hops=3)
        adapter.fetch_forward_transactions(self.addr, max_hops=6)
        self.assertEqual(p1.calls, 2)  # different cache key each time -> provider called twice

    def test_generic_exception_from_provider_is_also_caught_and_tried_next(self):
        p1 = FakeProvider("first", error=ValueError("unexpected"))
        p2 = FakeProvider("second", result=[{"tx_hash": "ok"}])
        adapter = ca.ChainFailoverAdapter("ETHEREUM", [p1, p2])
        result = adapter.fetch_forward_transactions(self.addr)
        self.assertEqual(result, [{"tx_hash": "ok"}])


class TestProviderHealthSnapshot(unittest.TestCase):
    def setUp(self):
        self._orig_live = os.environ.get("VAJRA_LIVE_MODE")
        self._orig_eth_key = os.environ.get("ETHERSCAN_API_KEY")
        self._orig_tron_key = os.environ.get("TRONGRID_API_KEY")

    def tearDown(self):
        for var, val in [("VAJRA_LIVE_MODE", self._orig_live),
                          ("ETHERSCAN_API_KEY", self._orig_eth_key),
                          ("TRONGRID_API_KEY", self._orig_tron_key)]:
            if val is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = val

    def test_live_mode_off_marks_every_provider_disabled(self):
        os.environ.pop("VAJRA_LIVE_MODE", None)
        snapshot = ca.provider_health_snapshot()
        self.assertTrue(all(p["status"] == "disabled" for p in snapshot))

    def test_covers_all_three_chains(self):
        snapshot = ca.provider_health_snapshot()
        chains = {p["chain"] for p in snapshot}
        self.assertEqual(chains, {"ETHEREUM", "BITCOIN", "TRON"})

    def test_live_mode_on_with_key_present_marks_ready(self):
        os.environ["VAJRA_LIVE_MODE"] = "1"
        os.environ["ETHERSCAN_API_KEY"] = "fake-key-for-test"
        snapshot = ca.provider_health_snapshot()
        etherscan_entry = next(p for p in snapshot if p["provider"] == "etherscan")
        self.assertEqual(etherscan_entry["status"], "ready")

    def test_live_mode_on_without_required_key_marks_missing_key(self):
        os.environ["VAJRA_LIVE_MODE"] = "1"
        os.environ.pop("ETHERSCAN_API_KEY", None)
        snapshot = ca.provider_health_snapshot()
        etherscan_entry = next(p for p in snapshot if p["provider"] == "etherscan")
        self.assertEqual(etherscan_entry["status"], "missing_key")

    def test_provider_with_no_key_requirement_never_reports_missing_key(self):
        os.environ["VAJRA_LIVE_MODE"] = "1"
        snapshot = ca.provider_health_snapshot()
        blockscout_entry = next(p for p in snapshot if p["provider"] == "blockscout")
        self.assertFalse(blockscout_entry["requires_key"])
        self.assertEqual(blockscout_entry["status"], "ready")


class TestIsoHelper(unittest.TestCase):
    def test_iso_formats_unix_timestamp_as_z_suffixed_string(self):
        formatted = ca._iso(0)  # epoch
        self.assertTrue(formatted.startswith("1970-01-01"))
        self.assertTrue(formatted.endswith("Z"))

    def test_iso_output_is_stable_for_same_input(self):
        self.assertEqual(ca._iso(1700000000), ca._iso(1700000000))


if __name__ == "__main__":
    unittest.main()
