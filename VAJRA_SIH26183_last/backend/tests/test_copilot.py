import unittest

from engine import copilot


def _report(**overrides):
    base = {
        "confidence": 0.85,
        "confidence_breakdown": [
            {"factor": "Deposit-fingerprint match", "value": 0.9, "weight": 2.55, "contribution": 2.295},
            {"factor": "Mixer penalty (inverted)", "value": 1.0, "weight": 2.35, "contribution": 2.35},
            {"factor": "Cluster quality (diagnostic - not in formula)", "value": 0.5, "weight": 0.0, "contribution": 0.0},
        ],
        "ai_explanation": [
            {"feature": "peel_chain_score", "direction": "+", "magnitude": 0.41, "reason": "Peel chain detected"},
            {"feature": "in_degree", "direction": "-", "magnitude": 0.20, "reason": "Broad inbound sender pool"},
        ],
        "decision": {"action": "suggest_freeze", "rationale": "High confidence with exchange match."},
        "mixer_hit": None,
        "exchange_match": {"exchange": "WazirX", "address": "0xEX"},
        "linked_case_details": [],
        "risk_patterns": [],
    }
    base.update(overrides)
    return base


class TestConfidenceLabel(unittest.TestCase):
    def test_high(self):
        self.assertEqual(copilot.confidence_label(0.9), "High")

    def test_medium(self):
        self.assertEqual(copilot.confidence_label(0.5), "Medium")

    def test_low(self):
        self.assertEqual(copilot.confidence_label(0.1), "Low")

    def test_boundary_is_inclusive(self):
        self.assertEqual(copilot.confidence_label(0.75), "High")
        self.assertEqual(copilot.confidence_label(0.40), "Medium")


class TestWhySuspicious(unittest.TestCase):
    def test_diagnostic_only_rows_are_excluded(self):
        brief = copilot.generate_brief(_report())
        signals = [i["signal"] for i in brief["why_suspicious"]]
        self.assertTrue(all("diagnostic" not in s.lower() for s in signals))

    def test_negative_direction_ml_features_are_excluded(self):
        brief = copilot.generate_brief(_report())
        signals = [i["signal"] for i in brief["why_suspicious"]]
        self.assertFalse(any("Broad inbound sender pool" in s for s in signals))

    def test_positive_ml_feature_is_included(self):
        brief = copilot.generate_brief(_report())
        signals = [i["signal"] for i in brief["why_suspicious"]]
        self.assertTrue(any("Peel chain detected" in s for s in signals))

    def test_sorted_by_contribution_descending(self):
        brief = copilot.generate_brief(_report())
        contributions = [i["contribution"] for i in brief["why_suspicious"]]
        self.assertEqual(contributions, sorted(contributions, reverse=True))

    def test_no_evidence_gives_empty_list(self):
        brief = copilot.generate_brief(_report(confidence_breakdown=[], ai_explanation=[]))
        self.assertEqual(brief["why_suspicious"], [])


class TestNextSteps(unittest.TestCase):
    def test_suggest_freeze_action(self):
        brief = copilot.generate_brief(_report())
        steps = [s["step"] for s in brief["next_steps"]]
        self.assertTrue(any("freeze" in s.lower() for s in steps))

    def test_suggest_kyc_action(self):
        brief = copilot.generate_brief(_report(decision={"action": "suggest_kyc", "rationale": "x"}))
        steps = [s["step"] for s in brief["next_steps"]]
        self.assertTrue(any("kyc" in s.lower() for s in steps))

    def test_manual_review_with_mixer_suggests_escalation(self):
        brief = copilot.generate_brief(_report(
            decision={"action": "manual_review", "rationale": "mixer"},
            mixer_hit={"label": "Known Mixer", "address": "0xM"},
        ))
        steps = [s["step"] for s in brief["next_steps"]]
        self.assertTrue(any("escalate" in s.lower() for s in steps))

    def test_insufficient_evidence_action(self):
        brief = copilot.generate_brief(_report(decision={"action": "insufficient_evidence", "rationale": "x"}))
        steps = [s["step"] for s in brief["next_steps"]]
        self.assertTrue(any("clos" in s.lower() for s in steps))

    def test_linked_cases_add_a_cross_reference_step(self):
        brief = copilot.generate_brief(_report(linked_case_details=[{"case_id": "c2", "ncrp_ref": "NCRP-2"}]))
        steps = [s["step"] for s in brief["next_steps"]]
        self.assertTrue(any("linked open case" in s for s in steps))

    def test_structuring_pattern_adds_a_step(self):
        brief = copilot.generate_brief(_report(risk_patterns=[
            {"pattern": "structuring", "severity": "high", "label": "x", "evidence": "evidence text"}
        ]))
        steps = [s["step"] for s in brief["next_steps"]]
        self.assertTrue(any("structuring" in s.lower() for s in steps))

    def test_no_linked_cases_no_extra_step(self):
        brief = copilot.generate_brief(_report(linked_case_details=[]))
        steps = [s["step"] for s in brief["next_steps"]]
        self.assertFalse(any("linked open case" in s for s in steps))


class TestGenerateBrief(unittest.TestCase):
    def test_headline_mentions_freeze_for_suggest_freeze(self):
        brief = copilot.generate_brief(_report())
        self.assertIn("freeze", brief["headline"].lower())

    def test_headline_mentions_mixer_when_blocked(self):
        brief = copilot.generate_brief(_report(
            decision={"action": "manual_review", "rationale": "mixer"},
            mixer_hit={"label": "Known Mixer", "address": "0xM"},
        ))
        self.assertIn("mixer", brief["headline"].lower())

    def test_confidence_and_label_are_carried_through(self):
        brief = copilot.generate_brief(_report(confidence=0.55, decision={"action": "suggest_kyc", "rationale": "x"}))
        self.assertEqual(brief["confidence"], 0.55)
        self.assertEqual(brief["confidence_label"], "Medium")


if __name__ == "__main__":
    unittest.main()
