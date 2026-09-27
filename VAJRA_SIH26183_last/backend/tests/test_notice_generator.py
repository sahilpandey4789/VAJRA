import unittest
import sys
import os
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import notice_generator as ng


def _case_row(ncrp_ref="NCRP-2026-00001", suspect_wallet="0xabc123"):
    return {"ncrp_ref": ncrp_ref, "suspect_wallet": suspect_wallet}


def _report(confidence=0.85, exchange_match=None, report_hash="a1b2c3d4e5f6g7h8i9j0"):
    return {"confidence": confidence, "exchange_match": exchange_match, "report_hash": report_hash}


class TestNoticeGenerate(unittest.TestCase):
    def test_unknown_notice_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            ng.generate("not_a_real_type", _case_row(), _report(), "Officer X", "Mumbai")

    def test_freeze_notice_has_correct_subject(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(), "R. Kulkarni", "Mumbai")
        self.assertIn("102 CrPC", result["subject"])

    def test_kyc_disclosure_notice_has_correct_subject(self):
        result = ng.generate("kyc_disclosure", _case_row(), _report(), "R. Kulkarni", "Mumbai")
        self.assertIn("94 BNSS", result["subject"])

    def test_notice_type_is_echoed_back(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(), "Officer", "Delhi")
        self.assertEqual(result["notice_type"], "freeze_102_crpc")

    def test_body_includes_ncrp_ref(self):
        result = ng.generate("freeze_102_crpc", _case_row(ncrp_ref="NCRP-2026-99999"), _report(), "Officer", "Delhi")
        self.assertIn("NCRP-2026-99999", result["body"])

    def test_body_includes_suspect_wallet(self):
        result = ng.generate("freeze_102_crpc", _case_row(suspect_wallet="0xDEADBEEF"), _report(), "Officer", "Delhi")
        self.assertIn("0xDEADBEEF", result["body"])

    def test_body_includes_officer_name(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(), "S. Pillai", "Chennai")
        self.assertIn("S. Pillai", result["body"])

    def test_body_includes_jurisdiction(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(), "Officer", "Bengaluru City Police")
        self.assertIn("Bengaluru City Police", result["body"])

    def test_confidence_percentage_is_rounded_and_included(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(confidence=0.847), "Officer", "Delhi")
        self.assertIn("85%", result["body"])

    def test_confidence_zero_renders_as_zero_percent(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(confidence=0.0), "Officer", "Delhi")
        self.assertIn("0%", result["body"])

    def test_confidence_one_renders_as_hundred_percent(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(confidence=1.0), "Officer", "Delhi")
        self.assertIn("100%", result["body"])

    def test_with_exchange_match_uses_real_exchange_name(self):
        report = _report(exchange_match={"exchange": "WazirX", "address": "0xExchangeDeposit"})
        result = ng.generate("freeze_102_crpc", _case_row(), report, "Officer", "Delhi")
        self.assertIn("WazirX", result["body"])
        self.assertEqual(result["exchange_name"], "WazirX")

    def test_with_exchange_match_uses_real_deposit_wallet_address(self):
        report = _report(exchange_match={"exchange": "WazirX", "address": "0xExchangeDeposit"})
        result = ng.generate("freeze_102_crpc", _case_row(), report, "Officer", "Delhi")
        self.assertIn("0xExchangeDeposit", result["body"])

    def test_without_exchange_match_falls_back_to_unknown_vasp(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(exchange_match=None), "Officer", "Delhi")
        self.assertIn("Unknown VASP", result["body"])
        self.assertEqual(result["exchange_name"], "Unknown VASP")

    def test_without_exchange_match_deposit_wallet_placeholder_present(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(exchange_match=None), "Officer", "Delhi")
        self.assertIn("see evidence pack", result["body"])

    def test_report_hash_is_truncated_with_ellipsis(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(report_hash="abcdef1234567890xyz"), "Officer", "Delhi")
        self.assertIn("abcdef", result["body"])
        self.assertIn("…", result["body"])

    def test_sla_due_is_iso_format_string(self):
        result = ng.generate("freeze_102_crpc", _case_row(), _report(), "Officer", "Delhi")
        # must parse cleanly as ISO 8601 with Z suffix
        parsed = datetime.datetime.strptime(result["sla_due"], "%Y-%m-%dT%H:%M:%SZ")
        self.assertIsInstance(parsed, datetime.datetime)

    def test_sla_due_is_approximately_seven_days_ahead(self):
        before = datetime.datetime.utcnow()
        result = ng.generate("freeze_102_crpc", _case_row(), _report(), "Officer", "Delhi")
        sla_due = datetime.datetime.strptime(result["sla_due"], "%Y-%m-%dT%H:%M:%SZ")
        delta_days = (sla_due - before).total_seconds() / 86400
        self.assertGreater(delta_days, 6.9)
        self.assertLess(delta_days, 7.1)

    def test_kyc_disclosure_sla_is_also_seven_days(self):
        before = datetime.datetime.utcnow()
        result = ng.generate("kyc_disclosure", _case_row(), _report(), "Officer", "Delhi")
        sla_due = datetime.datetime.strptime(result["sla_due"], "%Y-%m-%dT%H:%M:%SZ")
        delta_days = (sla_due - before).total_seconds() / 86400
        self.assertGreater(delta_days, 6.9)
        self.assertLess(delta_days, 7.1)

    def test_freeze_and_kyc_bodies_differ_for_same_inputs(self):
        freeze = ng.generate("freeze_102_crpc", _case_row(), _report(), "Officer", "Delhi")
        kyc = ng.generate("kyc_disclosure", _case_row(), _report(), "Officer", "Delhi")
        self.assertNotEqual(freeze["body"], kyc["body"])

    def test_templates_dict_has_exactly_the_two_documented_types(self):
        self.assertEqual(set(ng.TEMPLATES.keys()), {"freeze_102_crpc", "kyc_disclosure"})


if __name__ == "__main__":
    unittest.main()
