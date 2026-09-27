import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import main as vajra_server


class TestTraceRateLimiter(unittest.TestCase):
    def setUp(self):
        vajra_server._rate_buckets.clear()

    def test_allows_up_to_the_limit(self):
        for _ in range(vajra_server.RATE_LIMIT_PER_HOUR):
            self.assertFalse(vajra_server._rate_limited("off-x"))

    def test_blocks_after_the_limit(self):
        for _ in range(vajra_server.RATE_LIMIT_PER_HOUR):
            vajra_server._rate_limited("off-y")
        self.assertTrue(vajra_server._rate_limited("off-y"))

    def test_buckets_are_independent_per_officer(self):
        for _ in range(vajra_server.RATE_LIMIT_PER_HOUR):
            vajra_server._rate_limited("off-a")
        self.assertTrue(vajra_server._rate_limited("off-a"))
        self.assertFalse(vajra_server._rate_limited("off-b"))


class TestLoginBruteForceProtection(unittest.TestCase):
    def setUp(self):
        vajra_server._login_fail_buckets.clear()

    def test_not_locked_out_initially(self):
        self.assertFalse(vajra_server._login_locked_out("MHA-CY-00001"))

    def test_locks_out_after_max_attempts(self):
        for _ in range(vajra_server.LOGIN_MAX_ATTEMPTS):
            vajra_server._record_login_failure("MHA-CY-00002")
        self.assertTrue(vajra_server._login_locked_out("MHA-CY-00002"))

    def test_successful_login_clears_the_bucket(self):
        for _ in range(vajra_server.LOGIN_MAX_ATTEMPTS):
            vajra_server._record_login_failure("MHA-CY-00003")
        vajra_server._clear_login_failures("MHA-CY-00003")
        self.assertFalse(vajra_server._login_locked_out("MHA-CY-00003"))

    def test_lockout_is_independent_per_officer_code(self):
        for _ in range(vajra_server.LOGIN_MAX_ATTEMPTS):
            vajra_server._record_login_failure("MHA-CY-00004")
        self.assertTrue(vajra_server._login_locked_out("MHA-CY-00004"))
        self.assertFalse(vajra_server._login_locked_out("MHA-CY-00005"))


if __name__ == "__main__":
    unittest.main()
