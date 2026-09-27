import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import scoring, clustering
import auth


class TestScoring(unittest.TestCase):
    def test_confidence_is_bounded_0_1(self):
        conf, _ = scoring.score(
            deposit_fingerprint=1.0, sweep_regularity=1.0, sender_diversity_z=3.0,
            mixer_penalty=0.0, ai_illicit_probability=0.9,
        )
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)

    def test_strong_signals_score_higher_than_weak_ones(self):
        strong, _ = scoring.score(
            deposit_fingerprint=1.0, sweep_regularity=1.0, sender_diversity_z=3.0,
            mixer_penalty=0.0, ai_illicit_probability=0.9,
        )
        weak, _ = scoring.score(
            deposit_fingerprint=0.0, sweep_regularity=0.0, sender_diversity_z=-1.0,
            mixer_penalty=1.0, ai_illicit_probability=0.1,
        )
        self.assertGreater(strong, weak)

    def test_mixer_hit_always_forces_manual_review(self):
        # Even a very high confidence number must not bypass the mixer cap - # this is a legal/evidentiary safety rail, not a tuning knob.
        decision = scoring.decide(confidence=0.99, mixer_penalty=1.0, exchange_matched=True)
        self.assertEqual(decision["action"], "manual_review")

    def test_no_exchange_match_and_low_confidence_is_insufficient_evidence(self):
        decision = scoring.decide(confidence=0.10, mixer_penalty=0.0, exchange_matched=False)
        self.assertEqual(decision["action"], "insufficient_evidence")

    def test_high_confidence_with_exchange_match_suggests_freeze(self):
        decision = scoring.decide(confidence=0.80, mixer_penalty=0.0, exchange_matched=True)
        self.assertEqual(decision["action"], "suggest_freeze")
        self.assertEqual(decision["notice_type"], "freeze_102_crpc")


class TestClustering(unittest.TestCase):
    def test_cluster_quality_score_is_bounded(self):
        clusters = {
            "root1": {"addresses": {"a", "b", "c"}, "edges": [("a", "b"), ("b", "c")]},
        }
        q = clustering.cluster_quality_score(clusters)
        self.assertGreaterEqual(q, 0.0)
        self.assertLessEqual(q, 1.0)

    def test_empty_clusters_do_not_crash(self):
        q = clustering.cluster_quality_score({})
        self.assertGreaterEqual(q, 0.0)


class TestAuth(unittest.TestCase):
    def test_token_roundtrip(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-00001", "Delhi")
        payload = auth.verify_token(token)
        self.assertEqual(payload["sub"], "off-1")
        self.assertEqual(payload["role"], "officer")

    def test_tampered_token_is_rejected(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-00001", "Delhi")
        h, p, sig = token.split(".")
        tampered = f"{h}.{p}.{sig[:-4]}AAAA"  # corrupt the signature
        with self.assertRaises(auth.TokenError):
            auth.verify_token(tampered)

    def test_expired_token_is_rejected(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-00001", "Delhi", ttl=-1)
        with self.assertRaises(auth.TokenError):
            auth.verify_token(token)

    def test_permission_table_denies_officer_admin_actions(self):
        self.assertFalse(auth.has_permission("officer", "view_audit_log"))
        self.assertTrue(auth.has_permission("admin", "view_audit_log"))

    def test_supervisor_can_approve_notices_officer_cannot(self):
        self.assertTrue(auth.has_permission("supervisor", "approve_notice"))
        self.assertFalse(auth.has_permission("officer", "approve_notice"))


if __name__ == "__main__":
    unittest.main()
