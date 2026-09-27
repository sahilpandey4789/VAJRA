import unittest

from engine import risk_patterns


def _tx(tx_hash, hop, inputs, outputs, timestamp):
    return {"tx_hash": tx_hash, "hop": hop, "inputs": inputs, "outputs": outputs, "timestamp": timestamp}


class TestRapidTransfers(unittest.TestCase):
    def test_no_hits_when_gaps_are_large(self):
        txs = [
            _tx("a", 1, ["S"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z"),
            _tx("b", 2, ["X"], [{"address": "Y", "value": 1}], "2026-01-01T05:00:00Z"),
        ]
        self.assertIsNone(risk_patterns.detect_rapid_transfers(txs))

    def test_hit_when_gap_under_threshold(self):
        txs = [
            _tx("a", 1, ["S"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z"),
            _tx("b", 2, ["X"], [{"address": "Y", "value": 1}], "2026-01-01T00:03:00Z"),
        ]
        hit = risk_patterns.detect_rapid_transfers(txs)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["pattern"], "rapid_transfers")
        self.assertEqual(hit["severity"], "high")

    def test_missing_or_bad_timestamps_do_not_crash(self):
        txs = [
            _tx("a", 1, ["S"], [{"address": "X", "value": 1}], None),
            _tx("b", 2, ["X"], [{"address": "Y", "value": 1}], "not-a-date"),
        ]
        self.assertIsNone(risk_patterns.detect_rapid_transfers(txs))


class TestLayering(unittest.TestCase):
    def test_below_threshold_is_none(self):
        txs = [_tx(f"t{i}", i, ["S"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z") for i in range(3)]
        self.assertIsNone(risk_patterns.detect_layering(txs))

    def test_at_or_above_threshold_fires(self):
        txs = [_tx(f"t{i}", i, ["S"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z") for i in range(5)]
        hit = risk_patterns.detect_layering(txs)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["pattern"], "layering")

    def test_empty_transactions_is_none(self):
        self.assertIsNone(risk_patterns.detect_layering([]))


class TestStructuring(unittest.TestCase):
    def test_below_min_count_is_none(self):
        txs = [_tx(f"t{i}", 1, ["S"], [{"address": f"X{i}", "value": 0.1}], "2026-01-01T00:00:00Z") for i in range(2)]
        self.assertIsNone(risk_patterns.detect_structuring(txs))

    def test_at_min_count_fires(self):
        txs = [_tx(f"t{i}", 1, ["S"], [{"address": f"X{i}", "value": 0.1}], "2026-01-01T00:00:00Z") for i in range(4)]
        hit = risk_patterns.detect_structuring(txs)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["pattern"], "structuring")

    def test_large_value_outputs_are_not_structuring(self):
        txs = [_tx(f"t{i}", 1, ["S"], [{"address": f"X{i}", "value": 5.0}], "2026-01-01T00:00:00Z") for i in range(6)]
        self.assertIsNone(risk_patterns.detect_structuring(txs))


class TestHighFanOut(unittest.TestCase):
    def test_below_threshold_is_none(self):
        txs = [_tx("t1", 1, ["S"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z")]
        self.assertIsNone(risk_patterns.detect_high_fan_out(txs))

    def test_at_threshold_fires(self):
        outs = [{"address": f"X{i}", "value": 1} for i in range(5)]
        txs = [_tx("t1", 1, ["S"], outs, "2026-01-01T00:00:00Z")]
        hit = risk_patterns.detect_high_fan_out(txs)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["pattern"], "high_fan_out")

    def test_empty_is_none(self):
        self.assertIsNone(risk_patterns.detect_high_fan_out([]))


class TestDetectAll(unittest.TestCase):
    def test_clean_trail_returns_empty_list(self):
        txs = [_tx("t1", 1, ["S"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z")]
        self.assertEqual(risk_patterns.detect_all(txs), [])

    def test_mixer_hit_is_included(self):
        txs = [_tx("t1", 1, ["S"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z")]
        patterns = risk_patterns.detect_all(txs, mixer_hit={"label": "Tornado-like Mixer", "address": "0xMIXER"})
        self.assertTrue(any(p["pattern"] == "mixer_hop" for p in patterns))

    def test_exchange_match_is_included(self):
        txs = [_tx("t1", 1, ["S"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z")]
        patterns = risk_patterns.detect_all(txs, exchange_match={"exchange": "WazirX", "address": "0xEX"})
        self.assertTrue(any(p["pattern"] == "exchange_cashout" for p in patterns))

    def test_results_sorted_high_severity_first(self):
        # layering (medium at depth 4) + mixer (always high) -> mixer must lead.
        # Timestamps spaced 6h apart so rapid_transfers does NOT also fire here.
        txs = [_tx(f"t{i}", i, ["S"], [{"address": "X", "value": 1}], f"2026-01-0{i+1}T00:00:00Z") for i in range(5)]
        patterns = risk_patterns.detect_all(txs, mixer_hit={"label": "Mixer", "address": "0xM"})
        self.assertEqual(patterns[0]["pattern"], "mixer_hop")

    def test_round_trip_is_included_when_origin_address_given(self):
        txs = [
            _tx("t1", 1, ["ORIGIN"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z"),
            _tx("t2", 2, ["X"], [{"address": "ORIGIN", "value": 1}], "2026-01-02T00:00:00Z"),
        ]
        patterns = risk_patterns.detect_all(txs, origin_address="ORIGIN")
        self.assertTrue(any(p["pattern"] == "round_trip" for p in patterns))

    def test_round_trip_omitted_when_no_origin_address_given(self):
        txs = [
            _tx("t1", 1, ["ORIGIN"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z"),
            _tx("t2", 2, ["X"], [{"address": "ORIGIN", "value": 1}], "2026-01-02T00:00:00Z"),
        ]
        patterns = risk_patterns.detect_all(txs)  # origin_address defaults to None
        self.assertFalse(any(p["pattern"] == "round_trip" for p in patterns))


class TestRoundTrip(unittest.TestCase):
    def test_no_origin_address_returns_none(self):
        txs = [_tx("t1", 2, ["X"], [{"address": "ORIGIN", "value": 1}], "2026-01-01T00:00:00Z")]
        self.assertIsNone(risk_patterns.detect_round_trip(txs, None))

    def test_funds_never_returning_gives_none(self):
        txs = [
            _tx("t1", 1, ["ORIGIN"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z"),
            _tx("t2", 2, ["X"], [{"address": "Y", "value": 1}], "2026-01-02T00:00:00Z"),
        ]
        self.assertIsNone(risk_patterns.detect_round_trip(txs, "ORIGIN"))

    def test_funds_returning_at_hop_two_fires(self):
        txs = [
            _tx("t1", 1, ["ORIGIN"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z"),
            _tx("t2", 2, ["X"], [{"address": "ORIGIN", "value": 1}], "2026-01-02T00:00:00Z"),
        ]
        hit = risk_patterns.detect_round_trip(txs, "ORIGIN")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["pattern"], "round_trip")
        self.assertEqual(hit["severity"], "high")

    def test_immediate_hop_zero_or_one_return_does_not_count(self):
        # ROUND_TRIP_MIN_HOP is 2 - a same-hop/first-hop "return" is
        # excluded on purpose (could just be routine change-handling).
        txs = [_tx("t1", 1, ["X"], [{"address": "ORIGIN", "value": 1}], "2026-01-01T00:00:00Z")]
        self.assertIsNone(risk_patterns.detect_round_trip(txs, "ORIGIN"))

    def test_evidence_names_the_hop_it_returned_at(self):
        txs = [
            _tx("t1", 1, ["ORIGIN"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z"),
            _tx("t2", 3, ["X"], [{"address": "ORIGIN", "value": 1}], "2026-01-02T00:00:00Z"),
        ]
        hit = risk_patterns.detect_round_trip(txs, "ORIGIN")
        self.assertIn("hop 3", hit["evidence"])

    def test_tx_hashes_include_the_returning_transaction(self):
        txs = [
            _tx("t1", 1, ["ORIGIN"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z"),
            _tx("t2", 2, ["X"], [{"address": "ORIGIN", "value": 1}], "2026-01-02T00:00:00Z"),
        ]
        hit = risk_patterns.detect_round_trip(txs, "ORIGIN")
        self.assertIn("t2", hit["tx_hashes"])

    def test_multiple_returns_reports_the_deepest_hop(self):
        txs = [
            _tx("t1", 1, ["ORIGIN"], [{"address": "X", "value": 1}], "2026-01-01T00:00:00Z"),
            _tx("t2", 2, ["X"], [{"address": "ORIGIN", "value": 1}], "2026-01-02T00:00:00Z"),
            _tx("t3", 4, ["ORIGIN"], [{"address": "Y", "value": 1}], "2026-01-03T00:00:00Z"),
            _tx("t4", 5, ["Y"], [{"address": "ORIGIN", "value": 1}], "2026-01-04T00:00:00Z"),
        ]
        hit = risk_patterns.detect_round_trip(txs, "ORIGIN")
        self.assertIn("hop 5", hit["evidence"])

    def test_empty_transactions_returns_none(self):
        self.assertIsNone(risk_patterns.detect_round_trip([], "ORIGIN"))

    def test_transaction_missing_hop_field_is_skipped_not_crashed(self):
        txs = [{"tx_hash": "t1", "inputs": ["X"], "outputs": [{"address": "ORIGIN", "value": 1}]}]  # no "hop" key
        self.assertIsNone(risk_patterns.detect_round_trip(txs, "ORIGIN"))


if __name__ == "__main__":
    unittest.main()
