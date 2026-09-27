import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import ofac_sanctions, scoring


class TestOfacSanctionsLookup(unittest.TestCase):
    def test_known_address_matches_case_insensitive_for_evm(self):
        hit = ofac_sanctions.lookup("0x08723392ed15743cc38513c4925f5e6be5c17243")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["entity_name"], "Lazarus Group")
        self.assertIn("DPRK3", hit["programs"])

    def test_btc_address_is_case_sensitive_exact_match(self):
        hit = ofac_sanctions.lookup("35irs2AU6pVgenYbWvMRz22avDBLC9XMkd")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["entity_name"], "Chen Zhi")

    def test_unknown_address_returns_none(self):
        self.assertIsNone(ofac_sanctions.lookup("not-a-real-address"))

    def test_none_and_empty_do_not_crash(self):
        self.assertIsNone(ofac_sanctions.lookup(None))
        self.assertIsNone(ofac_sanctions.lookup(""))

    def test_dataset_has_both_evm_and_bitcoin_entries(self):
        chains = {row[1] for row in ofac_sanctions.SANCTIONED_ADDRESSES}
        self.assertIn("ETHEREUM", chains)
        self.assertIn("BITCOIN", chains)


class TestAttributionTierSanctionsMatch(unittest.TestCase):
    def test_sanctions_match_forces_confirmed_even_at_low_confidence(self):
        result = scoring.attribution_tier(confidence=0.05, exchange_matched=False, mixer_penalty=0.0, sanctions_matched=True)
        self.assertEqual(result["tier"], "CONFIRMED")
        self.assertIn("OFAC", result["reason"])

    def test_sanctions_match_overrides_mixer_block(self):
        # A sanctioned address is real, first-party evidence regardless of
        # whether the trail continues past a mixer downstream - see
        # engine/scoring.py's attribution_tier() docstring.
        result = scoring.attribution_tier(confidence=0.05, exchange_matched=False, mixer_penalty=1.0, sanctions_matched=True)
        self.assertEqual(result["tier"], "CONFIRMED")

    def test_no_sanctions_match_falls_through_to_existing_logic(self):
        result = scoring.attribution_tier(confidence=0.5, exchange_matched=False, mixer_penalty=0.0, sanctions_matched=False)
        self.assertEqual(result["tier"], "PROBABLE")

    def test_sanctions_matched_defaults_false_backward_compatible(self):
        result = scoring.attribution_tier(confidence=0.5, exchange_matched=False, mixer_penalty=0.0)
        self.assertEqual(result["tier"], "PROBABLE")


if __name__ == "__main__":
    unittest.main()
