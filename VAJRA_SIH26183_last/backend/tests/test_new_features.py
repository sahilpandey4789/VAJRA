import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import scoring, tracer, syndicate
import auth


class TestAttributionTier(unittest.TestCase):
    """CONFIRMED / PROBABLE / UNATTRIBUTED - data-provenance attribution
    tier, separate from the confidence score (see scoring.py docstring
    for why a direct exchange-wallet match is CONFIRMED even at low
    confidence, and why a high heuristic-only confidence is still only
    PROBABLE)."""

    def test_direct_exchange_match_is_confirmed_even_at_low_confidence(self):
        result = scoring.attribution_tier(confidence=0.01, exchange_matched=True, mixer_penalty=0.0)
        self.assertEqual(result["tier"], "CONFIRMED")

    def test_mixer_hit_is_unattributed_even_with_exchange_match(self):
        # Evidentiary safety rail: the deterministic trail breaks at a
        # mixer hop, so nothing past it can be confirmed OR probable.
        result = scoring.attribution_tier(confidence=0.9, exchange_matched=True, mixer_penalty=1.0)
        self.assertEqual(result["tier"], "UNATTRIBUTED")

    def test_heuristic_only_strong_signal_is_probable_not_confirmed(self):
        result = scoring.attribution_tier(confidence=0.75, exchange_matched=False, mixer_penalty=0.0)
        self.assertEqual(result["tier"], "PROBABLE")

    def test_weak_signal_no_match_is_unattributed(self):
        result = scoring.attribution_tier(confidence=0.10, exchange_matched=False, mixer_penalty=0.0)
        self.assertEqual(result["tier"], "UNATTRIBUTED")

    def test_every_tier_carries_a_human_readable_reason(self):
        for conf, matched, mixer in [(0.9, True, 0.0), (0.75, False, 0.0), (0.1, False, 0.0), (0.9, True, 1.0)]:
            result = scoring.attribution_tier(conf, matched, mixer)
            self.assertIsInstance(result["reason"], str)
            self.assertGreater(len(result["reason"]), 10)


class TestTimeLockPreprocessor(unittest.TestCase):
    """Evidentiary-integrity pre-processor: a transaction dated before the
    victim-reported incident cannot be part of that incident's fund flow,
    so it's dropped before clustering/scoring ever sees it."""

    TXS = [
        {"timestamp": "2026-09-01T00:00:00Z", "hop": 1},
        {"timestamp": "2026-09-08T00:00:00Z", "hop": 1},
        {"timestamp": "2026-09-10T00:00:00Z", "hop": 2},
    ]

    def test_drops_only_transactions_before_the_cutoff(self):
        kept, dropped = tracer.apply_time_lock(self.TXS, "2026-09-05T00:00:00Z")
        self.assertEqual(dropped, 1)
        self.assertEqual(len(kept), 2)
        self.assertTrue(all(t["timestamp"] >= "2026-09-05T00:00:00Z" for t in kept))

    def test_fails_open_when_incident_timestamp_missing(self):
        kept, dropped = tracer.apply_time_lock(self.TXS, None)
        self.assertEqual(dropped, 0)
        self.assertEqual(len(kept), len(self.TXS))

    def test_fails_open_when_incident_timestamp_unparseable(self):
        kept, dropped = tracer.apply_time_lock(self.TXS, "not-a-real-timestamp")
        self.assertEqual(dropped, 0)
        self.assertEqual(len(kept), len(self.TXS))

    def test_empty_transaction_list_does_not_crash(self):
        kept, dropped = tracer.apply_time_lock([], "2026-09-05T00:00:00Z")
        self.assertEqual(kept, [])
        self.assertEqual(dropped, 0)


class TestReporterRole(unittest.TestCase):
    """Citizen/victim-facing intake role (POST /api/public/report) - the
    literal "Victim-Reported Suspect Wallet Addresses" path the PS title
    names. Must be able to submit a case and NOTHING else."""

    def test_reporter_can_submit_case(self):
        self.assertTrue(auth.has_permission("reporter", "submit_case"))

    def test_reporter_cannot_run_trace(self):
        self.assertFalse(auth.has_permission("reporter", "run_trace"))

    def test_reporter_cannot_draft_or_approve_notices(self):
        self.assertFalse(auth.has_permission("reporter", "draft_notice"))
        self.assertFalse(auth.has_permission("reporter", "approve_notice"))

    def test_reporter_has_no_investigator_permissions_at_all(self):
        investigator_only = {"run_trace", "draft_notice", "approve_notice", "view_own_jurisdiction",
                              "reassign_case", "cross_jurisdiction_view", "view_audit_log", "system_config"}
        for perm in investigator_only:
            self.assertFalse(auth.has_permission("reporter", perm), f"reporter must not have '{perm}'")

    def test_reporter_token_round_trips_like_any_other_role(self):
        token = auth.issue_token("rpt-1", "reporter", "RPT-TEST01", "citizen@example.com")
        payload = auth.verify_token(token)
        self.assertEqual(payload["role"], "reporter")
        self.assertEqual(payload["sub"], "rpt-1")


