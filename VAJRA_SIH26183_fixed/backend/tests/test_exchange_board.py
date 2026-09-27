import json
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.exchange_board import aggregate_exchange_risk


def _row(report_json, generated_at, case_id, confidence):
    return {"report_json": json.dumps(report_json), "generated_at": generated_at,
            "case_id": case_id, "confidence": confidence}


class TestExchangeBoard(unittest.TestCase):
    def test_empty_input_returns_empty_board(self):
        self.assertEqual(aggregate_exchange_risk([]), [])

    def test_reports_without_exchange_match_are_ignored(self):
        rows = [_row({"exchange_match": None, "chain": "ETHEREUM"}, "2026-01-01T00:00:00Z", "c1", 0.9)]
        self.assertEqual(aggregate_exchange_risk(rows), [])

    def test_single_match_scores_correctly(self):
        rows = [_row(
            {"exchange_match": {"exchange": "WazirX", "chain": "ETHEREUM", "address": "0xabc"}, "chain": "ETHEREUM"},
            "2026-01-01T00:00:00Z", "case-1", 0.80,
        )]
        board = aggregate_exchange_risk(rows)
        self.assertEqual(len(board), 1)
        b = board[0]
        self.assertEqual(b["exchange"], "WazirX")
        self.assertEqual(b["linked_cases"], 1)
        self.assertAlmostEqual(b["avg_confidence"], 0.80)
        self.assertAlmostEqual(b["fraud_link_score"], 0.80)  # 1 case * 0.80
        self.assertEqual(b["fraud_link_score_normalized"], 1.0)

    def test_repeat_offender_ranks_above_single_high_confidence_hit(self):
        # Exchange A: 3 cases at 0.5 confidence each -> score 1.5
        # Exchange B: 1 case at 0.9 confidence        -> score 0.9
        # A repeat offender should outrank a single high-confidence hit - # this is the whole point of the scoring formula.
        rows = [
            _row({"exchange_match": {"exchange": "A", "chain": "ETHEREUM", "address": "0x1"}}, "2026-01-01T00:00:00Z", "c1", 0.5),
            _row({"exchange_match": {"exchange": "A", "chain": "ETHEREUM", "address": "0x2"}}, "2026-01-02T00:00:00Z", "c2", 0.5),
            _row({"exchange_match": {"exchange": "A", "chain": "ETHEREUM", "address": "0x3"}}, "2026-01-03T00:00:00Z", "c3", 0.5),
            _row({"exchange_match": {"exchange": "B", "chain": "TRON", "address": "0x9"}}, "2026-01-04T00:00:00Z", "c4", 0.9),
        ]
        board = aggregate_exchange_risk(rows)
        self.assertEqual(board[0]["exchange"], "A")
        self.assertGreater(board[0]["fraud_link_score"], board[1]["fraud_link_score"])
        self.assertEqual(board[1]["exchange"], "B")

    def test_same_exchange_hit_from_two_chains_merges_and_unions_chains(self):
        rows = [
            _row({"exchange_match": {"exchange": "Binance", "chain": "BITCOIN", "address": "0xb1"}}, "2026-01-01T00:00:00Z", "c1", 0.6),
            _row({"exchange_match": {"exchange": "Binance", "chain": "TRON", "address": "0xb2"}}, "2026-01-02T00:00:00Z", "c2", 0.7),
        ]
        board = aggregate_exchange_risk(rows)
        self.assertEqual(len(board), 1)
        self.assertEqual(board[0]["chains"], ["BITCOIN", "TRON"])
        self.assertEqual(board[0]["linked_cases"], 2)

    def test_multiple_trace_versions_of_same_case_do_not_double_count_case(self):
        # Same case_id re-traced twice (a version bump) should count as one
        # linked case, not two - case_ids is a set.
        rows = [
            _row({"exchange_match": {"exchange": "WazirX", "chain": "ETHEREUM", "address": "0xabc"}}, "2026-01-01T00:00:00Z", "case-1", 0.5),
            _row({"exchange_match": {"exchange": "WazirX", "chain": "ETHEREUM", "address": "0xabc"}}, "2026-01-02T00:00:00Z", "case-1", 0.9),
        ]
        board = aggregate_exchange_risk(rows)
        self.assertEqual(board[0]["linked_cases"], 1)

    def test_last_seen_takes_the_most_recent_timestamp(self):
        rows = [
            _row({"exchange_match": {"exchange": "WazirX", "chain": "ETHEREUM", "address": "0xabc"}}, "2026-01-01T00:00:00Z", "c1", 0.5),
            _row({"exchange_match": {"exchange": "WazirX", "chain": "ETHEREUM", "address": "0xabc"}}, "2026-03-01T00:00:00Z", "c2", 0.5),
        ]
        board = aggregate_exchange_risk(rows)
        self.assertEqual(board[0]["last_seen"], "2026-03-01T00:00:00Z")

    def test_malformed_report_json_is_skipped_not_fatal(self):
        rows = [{"report_json": "{not valid json", "generated_at": "x", "case_id": "c1", "confidence": 0.5}]
        self.assertEqual(aggregate_exchange_risk(rows), [])

    def test_missing_confidence_falls_back_to_report_confidence(self):
        rows = [_row(
            {"exchange_match": {"exchange": "WazirX", "chain": "ETHEREUM", "address": "0xabc"}, "confidence": 0.42},
            "2026-01-01T00:00:00Z", "c1", None,
        )]
        board = aggregate_exchange_risk(rows)
        self.assertAlmostEqual(board[0]["avg_confidence"], 0.42)


if __name__ == "__main__":
    unittest.main()
