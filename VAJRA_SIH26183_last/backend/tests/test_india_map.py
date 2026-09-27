import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import india_map


def _case(jurisdiction, risk_band="medium", confidence=0.5, status="in_progress"):
    return {"jurisdiction": jurisdiction, "risk_band": risk_band, "confidence": confidence, "status": status}


class TestIndiaMapDistribution(unittest.TestCase):
    def test_parses_city_from_em_dash_jurisdiction_string(self):
        dist = india_map.national_distribution([_case("Cyber Crime Cell - Mumbai")])
        self.assertEqual(dist[0]["city"], "Mumbai")
        self.assertEqual(dist[0]["state"], "Maharashtra")

    def test_unknown_jurisdiction_falls_back_to_national(self):
        dist = india_map.national_distribution([_case("Some Unmapped Cell - Nowhere")])
        self.assertEqual(dist[0]["city"], "National")

    def test_aggregates_counts_and_risk_bands_correctly(self):
        cases = [
            _case("Cyber Crime Cell - Delhi", risk_band="high", confidence=0.9),
            _case("Cyber Crime Cell - Delhi", risk_band="low", confidence=0.1, status="cleared"),
        ]
        dist = india_map.national_distribution(cases)
        delhi = dist[0]
        self.assertEqual(delhi["cases"], 2)
        self.assertEqual(delhi["high_risk"], 1)
        self.assertEqual(delhi["low_risk"], 1)
        self.assertEqual(delhi["open_cases"], 1)  # the cleared one shouldn't count as open
        self.assertAlmostEqual(delhi["avg_confidence"], 0.5)

    def test_sorted_descending_by_case_count(self):
        cases = [_case("Cyber Crime Cell - Mumbai")] + [_case("Cyber Crime Cell - Delhi")] * 3
        dist = india_map.national_distribution(cases)
        self.assertEqual(dist[0]["city"], "Delhi")
        self.assertGreaterEqual(dist[0]["cases"], dist[1]["cases"])

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(india_map.national_distribution([]), [])


class TestCaseGeoTrail(unittest.TestCase):
    def test_resolved_exchange_returns_both_ends(self):
        trail = india_map.case_geo_trail(
            "Cyber Crime Cell - Mumbai",
            exchange_match={"exchange": "CoinDCX", "address": "0xabc"},
            mixer_hit=None,
        )
        self.assertEqual(trail["trail_type"], "resolved")
        self.assertEqual(trail["origin"]["city"], "Mumbai")
        self.assertEqual(trail["destination"]["city"], "Bengaluru")
        self.assertEqual(trail["exchange"], "CoinDCX")

    def test_origin_state_matches_jurisdiction_city(self):
        trail = india_map.case_geo_trail("Cyber Crime Cell - Delhi", exchange_match=None, mixer_hit=None)
        self.assertEqual(trail["origin"]["state"], "Delhi (NCT)")

    def test_unmapped_jurisdiction_falls_back_to_national_origin(self):
        trail = india_map.case_geo_trail("Some Unmapped Cell - Nowhere", exchange_match=None, mixer_hit=None)
        self.assertEqual(trail["origin"]["city"], "National")

    def test_international_exchange_has_no_destination_coordinates(self):
        trail = india_map.case_geo_trail(
            "Cyber Crime Cell - Delhi",
            exchange_match={"exchange": "Binance", "address": "0xdef"},
            mixer_hit=None,
        )
        self.assertEqual(trail["trail_type"], "international")
        self.assertIsNone(trail["destination"])
        self.assertEqual(trail["exchange"], "Binance")

    def test_mixer_hit_has_no_destination_and_no_exchange(self):
        trail = india_map.case_geo_trail(
            "Cyber Crime Cell - Mumbai", exchange_match=None, mixer_hit={"label": "TronMix"},
        )
        self.assertEqual(trail["trail_type"], "mixer")
        self.assertIsNone(trail["destination"])
        self.assertIsNone(trail["exchange"])

    def test_neither_exchange_nor_mixer_is_unresolved(self):
        trail = india_map.case_geo_trail("Cyber Crime Cell - Mumbai", exchange_match=None, mixer_hit=None)
        self.assertEqual(trail["trail_type"], "unresolved")
        self.assertIsNone(trail["destination"])

    def test_exchange_match_takes_priority_over_mixer_hit(self):
        # a report should never have both, but if it somehow did, a
        # resolved destination is more actionable information than a
        # mixer dead-end, so exchange wins.
        trail = india_map.case_geo_trail(
            "Cyber Crime Cell - Mumbai",
            exchange_match={"exchange": "WazirX", "address": "0xabc"},
            mixer_hit={"label": "TronMix"},
        )
        self.assertEqual(trail["trail_type"], "resolved")

    def test_unmapped_exchange_name_is_international_not_a_crash(self):
        trail = india_map.case_geo_trail(
            "Cyber Crime Cell - Mumbai",
            exchange_match={"exchange": "SomeFutureExchangeNotYetMapped", "address": "0xabc"},
            mixer_hit=None,
        )
        self.assertEqual(trail["trail_type"], "international")
        self.assertIsNone(trail["destination"])


if __name__ == "__main__":
    unittest.main()
