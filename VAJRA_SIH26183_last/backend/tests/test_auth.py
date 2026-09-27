import unittest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt as _pyjwt
from engine import cache  # unused directly, keeps import order consistent with other test files
import auth


class TestIssueAndVerifyToken(unittest.TestCase):
    def test_issue_token_returns_a_string(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-001", "Mumbai")
        self.assertIsInstance(token, str)

    def test_verify_token_roundtrips_all_fields(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-001", "Mumbai")
        payload = auth.verify_token(token)
        self.assertEqual(payload["sub"], "off-1")
        self.assertEqual(payload["role"], "officer")
        self.assertEqual(payload["officer_code"], "MHA-CY-001")
        self.assertEqual(payload["jurisdiction"], "Mumbai")

    def test_verify_token_includes_issued_at_and_expiry(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-001", "Mumbai")
        payload = auth.verify_token(token)
        self.assertIn("iat", payload)
        self.assertIn("exp", payload)
        self.assertGreater(payload["exp"], payload["iat"])

    def test_default_ttl_matches_fifteen_minutes(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-001", "Mumbai")
        payload = auth.verify_token(token)
        self.assertEqual(payload["exp"] - payload["iat"], 15 * 60)

    def test_custom_ttl_is_respected(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-001", "Mumbai", ttl=3600)
        payload = auth.verify_token(token)
        self.assertEqual(payload["exp"] - payload["iat"], 3600)

    def test_expired_token_raises_token_error(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-001", "Mumbai", ttl=-10)
        with self.assertRaises(auth.TokenError):
            auth.verify_token(token)

    def test_expired_token_error_message_mentions_expired(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-001", "Mumbai", ttl=-10)
        with self.assertRaises(auth.TokenError) as ctx:
            auth.verify_token(token)
        self.assertIn("expired", str(ctx.exception).lower())

    def test_tampered_token_raises_token_error(self):
        token = auth.issue_token("off-1", "officer", "MHA-CY-001", "Mumbai")
        tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
        with self.assertRaises(auth.TokenError):
            auth.verify_token(tampered)

    def test_garbage_string_raises_token_error_not_a_crash(self):
        with self.assertRaises(auth.TokenError):
            auth.verify_token("this-is-not-a-jwt-at-all")

    def test_token_signed_with_different_secret_is_rejected(self):
        forged = _pyjwt.encode(
            {"sub": "attacker", "role": "admin", "exp": int(time.time()) + 3600},
            "some-other-secret-entirely", algorithm="HS256",
        )
        with self.assertRaises(auth.TokenError):
            auth.verify_token(forged)

    def test_refresh_token_has_refresh_role(self):
        refresh = auth.issue_refresh_token("off-1")
        payload = auth.verify_token(refresh)
        self.assertEqual(payload["role"], "refresh")

    def test_refresh_token_ttl_is_seven_days(self):
        refresh = auth.issue_refresh_token("off-1")
        payload = auth.verify_token(refresh)
        self.assertEqual(payload["exp"] - payload["iat"], 7 * 24 * 3600)

    def test_refresh_token_carries_the_officer_id_as_sub(self):
        refresh = auth.issue_refresh_token("officer-xyz")
        payload = auth.verify_token(refresh)
        self.assertEqual(payload["sub"], "officer-xyz")


class TestUsingDefaultSecret(unittest.TestCase):
    def setUp(self):
        self._orig_secret = auth.SECRET

    def tearDown(self):
        auth.SECRET = self._orig_secret

    def test_default_secret_detected_as_default(self):
        auth.SECRET = auth._DEFAULT_SECRET
        self.assertTrue(auth.using_default_secret())

    def test_custom_secret_is_not_flagged_as_default(self):
        auth.SECRET = "a-real-production-secret-value"
        self.assertFalse(auth.using_default_secret())


class TestRolePermissions(unittest.TestCase):
    def test_reporter_can_submit_case(self):
        self.assertTrue(auth.has_permission("reporter", "submit_case"))

    def test_reporter_cannot_run_trace(self):
        self.assertFalse(auth.has_permission("reporter", "run_trace"))

    def test_reporter_cannot_approve_notice(self):
        self.assertFalse(auth.has_permission("reporter", "approve_notice"))

    def test_officer_can_run_trace(self):
        self.assertTrue(auth.has_permission("officer", "run_trace"))

    def test_officer_can_draft_notice(self):
        self.assertTrue(auth.has_permission("officer", "draft_notice"))

    def test_officer_cannot_approve_notice(self):
        self.assertFalse(auth.has_permission("officer", "approve_notice"))

    def test_officer_cannot_reassign_case(self):
        self.assertFalse(auth.has_permission("officer", "reassign_case"))

    def test_officer_cannot_view_cross_jurisdiction(self):
        self.assertFalse(auth.has_permission("officer", "cross_jurisdiction_view"))

    def test_supervisor_can_approve_notice(self):
        self.assertTrue(auth.has_permission("supervisor", "approve_notice"))

    def test_supervisor_can_reassign_case(self):
        self.assertTrue(auth.has_permission("supervisor", "reassign_case"))

    def test_supervisor_cannot_view_cross_jurisdiction(self):
        self.assertFalse(auth.has_permission("supervisor", "cross_jurisdiction_view"))

    def test_supervisor_cannot_view_audit_log(self):
        self.assertFalse(auth.has_permission("supervisor", "view_audit_log"))

    def test_admin_has_every_officer_permission(self):
        for perm in auth.ROLE_PERMISSIONS["supervisor"]:
            self.assertTrue(auth.has_permission("admin", perm))

    def test_admin_can_view_cross_jurisdiction(self):
        self.assertTrue(auth.has_permission("admin", "cross_jurisdiction_view"))

    def test_admin_can_view_audit_log(self):
        self.assertTrue(auth.has_permission("admin", "view_audit_log"))

    def test_admin_can_access_system_config(self):
        self.assertTrue(auth.has_permission("admin", "system_config"))

    def test_unknown_role_has_no_permissions(self):
        self.assertFalse(auth.has_permission("hacker", "run_trace"))

    def test_unknown_permission_on_known_role_is_false(self):
        self.assertFalse(auth.has_permission("admin", "delete_everything"))

    def test_role_permissions_table_has_exactly_four_roles(self):
        self.assertEqual(set(auth.ROLE_PERMISSIONS.keys()), {"reporter", "officer", "supervisor", "admin"})


if __name__ == "__main__":
    unittest.main()
