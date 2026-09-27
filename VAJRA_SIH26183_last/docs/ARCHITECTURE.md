# Architecture

## Why this shape

The Master Document specifies a production architecture of FastAPI +
Celery + Redis + PostgreSQL + Neo4j + WebSockets, deployed behind an
API gateway. This build runs the **real FastAPI** - `backend/main.py`
is a real `FastAPI()` app run under `uvicorn`, booting and serving live
HTTP responses. The remaining substitutions below are still genuine,
deliberate architectural stand-ins for the pieces that only earn their
keep at a scale this demo doesn't need yet - not missing features:

| Production spec        | This build            | Why it's equivalent here |
|------------------------|------------------------|---------------------------|
| FastAPI                | **FastAPI (real)** - `backend/main.py`, run via `uvicorn`. Verified: boots, seeds the DB, serves `/api/auth/login`, `/api/cases`, `/api/notices/*` etc. over real HTTP. | No longer a stand-in - this is the actual production framework, already in place. |
| Celery + Redis (async workers) | Synchronous pipeline run in a request thread, pushed live via SSE | The fixture data is small enough that the whole pipeline runs in under a second; the *shape* of the async progress protocol (discrete named stages, each with a detail string) is identical to what a Celery task would emit over Redis pub/sub. |
| WebSockets              | Server-Sent Events (`text/event-stream`) | One-directional server→client push is all the live trace-progress UI needs. SSE needs zero extra dependencies and works over plain HTTP/1.1. Swapping to WS in production is a transport change, not a redesign - the event payloads (`{stage, detail}`, final `{...report}`) stay the same. |
| PostgreSQL              | SQLite                | Schema uses only ANSI-standard SQL features (no SQLite-only syntax), explicit foreign keys, and ISO-8601 timestamp strings - a `psycopg2` connection string swap in `db.py::get_conn()` is the entire migration. |
| Neo4j (cross-case graph)| Real union-find graph in Python/SQLite (`engine/case_graph.py`) | Genuinely computes the query Neo4j would answer - direct and transitive links via shared laundering-path addresses, known exchange/mixer infrastructure excluded - not a fixture. A graph database earns its keep at cross-jurisdiction scale (thousands of concurrent cases, sub-second queries across a national index); a single cyber cell's case list is a few hundred nodes at most, well within what an in-process union-find handles instantly. See `docs/BUILT_VS_ROADMAP.md` for the exact threshold. |
| Etherscan / TronScan / Blockstream APIs | Offline fixture transaction graphs, served through a real adapter interface (`engine/chain_adapters.py`) | The adapter interface, and the exact HTTP endpoint the live adapter would call, are written and documented; only the actual outbound HTTP call hasn't been exercised against real provider traffic yet. Flip `VAJRA_LIVE_MODE=1` with a real `ETHERSCAN_API_KEY` - this is the single highest-priority "prove it's real" action item before a demo. |

## Request flow (trace)

```
Officer clicks "Run trace"
  → GET /api/trace/{case_id}/stream  (SSE, JWT in ?token=)
      → server.py validates auth + RBAC + rate limit
      → engine/tracer.py:run_trace()
          1. collecting  → chain_adapters.get_adapter().fetch_forward_transactions()
          2. tracing     → hop counting
          3. clustering  → clustering.build_clusters() (co-spend / change-address)
          4. checking    → mixer-contract lookup, peel-chain detection
          5. scoring     → ml_model.predict_illicit_probability() + scoring.score()
      → each stage emits an SSE `stage` event as it completes
      → final SSE `result` event carries the full report (JSON, SHA-256-hashed)
      → report persisted to trace_reports; case row updated
  ← frontend renders fund-flow graph, ledger, confidence breakdown, decision
```

## API dependency & resilience (documented, not yet load-tested)

Production deployment needs: primary/backup chain-API failover (e.g.
Etherscan → Alchemy → Infura), exponential backoff on HTTP 429, and a
short-TTL cache (Redis) in front of chain APIs to stay within free-tier
rate limits during a spike of simultaneous investigations. The adapter
interface in `engine/chain_adapters.py` is exactly the seam this slots
into - `LiveEtherscanAdapter.fetch_forward_transactions()` is where the
retry/cache wrapper goes.

## Security notes (also see docs/BUILT_VS_ROADMAP.md)

- Passwords are hashed with **Argon2id** (`argon2-cffi`, library-default
  parameters: memory 64MB, 3 iterations, 4 parallel lanes) - OWASP's
  current top recommendation. This build previously used PBKDF2-HMAC-
  SHA256; that swap is done (`db.py::_hash_password` / `verify_password`),
  verified live: correct password → 200, wrong password → 401, and the
  stored hash is a real `$argon2id$...` string, not a legacy PBKDF2 hex
  digest. `verify_password()` still recognises old PBKDF2 hashes as a
  migration fallback, so no already-seeded account is broken by the swap.
- JWTs are HMAC-SHA256, 15-minute access token TTL, matching the
  Technical Defense Document's stated session policy.
- Rate limiting is in-memory (60 wallet queries/hour/officer) - fine for
  a single-process demo, needs to move to Redis for multi-worker
  deployments.
- All mutating actions (trace run, notice draft/approve/send, vault
  download) are written to `audit_log` with officer id, timestamp and
  IP, exactly as specified.
