import unittest
import sys
import os
import tempfile
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# DB_PATH must be overridden BEFORE main.py's startup event calls
# db.init_db() (which happens when TestClient enters the app's lifespan
# below) - and it has to be a mutation of the live db.DB_PATH global,
# not just os.environ, because db.py already read VAJRA_DB_PATH at
# import time. db.get_conn() re-reads the DB_PATH global on every call
# (see its docstring/comment), so mutating it here - regardless of
# whichever test file happened to import `db` first during discovery - # reliably redirects every connection the app opens for the rest of
# this test file to an isolated temp database, never the real
# development vajra.db.
import db

_TEST_DB = os.path.join(tempfile.gettempdir(), f"vajra_api_test_{os.getpid()}.db")
db.DB_PATH = _TEST_DB
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)
db.init_db(force_reseed=True)

import main
from fastapi.testclient import TestClient


class TestAPIIntegration(unittest.TestCase):
    """
    Every previous test file in this suite exercises engine/ modules as
    pure functions. This file is different on purpose: it drives the
    actual FastAPI app through real HTTP-shaped requests (TestClient
    talks the real ASGI protocol, not a mocked shortcut), against a real - if temporary and isolated - SQLite database, seeded exactly the
    way `python main.py` seeds it for a live demo. It's the automated
    version of the manual curl/requests checks used throughout this
    project's development passes, now permanent and re-runnable.
    """

    @classmethod
    def setUpClass(cls):
        cls._cm = TestClient(main.app)
        cls.client = cls._cm.__enter__()  # triggers the real FastAPI startup event

    @classmethod
    def tearDownClass(cls):
        cls._cm.__exit__(None, None, None)
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)

    def _login(self, code="MHA-CY-08231", password="vajra123"):
        return self.client.post("/api/auth/login", json={"officer_code": code, "password": password})

    def _officer_token(self):
        return self._login().json()["access_token"]

    def _supervisor_token(self):
        return self._login(code="MHA-CY-04410").json()["access_token"]

    def _auth_headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    # ---- health ----
    def test_health_check_returns_200(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)

    # ---- login: valid paths ----
    def test_valid_login_returns_200(self):
        self.assertEqual(self._login().status_code, 200)

    def test_valid_login_returns_access_and_refresh_tokens(self):
        body = self._login().json()
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)

    def test_valid_login_returns_officer_details(self):
        body = self._login().json()
        self.assertEqual(body["officer"]["officer_code"], "MHA-CY-08231")
        self.assertEqual(body["officer"]["role"], "officer")

    def test_supervisor_login_returns_supervisor_role(self):
        body = self._login(code="MHA-CY-04410").json()
        self.assertEqual(body["officer"]["role"], "supervisor")

    # ---- login: invalid paths (business-logic validation, unchanged by the Pydantic pass) ----
    def test_wrong_password_returns_401(self):
        r = self._login(password="wrong-password-entirely")
        self.assertEqual(r.status_code, 401)

    def test_unknown_officer_code_returns_401(self):
        r = self._login(code="MHA-CY-99999")
        self.assertEqual(r.status_code, 401)

    # ---- login: Pydantic-level validation ----
    def test_officer_code_as_wrong_type_returns_422_not_500(self):
        r = self.client.post("/api/auth/login", json={"officer_code": 12345, "password": "vajra123"})
        self.assertEqual(r.status_code, 422)

    def test_missing_body_entirely_returns_422_not_500(self):
        r = self.client.post("/api/auth/login")
        self.assertEqual(r.status_code, 422)

    def test_malformed_json_returns_422_not_500(self):
        r = self.client.post(
            "/api/auth/login",
            content=b"not valid json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(r.status_code, 422)

    def test_empty_json_object_is_accepted_by_pydantic_then_rejected_by_business_logic(self):
        # {} is valid against LoginRequest (both fields default to ""),
        # so Pydantic lets it through - the *existing* "officer_code is
        # required" business-logic check downstream is what should catch
        # it, exactly as the app has always handled that case. This is the key
        # behavioural guarantee of the whole refactor: unchanged 400s for
        # cases the app already handled, only *new* 422s for genuinely
        # malformed input the app never handled cleanly before.
        r = self.client.post("/api/auth/login", json={})
        self.assertEqual(r.status_code, 400)

    def test_openapi_schema_documents_login_request_body(self):
        spec = self.client.get("/openapi.json").json()
        schema_ref = spec["paths"]["/api/auth/login"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        self.assertIn("$ref", schema_ref)
        self.assertIn("LoginRequest", schema_ref["$ref"])

    # ---- auth-gated endpoints ----
    def test_cases_list_without_token_returns_401(self):
        r = self.client.get("/api/cases")
        self.assertEqual(r.status_code, 401)

    def test_cases_list_with_valid_token_returns_200(self):
        r = self.client.get("/api/cases", headers=self._auth_headers(self._officer_token()))
        self.assertEqual(r.status_code, 200)

    def test_cases_list_returns_seeded_cases(self):
        r = self.client.get("/api/cases", headers=self._auth_headers(self._officer_token()))
        self.assertGreater(len(r.json()["cases"]), 0)

    def test_invalid_token_returns_401(self):
        r = self.client.get("/api/cases", headers=self._auth_headers("not-a-real-token"))
        self.assertEqual(r.status_code, 401)

    # ---- priority queue ----
    def test_priority_queue_returns_200(self):
        r = self.client.get("/api/cases/priority-queue", headers=self._auth_headers(self._officer_token()))
        self.assertEqual(r.status_code, 200)

    def test_priority_queue_entries_have_score_and_urgency(self):
        r = self.client.get("/api/cases/priority-queue?limit=3", headers=self._auth_headers(self._officer_token()))
        queue = r.json()["queue"]
        if queue:  # seeded data always has open cases, but guard anyway
            self.assertIn("score", queue[0])
            self.assertIn("urgency", queue[0])

    # ---- case creation validation ----
    def test_create_case_missing_wallet_returns_400(self):
        r = self.client.post("/api/cases", json={"chain": "ethereum"},
                              headers=self._auth_headers(self._officer_token()))
        self.assertEqual(r.status_code, 400)

    def test_create_case_invalid_chain_returns_400(self):
        r = self.client.post("/api/cases", json={"suspect_wallet": "0xabc", "chain": "dogecoin"},
                              headers=self._auth_headers(self._officer_token()))
        self.assertEqual(r.status_code, 400)

    def test_create_case_wrong_type_for_wallet_returns_422(self):
        r = self.client.post("/api/cases", json={"suspect_wallet": 12345, "chain": "ethereum"},
                              headers=self._auth_headers(self._officer_token()))
        self.assertEqual(r.status_code, 422)

    def test_create_case_without_auth_returns_401(self):
        r = self.client.post("/api/cases", json={"suspect_wallet": "0xabc", "chain": "ethereum"})
        self.assertEqual(r.status_code, 401)

    # ---- maker-checker (the flagship RBAC guarantee - re-verified as a real HTTP round-trip) ----
    def test_officer_cannot_approve_own_notice(self):
        officer_headers = self._auth_headers(self._officer_token())
        cases = self.client.get("/api/cases", headers=officer_headers).json()["cases"]
        case_id = cases[0]["id"]
        # trace first so a report exists for the notice generator to use
        with self.client.stream("GET", f"/api/trace/{case_id}/stream",
                                 params={"token": self._officer_token()}) as resp:
            for _ in resp.iter_lines():
                pass  # drain the SSE stream to completion
        draft = self.client.post("/api/notices", json={"case_id": case_id, "notice_type": "freeze_102_crpc"},
                                  headers=officer_headers)
        if draft.status_code != 201:
            self.skipTest(f"could not draft a notice on seeded case {case_id}: {draft.text}")
        notice_id = draft.json()["id"]
        approve = self.client.post(f"/api/notices/{notice_id}/approve", headers=officer_headers)
        self.assertEqual(approve.status_code, 403)

    def test_notice_type_wrong_type_returns_422(self):
        r = self.client.post("/api/notices", json={"case_id": "case-1", "notice_type": 5},
                              headers=self._auth_headers(self._officer_token()))
        self.assertEqual(r.status_code, 422)

    def test_notice_unknown_type_returns_400(self):
        cases = self.client.get("/api/cases", headers=self._auth_headers(self._officer_token())).json()["cases"]
        r = self.client.post("/api/notices", json={"case_id": cases[0]["id"], "notice_type": "not_a_real_type"},
                              headers=self._auth_headers(self._officer_token()))
        self.assertEqual(r.status_code, 400)

    # ---- request correlation IDs ----
    def test_response_includes_x_request_id_header(self):
        r = self.client.get("/api/health")
        self.assertIn("X-Request-ID", r.headers)
        self.assertGreater(len(r.headers["X-Request-ID"]), 0)

    def test_client_supplied_request_id_is_echoed_back(self):
        r = self.client.get("/api/health", headers={"X-Request-ID": "my-custom-trace-id-123"})
        self.assertEqual(r.headers["X-Request-ID"], "my-custom-trace-id-123")

    def test_different_requests_get_different_request_ids(self):
        r1 = self.client.get("/api/health")
        r2 = self.client.get("/api/health")
        self.assertNotEqual(r1.headers["X-Request-ID"], r2.headers["X-Request-ID"])

    # ---- pagination on GET /api/cases ----
    def test_cases_list_includes_pagination_metadata(self):
        r = self.client.get("/api/cases", headers=self._auth_headers(self._officer_token()))
        body = r.json()
        for key in ("cases", "total", "limit", "offset"):
            self.assertIn(key, body)

    def test_cases_list_default_limit_is_200(self):
        body = self.client.get("/api/cases", headers=self._auth_headers(self._officer_token())).json()
        self.assertEqual(body["limit"], 200)

    def test_cases_list_respects_custom_limit(self):
        body = self.client.get("/api/cases?limit=1", headers=self._auth_headers(self._officer_token())).json()
        self.assertEqual(body["limit"], 1)
        self.assertLessEqual(len(body["cases"]), 1)

    def test_cases_list_limit_is_capped_at_500(self):
        body = self.client.get("/api/cases?limit=99999", headers=self._auth_headers(self._officer_token())).json()
        self.assertEqual(body["limit"], 500)

    def test_cases_list_limit_below_one_is_clamped_to_one(self):
        body = self.client.get("/api/cases?limit=0", headers=self._auth_headers(self._officer_token())).json()
        self.assertEqual(body["limit"], 1)

    def test_cases_list_total_matches_full_count_regardless_of_limit(self):
        headers = self._auth_headers(self._officer_token())
        full = self.client.get("/api/cases", headers=headers).json()
        limited = self.client.get("/api/cases?limit=1", headers=headers).json()
        self.assertEqual(full["total"], limited["total"])

    def test_cases_list_offset_skips_records(self):
        headers = self._auth_headers(self._officer_token())
        all_cases = self.client.get("/api/cases", headers=headers).json()["cases"]
        if len(all_cases) < 2:
            self.skipTest("not enough seeded cases in this jurisdiction to test offset")
        offset_page = self.client.get("/api/cases?limit=100&offset=1", headers=headers).json()["cases"]
        self.assertEqual(offset_page[0]["id"], all_cases[1]["id"])

    def test_cases_list_negative_offset_is_clamped_to_zero(self):
        headers = self._auth_headers(self._officer_token())
        r = self.client.get("/api/cases?offset=-5", headers=headers)
        self.assertEqual(r.json()["offset"], 0)

    # ---- global unhandled-exception handler ----
    def test_unhandled_exception_handler_returns_500_with_request_id(self):
        # Exercising this through a real route would mean deliberately
        # breaking a working endpoint just to test the failure path - # instead call the registered handler directly, the same way
        # Starlette would when a route raises an uncaught exception.
        import asyncio as _asyncio
        from starlette.requests import Request as StarletteRequest

        async def _run():
            scope = {"type": "http", "method": "GET", "path": "/api/fake",
                      "headers": [], "query_string": b"", "client": ("test", 0)}
            request = StarletteRequest(scope)
            request.state.request_id = "test-req-id-999"
            response = await main.unhandled_exception_handler(request, ValueError("simulated failure"))
            return response

        response = _asyncio.get_event_loop().run_until_complete(_run())
        self.assertEqual(response.status_code, 500)
        body = json.loads(response.body)
        self.assertEqual(body["request_id"], "test-req-id-999")
        self.assertEqual(body["detail"], "internal server error")
        self.assertNotIn("ValueError", str(body))  # never leak the exception type/message to the client

    def test_unhandled_exception_handler_falls_back_when_no_request_id_set(self):
        import asyncio as _asyncio
        from starlette.requests import Request as StarletteRequest

        async def _run():
            scope = {"type": "http", "method": "GET", "path": "/api/fake",
                      "headers": [], "query_string": b"", "client": ("test", 0)}
            request = StarletteRequest(scope)  # no request_id ever set on .state
            return await main.unhandled_exception_handler(request, RuntimeError("boom"))

        response = _asyncio.get_event_loop().run_until_complete(_run())
        body = json.loads(response.body)
        self.assertEqual(body["request_id"], "-")


if __name__ == "__main__":
    unittest.main()