class TestSyndicateScore(unittest.TestCase):
    """Syndicate Score + Freeze Window - engine/syndicate.py. Turns
    "N cases share a wallet cluster" (already detected by
    engine/case_graph.py) into a single actionable WATCH/ESCALATE/
    CRITICAL signal plus a heuristic cash-out urgency estimate."""

    def test_more_victims_scores_higher(self):
        idx = {str(i): {"confidence": 0.5} for i in range(6)}
        score_2 = syndicate.syndicate_score(["0", "1"], idx)
        score_6 = syndicate.syndicate_score([str(i) for i in range(6)], idx)
        self.assertGreater(score_6, score_2)

    def test_higher_confidence_scores_higher_at_same_victim_count(self):
        low = syndicate.syndicate_score(["a", "b"], {"a": {"confidence": 0.1}, "b": {"confidence": 0.1}})
        high = syndicate.syndicate_score(["a", "b"], {"a": {"confidence": 0.9}, "b": {"confidence": 0.9}})
        self.assertGreater(high, low)

    def test_tier_boundaries(self):
        self.assertIsNone(syndicate.syndicate_tier(1))
        self.assertEqual(syndicate.syndicate_tier(syndicate.WATCH_THRESHOLD), "WATCH")
        self.assertEqual(syndicate.syndicate_tier(syndicate.ESCALATE_THRESHOLD), "ESCALATE")
        self.assertEqual(syndicate.syndicate_tier(syndicate.CRITICAL_THRESHOLD), "CRITICAL")

    def test_freeze_window_shrinks_as_victim_count_grows(self):
        small = syndicate.freeze_window_hours(victim_count=2, avg_confidence=0.5)
        large = syndicate.freeze_window_hours(victim_count=15, avg_confidence=0.5)
        self.assertLess(large, small)

    def test_freeze_window_shrinks_as_confidence_grows(self):
        low_conf = syndicate.freeze_window_hours(victim_count=3, avg_confidence=0.1)
        high_conf = syndicate.freeze_window_hours(victim_count=3, avg_confidence=0.9)
        self.assertLess(high_conf, low_conf)

    def test_freeze_window_never_goes_below_floor(self):
        extreme = syndicate.freeze_window_hours(victim_count=100, avg_confidence=1.0)
        self.assertGreaterEqual(extreme, 2.0)

    def test_pooled_value_sums_across_cases(self):
        idx = {"a": {"total_value": 10.5}, "b": {"total_value": 4.25}}
        self.assertEqual(syndicate.pooled_value(idx, ["a", "b"]), 14.75)

    def test_pooled_value_none_when_no_case_has_value_data(self):
        idx = {"a": {"total_value": None}, "b": {}}
        self.assertIsNone(syndicate.pooled_value(idx, ["a", "b"]))

    def test_build_syndicate_report_skips_isolated_cases(self):
        # case_graph.build_networks() never returns a single-case group in
        # the first place, but build_syndicate_report() itself also guards
        # on WATCH_THRESHOLD as a second, independent safety check.
        networks = [{"case_ids": ["only-one"], "edges": []}]
        index = {"only-one": {"confidence": 0.9}}
        self.assertEqual(syndicate.build_syndicate_report(networks, index), [])

    def test_build_syndicate_report_sorts_highest_score_first(self):
        networks = [
            {"case_ids": ["a", "b"], "edges": []},
            {"case_ids": ["c", "d", "e", "f", "g", "h"], "edges": []},
        ]
        index = {k: {"confidence": 0.5} for k in "abcdefgh"}
        report = syndicate.build_syndicate_report(networks, index)
        self.assertEqual(len(report), 2)
        self.assertGreaterEqual(report[0]["syndicate_score"], report[1]["syndicate_score"])


if __name__ == "__main__":
    unittest.main()
