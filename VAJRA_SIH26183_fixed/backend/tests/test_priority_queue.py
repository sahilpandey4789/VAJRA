import unittest
import sys
import os
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.priority import compute_case_priority, _hours_since, _golden_hour_component


def _case(attribution_tier="UNATTRIBUTED", risk_band="low", syndicate_alert_tier=None, status="new"):
    return {
        "attribution_tier": attribution_tier,
        "risk_band": risk_band,
        "syndicate_alert_tier": syndicate_alert_tier,
        "status": status,
    }


NOW = datetime.datetime(2026, 9, 18, 12, 0, 0, tzinfo=datetime.timezone.utc)


class TestGoldenHourDecay(unittest.TestCase):
    def test_no_timestamp_gives_no_component(self):
        self.assertEqual(_golden_hour_component(None), (0, None))

    def test_fresh_hit_scores_highest(self):
        points, label = _golden_hour_component(2.0)
        self.assertEqual(points, 15)
        self.assertIn("freshest", label)

    def test_day_old_hit_scores_medium(self):
        points, _ = _golden_hour_component(20)
        self.assertEqual(points, 10)

    def test_three_day_old_hit_scores_low(self):
        points, _ = _golden_hour_component(50)
        self.assertEqual(points, 5)

    def test_stale_hit_scores_zero(self):
        points, label = _golden_hour_component(200)
        self.assertEqual(points, 0)
        self.assertIn("stale", label)

    def test_hours_since_parses_z_suffix_iso(self):
        h = _hours_since("2026-09-18T10:00:00Z", now=NOW)
        self.assertAlmostEqual(h, 2.0, places=3)

    def test_hours_since_none_input_is_none(self):
        self.assertIsNone(_hours_since(None, now=NOW))

    def test_hours_since_malformed_input_is_none_not_a_crash(self):
        self.assertIsNone(_hours_since("not-a-date", now=NOW))


class TestComputeCasePriority(unittest.TestCase):
    def test_untraced_case_scores_low_and_says_so(self):
        result = compute_case_priority(_case(), latest_report=None, case_notices=[], now=NOW)
        self.assertEqual(result["urgency"], "low")
        self.assertIn("not traced yet", " ".join(result["reasons"]))

    def test_confirmed_high_risk_fresh_exchange_hit_is_critical(self):
        report = {"exchange_match": {"exchange": "WazirX", "matched_at": "2026-09-18T10:00:00Z"}}
        result = compute_case_priority(
            _case(attribution_tier="CONFIRMED", risk_band="high"),
            latest_report=report, case_notices=[], now=NOW,
        )
        self.assertEqual(result["urgency"], "critical")
        self.assertEqual(result["hours_since_exchange_hit"], 2.0)
        self.assertTrue(any("actionable now" in r for r in result["reasons"]))

    def test_notice_already_sent_drops_score_and_says_monitoring(self):
        report = {"exchange_match": {"exchange": "WazirX", "matched_at": "2026-09-18T10:00:00Z"}}
        with_pending = compute_case_priority(
            _case(attribution_tier="CONFIRMED", risk_band="high"),
            latest_report=report, case_notices=[], now=NOW,
        )
        with_sent = compute_case_priority(
            _case(attribution_tier="CONFIRMED", risk_band="high"),
            latest_report=report, case_notices=[{"status": "sent"}], now=NOW,
        )
        self.assertLess(with_sent["score"], with_pending["score"])
        self.assertTrue(any("monitoring only" in r for r in with_sent["reasons"]))

    def test_pending_approval_drops_score_less_than_sent(self):
        report = {"exchange_match": {"exchange": "WazirX", "matched_at": "2026-09-18T10:00:00Z"}}
        pending = compute_case_priority(
            _case(attribution_tier="CONFIRMED", risk_band="high"),
            latest_report=report, case_notices=[{"status": "pending_approval"}], now=NOW,
        )
        sent = compute_case_priority(
            _case(attribution_tier="CONFIRMED", risk_band="high"),
            latest_report=report, case_notices=[{"status": "sent"}], now=NOW,
        )
        self.assertGreater(pending["score"], sent["score"])

    def test_mixer_only_case_scores_low_but_nonzero(self):
        report = {"exchange_match": None, "mixer_hit": {"label": "Tornado-style mixer"}}
        result = compute_case_priority(_case(risk_band="medium"), latest_report=report, case_notices=[], now=NOW)
        self.assertTrue(any("mixer" in r for r in result["reasons"]))
        self.assertGreater(result["score"], 0)

    def test_critical_syndicate_alert_boosts_score(self):
        report = {"exchange_match": {"exchange": "WazirX", "matched_at": "2026-09-18T10:00:00Z"}}
        base = compute_case_priority(_case(attribution_tier="PROBABLE", risk_band="medium"),
                                      latest_report=report, case_notices=[], now=NOW)
        boosted = compute_case_priority(
            _case(attribution_tier="PROBABLE", risk_band="medium", syndicate_alert_tier="CRITICAL"),
            latest_report=report, case_notices=[], now=NOW,
        )
        self.assertGreater(boosted["score"], base["score"])
        self.assertTrue(any("CRITICAL syndicate" in r for r in boosted["reasons"]))

    def test_score_is_always_clamped_0_to_100(self):
        report = {"exchange_match": {"exchange": "WazirX", "matched_at": "2026-09-18T11:59:00Z"}}
        result = compute_case_priority(
            _case(attribution_tier="CONFIRMED", risk_band="high", syndicate_alert_tier="CRITICAL"),
            latest_report=report, case_notices=[], now=NOW,
        )
        self.assertLessEqual(result["score"], 100)
        self.assertGreaterEqual(result["score"], 0)

    def test_low_risk_untraced_case_stays_at_low_urgency(self):
        result = compute_case_priority(
            _case(attribution_tier="UNATTRIBUTED", risk_band="low"),
            latest_report=None, case_notices=[], now=NOW,
        )
        self.assertEqual(result["urgency"], "low")
        self.assertIsNone(result["hours_since_exchange_hit"])


if __name__ == "__main__":
    unittest.main()
