# Built vs. Roadmap

Stated up front, not discovered under questioning. This table is also
rendered live inside the console (About this build).

## Built and actually running

- **Clustering heuristics** - co-spend (shared-input union-find),
  change-address (never-seen, non-round output), deposit-fingerprint
  (unique-sender count + sweep-interval regularity via coefficient of
  variation). Real computation over the traced transaction list, not a
  lookup table. See `backend/engine/clustering.py`.
- **Attribution confidence formula** - the exact weighted sigmoid from
  the Technical Defense Document, with weights fit against the three
  known-outcome fixtures (a closed-form calibration, not logistic
  regression yet - see roadmap). See `backend/engine/scoring.py`.
- **AI illicit-probability classifier** - a real `RandomForestClassifier`
  (scikit-learn), trained at first run, serialized to disk, loaded and
  actually run at inference time for every trace. Training data is
  synthetic (engineered to match the Elliptic feature family) - the
  real Elliptic++ dataset requires a separate licensed download. See
  `backend/engine/ml_model.py` docstring for the full honesty note.
- **Legal notice drafting** - real template engine producing outcome-
  aware notices (freeze under 102 CrPC/106 BNSS vs. KYC-disclosure under
  94 BNSS/79(3)(b) IT Act), populated with real case/report data,
  including the SHA-256 evidence-pack hash. See
  `backend/engine/notice_generator.py`.
- **Maker-checker workflow** - enforced server-side, not just in the UI:
  an Officer cannot approve their own draft (`403`), a notice cannot be
  sent before Supervisor+ approval (`409`), and every step is logged.
- **RBAC** - three real roles (Officer/Supervisor/Admin) with a real
  permission table, checked on every route server-side.
- **Live progress** - Server-Sent Events streaming the actual pipeline's
  stage-by-stage progress, not a timed animation.
- **Persistence & audit** - real SQLite database (cases, notices,
  officers, audit log), foreign keys, immutable audit trail.
- **Cross-case link graph** - real union-find over every case's traced
  addresses, not the old hardcoded `linked_cases` fixture (which used to
  point at "NCRP-71005" / "NCRP-68894" - two case numbers that never
  existed anywhere else in this system). Known exchange hot wallets and
  known mixer contracts are excluded from the overlap check, so two
  cases both ending at the same exchange is never mistaken for a shared
  laundering network - only a shared *intermediate* wallet counts.
  Direct and transitive links both surface. Exposed via
  `GET /api/cases/{id}/network` (one case's connected component) and
  `GET /api/cases/network` (the full graph, rendered as an interactive
  SVG in the new **Case network** view) - both recomputed fresh on every
  request, never frozen at trace time. See `backend/engine/case_graph.py`
  and its docstring for exactly why this is the same graph query Neo4j
  would run, and where that swap actually earns its keep (below).
- **Advanced risk-pattern detection** - real heuristics over the actual
  traced transaction shape/timing, not a keyword-matched label: rapid
  sequential transfers (hop-to-hop gap under threshold), deep layering
  chains, structuring/smurfing (repeated small single-output transfers),
  high-fan-out transactions, and round-trip/self-dealing detection
  (funds looping back to the original suspect wallet after crossing
  intermediate hops - a wash-laundering signature), alongside the
  existing mixer/exchange checks. Every detected pattern carries the
  specific tx hashes that triggered it. See `backend/engine/risk_patterns.py`.
- **Investigation Copilot** - an explainable-AI reasoning layer, not a
  chatbot and not a second model: it narrates fields the pipeline
  already computed for real (the confidence-formula breakdown from
  `scoring.py`, the RandomForest's local feature attribution from
  `ml_model.py`, mixer/exchange/cross-case/pattern findings) into a
  ranked "why this wallet is flagged" list and a deterministic,
  rule-based "recommended next steps" list - every line traces back to
  a specific real field, so there is nothing here an investigator can't
  verify against the rest of the report. See `backend/engine/copilot.py`.
- **Investigation Timeline Replay** - a scrubbable slider (not just an
  autoplay button) over `report.transactions` in real chronological
  order, revealing the matching hop tier on the fund-flow graph as it
  moves and showing the exact transaction (hash, value, timestamp, and
  any mixer/exchange/structuring flag) at that position. Built entirely
  on data the pipeline already traced - no separate replay log. See
  `frontend/src/console-core/components/graph.js`'s `renderTimelineReplay`.
- **Offline-first frontend** - if the backend is unreachable, or every
  live provider fails, the console transparently serves an identical
  cached snapshot of computed output and clearly labels itself
  **OFFLINE DEMO** instead of **LIVE DATA**.

- **Live blockchain data with automatic failover** - real adapters for
  Etherscan+Blockscout (Ethereum), Blockstream+mempool.space (Bitcoin),
  TronGrid+TronScan (Tron): retry with exponential backoff, hard
  timeouts, and failover to the next provider before falling back to
  the offline fixture (never a crash, never a hang). Gated behind
  `VAJRA_LIVE_MODE=1` - off by default so the demo stays reproducible.
  **Note:** written directly against each provider's published
  API docs; not yet exercised against real live traffic. See
  `backend/engine/chain_adapters.py`.
- **AI explainability** - every trace ships a ranked list of feature
  contributions (`+ Peel chain detected`, `- No mixer`, …), not just a
  bare percentage. This is a documented SHAP-style local approximation
  built from the RandomForest's own `feature_importances_` (the real
  `shap` package isn't installable in this build's sandbox); the
  swap-in path to exact Shapley values is one line once it can be
  installed. See `ml_model.explain_prediction()`.
- **Cluster-quality diagnostic** - a 0–1 score summarising how well-
  corroborated the union-find clusters are for this trace, shown
  alongside the confidence breakdown so "why this number" always
  includes how much to trust the cluster groupings themselves. Kept
  separate from the calibrated 5-factor confidence formula rather than
  silently becoming an unweighted 6th input. See `clustering.py`.
- **Real evidence PDF reports** - generated with `reportlab` (not an
  HTML string with a `.pdf` extension): wallet, hop-flow diagram,
  confidence breakdown, AI reasons, SHA-256 hash, QR verification code
  (falls back to a printed hash block if the optional `qrcode` package
  isn't installed), and a digital-signature placeholder. See
  `backend/engine/evidence_report.py`.
- **Cache layer** - `engine/cache.py` uses real Redis if `REDIS_URL` is
  configured and the `redis` package is installed, and a thread-safe
  in-memory TTL cache otherwise, behind one identical interface.
- **Consumed refresh tokens** - `POST /api/auth/refresh` actually
  exchanges a refresh token for a new access token; see roadmap below
  for what's still stateless about it.
- **Searchable audit log & real dashboard stats** - `/api/audit-log`
  supports filtering by text, action, officer and date; `/api/stats`
  computes funds traced, pending approvals, exchange requests,
  blockchain distribution, today's activity and average trace time from
  the real database instead of a hardcoded `4.2`.
- **Exchange Risk Board** - `GET /api/exchanges/risk-board` reads the
  PS title literally ("identify fraud-linked cryptocurrency
  **exchanges**", not just trace one wallet): it aggregates every
  trace's `exchange_match` across all cases into a ranked list, scored
  as `linked_cases × avg_confidence` and normalized 0–1, jurisdiction-
  filtered the same way `/api/cases` is. An exchange that keeps
  reappearing across many high-confidence victim complaints ranks above
  one seen once. New console view: **Exchange risk board**. See the
  route in `backend/main.py` and `frontend/src/console-core/views/exchanges.js`.
- **Real-time alert broadcast** - `GET /api/alerts/stream` is a global
  SSE fan-out channel (thread-safe `AlertBroadcaster`, stdlib
  `queue.Queue`, same "no new framework" approach as everything else
  here): the moment *any* officer's trace completes as high-risk or
  hits a known exchange, *every* connected officer's console gets it
  live - a toast, the sidebar queue, and an open Exchange Risk Board all
  refresh immediately. Makes the PS's literal word "Real-Time" true
  instead of on-demand-only (previously: an officer only saw progress
  for the one trace they personally ran). Verified end-to-end: two
  independent SSE connections, one officer runs a trace, the other
  receives `high_risk_case` and `exchange_match` events within the same
  second. See `AlertBroadcaster` in `backend/main.py`.

## Production hardening pass (this build)

Done in response to the direct question "would you call this production-
ready" - the honest answer was "no," so here's what was actually fixable
without network access, tested end-to-end, not just written:

- **SQLite WAL mode + busy_timeout** (`db.get_conn()`) - readers no longer
  block behind a writer. Verified: 80 concurrent mixed-read requests across
  2 officers, 0 failures; 5 concurrent full trace pipelines (incl. 3 racing
  on the *same* case) completed in 1.4s with zero lock errors.
- **Fixed a real connection-leak bug in the trace SSE endpoint** - it
  declared `Connection: keep-alive` and then never closed server-side
  after the one-shot pipeline finished. The browser client already calls
  `es.close()` itself (see `api.js`), so this was invisible in normal use,
  but any client that didn't proactively disconnect (dropped network, a
  script, a crashed tab) would hold a `ThreadingHTTPServer` thread open
  forever - real thread-exhaustion risk at scale. Now closes
  deterministically server-side once the payload is flushed
  (`self.close_connection = True`). Found and fixed by actually load-testing
  concurrent trace runs, not by inspection.
- **JWT secret enforcement** - `VAJRA_ENV=production` now refuses to boot
  with the default dev signing secret (`auth.using_default_secret()`);
  otherwise prints a loud warning. Verified both paths (exit 1 vs. clean
  boot with a real secret set).
- **Login brute-force protection** - 8 failed attempts / 15 min locks that
  officer_code out, independent of IP (a shared-NAT government network
  makes IP-based limiting either useless or collectively punishing).
  Verified live: the 9th attempt with the *correct* password is still
  locked out.
- **`notice_type` input validation** - an unrecognized value used to hit an
  unhandled `ValueError` deep in `notice_generator.py`; now a clean `400`
  against the same `TEMPLATES` dict that's the actual source of truth.
- **Password hashing** - Argon2id (`argon2-cffi`), OWASP's current top
  recommendation, with a legacy-PBKDF2 fallback path so any
  previously-seeded account isn't broken by the migration. Verified: a
  fresh hash is a real `$argon2id$...` string, not a legacy hex digest.
- **Configurable CORS origin** (`VAJRA_ALLOWED_ORIGIN`) instead of a
  hardcoded `*` on every response - defaults to `*` for the demo, pin it
  to the real console URL for a real deployment. Verified: overriding it
  actually changes the header sent.
- **Baseline security headers** (`X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`) on every
  response, API and static alike. Cheap, real, but not a substitute for
  an actual security review - see below.
- **Configurable DB path** (`VAJRA_DB_PATH`) so a container can mount a
  persistent volume instead of writing inside the image layer. Verified:
  server boots and serves correctly against a path outside the repo.
- **Exchange Risk Board aggregation extracted to a pure function**
  (`engine/exchange_board.py`) so it's unit-tested independent of the
  HTTP/DB layer, instead of living inline in the route handler.
- **359 tests** (`backend/tests/`, stdlib `unittest` plus FastAPI's
  `TestClient` for real HTTP-level integration tests), covering scoring
  bounds and decision thresholds, clustering quality bounds, JWT
  issue/verify/tamper/expiry, RBAC permission table, the rate limiter,
  the login lockout, the exchange aggregation logic (including the
  "repeat offender should outrank a single high-confidence hit" property
  the scoring formula is supposed to guarantee), request correlation
  IDs, pagination, and a full maker-checker approval flow driven as real
  HTTP requests. Count is from `def test_` functions in `backend/tests/`
  as of this build - re-run `python3 -m unittest discover -s tests`
  before your demo to confirm the live pass count on your machine.
- **Structured logging + request correlation IDs** - every request gets
  a short ID, echoed back as `X-Request-ID`, included in a structured
  log line for that request.
- **A global unhandled-exception handler** - logs the full traceback
  server-side against the request's correlation ID, returns a
  deliberately generic error body to the client (never a leaked stack
  trace or exception message).
- **Pydantic request validation** on the highest-traffic and most
  security-relevant endpoints (auth, case intake, notices) - malformed
  or wrong-typed input now gets a clean `422` instead of risking an
  unhandled exception, and `/docs` actually documents the request shape.
- **Pagination** on `GET /api/cases` (`limit`/`offset`, capped and
  clamped, `total` in the response) - backward-compatible, since any
  caller that doesn't pass these params gets everything up to 200
  results exactly as before.
- **Dockerfile + docker-compose.yml** - packaging only.
  **Honesty note:** `docker compose up --build` has not been run on a
  machine with internet access yet - the files are written correctly
  against the real `requirements.txt` and entrypoint, but that build-test
  is still outstanding. Don't present this as "containerized and
  verified" - present it as "packaged, needs one build-test before the
  finale."

**What's still honestly not done, and why:** live blockchain API calls
against real Etherscan/Blockstream/TronGrid traffic, and the real
Elliptic++ dataset swap for the live per-wallet classifier - both need
outbound internet access to set up (API keys, a licensed dataset
download) and haven't been done yet. Don't claim otherwise in front of a
judge who asks.

**What's blocked on the team's action, not on more engineering time:**
- **Etherscan / TronGrid API keys** - sign-up requires a real email/identity
  and terms acceptance. Get free-tier keys, put them in `.env`, set
  `VAJRA_LIVE_MODE=1`, then actually run a trace against a real address on
  each chain before the finale. This is the single highest-value thing
  left - it's the one claim ("real-time blockchain data") that's currently
  unverified against reality.
- **Real Elliptic++ dataset** - download from Kaggle (license acceptance
  required), retrain `ml_model.py` against it instead of the synthetic
  data. Directly answers the "is this real data" judge question.
- **`docker compose up --build`** - an actual build-test, once run on a
  machine with internet, of the Dockerfile/compose files shipped here.
- **A real deployment** (cloud VM/container host, HTTPS via a real domain +
  cert, monitoring) - needs an account and budget that belong to the team.
- **A real security review / pentest** and **legal/compliance sign-off**
  for handling real victim complaint data - both need human expertise;
  the hardening done here (WAL mode, connection-leak fix, brute-force
  lockout, Argon2id hashing, security headers, input validation, 359
  tests) measurably reduces risk but is not a replacement for either.

## UI pass (inspired by, not copied from, a reference SIH project)

Looked at another team's SIH submission for inspiration per request. Didn't
copy its teal/brass palette or generic icon-grid dashboard (that's the
"SaaS starter kit" look VAJRA's ink/copper dossier aesthetic was already
avoiding) - took one genuinely useful idea (a light/dark toggle) and built
it with VAJRA's own palette family instead:

- **Dark mode toggle** - sun/moon button in the topbar, persisted in
  localStorage, applied before first paint (no flash). The sidebar, topbar
  and login screen were already fixed-dark "ink" surfaces by design; this
  only re-themes the main paper content area. Deliberately does NOT touch
  the badge/chip/pill accent colors (role-badge, approval-banner, risk
  chips, etc.) - they're self-contained light-pastel-background +
  dark-text pairs that read fine as colored tags on a dark card (the same
  pattern Linear/Notion/GitHub use), so leaving them alone was the correct
  call. The handful of *bare* colored text that WOULD lose contrast on a
  dark background (a stat number, a table-cell pill label) gets an
  explicit lighter override - verified via a full grep of every
  accent-color usage in the CSS, not spot-checked.
- **Dashboard hero signal** - a stamped-dossier-style banner tying
  straight into the Exchange Risk Board (the PS's headline feature)
  instead of burying it in the stat-card grid: leads with "N fraud-linked
  exchanges identified" and the top repeat offender, with a direct link
  into the board.

**Note:** these changes were verified structurally (every JS file
re-parses cleanly, every CSS file's braces balance, every DOM ID
referenced in JS exists in the served HTML) and visually - real
screenshots of the login screen, signup tab, and dashboard were
rendered in both dark and light themes and inspected directly, catching
and fixing a genuine invisible-text bug on the light-mode login screen
in the process. A final click-through in an actual browser before the
demo is still worthwhile, but this has had a real visual check, not
just a structural one.

## Real Elliptic dataset benchmark

The team provided the real, published Elliptic Bitcoin dataset (Kaggle
`elliptic-data-set`: 203,769 transactions, 166 anonymized features,
4,545 labelled illicit / 42,019 labelled licit). A RandomForest was
trained and evaluated directly on it in `engine/train_elliptic_benchmark.py`,
using the same temporal train/test split convention as the original
Elliptic paper (train on time steps 1-34, test on 35-49 - no
future-leakage into training). Real, reproducible results on the real
data:

| Metric | Value |
|---|---|
| AUROC | 0.9366 |
| Precision | 0.9629 |
| Recall | 0.7193 |
| F1 | 0.8235 |
| Test set | 16,670 real labelled transactions |

See `engine/elliptic_benchmark_metrics.json` and the saved model at
`engine/elliptic_benchmark_classifier.pkl`.

**Honesty note - why this is a benchmark, not a drop-in replacement
for the live model:** Elliptic's 166 features are anonymized/PCA-
transformed by the original authors (never disclosed as named,
interpretable fields) - they describe *transactions* as graph nodes.
VAJRA's live per-wallet classifier (`ml_model.py`, used by
`/api/trace`) instead uses 8 *named* engineered features
(`in_degree`, `mixer_proximity`, `peel_chain_score`, etc.) computed
live from each traced *wallet's* transaction neighbourhood. The two
feature spaces have different units and different graph granularity
(transaction-level vs wallet-level) - a model trained on one cannot
score a feature vector built for the other. So this benchmark proves
VAJRA's modelling approach holds up on real, external, published data
with real reported numbers - genuinely useful to say in front of a
judge - while the live trace path keeps its own 8-feature model,
which remains trained on synthetic-but-realistic data (see
`ml_model.py` docstring). Real in/out-degree stats were pulled from
the Elliptic edgelist to check whether they could recalibrate the
live model's synthetic generator; they were **not** used, because
Elliptic's degree counts are per-transaction (mean ~1.3 in / ~0.9 out)
while VAJRA's live feature is per-wallet across many transactions - mixing the two units would have quietly introduced a wrong-but-
plausible-looking number rather than a real improvement.

## Competitive benchmarking

After reviewing competing SIH26183 GitHub submissions for the same
problem statement, three specific gaps were identified and closed. In
short:

- **Attribution tier (CONFIRMED / PROBABLE / UNATTRIBUTED)** - `engine/scoring.py`'s `attribution_tier()`. Separate from the
  existing confidence score: a direct known-exchange-wallet address
  match is CONFIRMED even at low confidence; a high confidence built
  entirely from heuristics (deposit-fingerprint, sweep regularity, AI
  probability) is only PROBABLE. Persisted on `cases.attribution_tier`.
- **Time-lock pre-processor** - `engine/tracer.py`'s
  `apply_time_lock()`. Drops any transaction dated before the
  victim-reported incident (new optional `incident_timestamp` field at
  case intake) before clustering/scoring ever sees it - an evidentiary-
  integrity check, not a UI filter. Fails open if the timestamp is
  missing/unparseable, and logs a `time_lock` ledger event with the
  count excluded and the cutoff used.
- **Reporter role - citizen/victim intake.** `POST
  /api/auth/register-reporter`, `POST /api/public/report`, `GET
  /api/cases/unassigned`, `POST /api/cases/{id}/claim`. Until this
  pass every role in this system (officer/supervisor/admin) was
  investigator-side - there was no citizen-facing path at all, despite
  the PS being literally titled "Victim-**Reported** Suspect Wallet
  Addresses". A citizen self-registers, submits a suspect address with
  no jurisdiction required (they wouldn't know which Cyber Crime Cell
  owns it), and an officer claims it into their own jurisdiction from
  a triage queue before any trace runs.
  **Console UI status: wired.** A standalone citizen-facing screen
  (`pages/Report.jsx`, reached via "Report a suspect wallet" on the
  landing page - no officer login involved) handles registration +
  submission and returns the NCRP reference number. The officer side
  gets a new "Citizen reports" console tab (`components/ReportsQueue.jsx`)
  listing unassigned reports with a one-click claim button. Demos as a
  real clickable flow end to end now, not just an API call.
- **JWT: hand-rolled stdlib → real PyJWT**, matching the standard-
  library-where-a-standard-exists concern raised in the same review.
  Every function in `auth.py` kept its exact name/signature, so no
  caller changed.
- 14 new tests added (`tests/test_new_features.py`) covering all three
  features above. Suite total: 88 (was 80).

**Deliberately not done** - flagged as bigger, riskier refactors,
not worth the risk of breaking a working build: splitting `main.py`
into per-domain routers, and introducing a SQLAlchemy ORM layer over
the current raw-`sqlite3` schema. Both remain the two highest-value
remaining code-quality items if time allows before the final
submission.

## Syndicate Score + Freeze Window

A feature that isn't a gap-closer against a competitor - it's a genuinely new capability none of the 5 SIH26183
teams reviewed have. `engine/syndicate.py`:

- **Syndicate Score / Tier (WATCH / ESCALATE / CRITICAL)** - sits on
  top of the existing `engine/case_graph.py` cross-case network
  detection (no new graph logic; this module scores networks that
  were already being found). More linked cases + higher average
  attribution confidence = a higher score. Real-world gap this closes:
  a single small complaint reads as low-priority in isolation, but the
  same wallet cluster hitting 10+ victims is an organized operation - and nothing previously connected those dots automatically.
- **Freeze Window (hours)** - an explicitly-labeled HEURISTIC urgency
  estimate, not a prediction. Shrinks as victim count and confidence
  grow (a larger, more-confidently-attributed cluster reads as more
  actively operated, so less time is assumed to be left), floored at 2
  hours. The "why this number" reasoning is in the function's own
  docstring, written for a judge who asks exactly that.
- **Auto-escalation** - `GET /api/syndicates` writes
  `cases.syndicate_alert_tier` and one `audit_log` entry the moment a
  network crosses a *new, higher* tier than what's already stored - idempotent, so calling it repeatedly (e.g. every dashboard load)
  never double-logs the same escalation.
- Verified end-to-end: seeded two existing fixture cases
  that genuinely share a wallet cluster, confirmed the pipeline found
  the network, scored it WATCH, computed a real freeze-window number,
  wrote the escalation once, and confirmed a second identical call
  wrote nothing further (idempotency).
- 10 new tests in `tests/test_new_features.py` covering score
  ordering, tier boundaries, freeze-window monotonicity and floor, and
  pooled-value aggregation. Suite total: 98 (was 88).

## Documented next step (roadmap, not hidden as "done")

- **Real Elliptic++ training data** for the illicit-probability
  classifier, replacing the synthetic-but-schema-matched dataset. The
  Elliptic++ variant (unlike the base Elliptic set added above) adds
  actor-level, address-level, and some named features - worth
  revisiting once available, as it may close more of the schema gap
  described above.
- **Re-fit confidence-formula weights** via logistic regression once a
  larger set of investigator-confirmed outcomes exists, instead of the
  3-fixture calibration used now.
- **FastAPI + Celery + Redis + WebSockets** for horizontal scaling across
  multiple worker processes (this build is single-process; see
  `docs/ARCHITECTURE.md` for the exact swap points).
- **PostgreSQL** in place of SQLite at production scale (schema is
  already portable - no SQLite-only features used).
- **Neo4j** for the same cross-case graph query at cross-jurisdiction
  scale - thousands of concurrent cases and sub-second queries across a
  national case index. The query itself (union-find over shared
  addresses) is already real and tested at single-cyber-cell scale; see
  `backend/engine/case_graph.py`. Neo4j only earns its keep once the
  node count is large enough that an in-process union-find over a
  Python dict stops being the cheaper option - a threshold a real
  deployment would hit, a hackathon demo with a few hundred cases will
  not.
- **SQL-side exchange aggregation** - the Exchange Risk Board currently
  aggregates in Python over rows fetched from SQLite; on Postgres this
  becomes a single `GROUP BY` with `jsonb` extraction (no new
  infrastructure, same point made in the roadmap doc this build shipped
  with - just now actually built on the Python side first).
- **Redis pub/sub or a WebSocket hub** for the real-time alert broadcast
  at multi-worker scale (this build's `AlertBroadcaster` is correct and
  tested for a single process; a horizontally-scaled deployment needs a
  shared channel across workers - same upgrade path already documented
  for Live progress updates, above).
- **Direct Sahyog Portal API submission** for notices, in place of the
  simulated "sent" status transition.
- **A revocable refresh-token store** - current refresh tokens are
  stateless JWTs (real, consumed by `POST /api/auth/refresh`) but not
  individually revocable before expiry; a server-side store (Redis or a
  DB table) would allow instant revocation on logout/compromise.
  (Password hashing is already Argon2id, not PBKDF2 - see "Built" above;
  this line used to list that as outstanding too, which was stale.)

## Explicitly not built (asked for, deliberately declined rather than faked)

A later request asked for a "What-If Investigation Simulator" (freeze a
wallet, predict alternate fund routes, estimate recovery probability)
and a general-purpose "AI Investigation Copilot" chatbot. Neither is in
this build:

- **Alternate-route prediction** would require either fabricating a
  probability with no model behind it, or real adversarial-routing
  modelling that would need data and time this build doesn't have.
  Faking it would put a made-up number next to the real,
  inspectable ones everywhere else in this report - exactly the
  black-box problem the rest of this build was written to avoid.
- **A chatbot-style copilot** was scoped down to `engine/copilot.py`
  instead: real, deterministic, evidence-linked narration and next-step
  rules over data the pipeline already computed (see "Built" above) - not a free-text model call that could say something the rest of the
  console can't back up.

If real reachability analysis over the already-traced graph (e.g. "what
remains reachable if this cluster address is removed") is wanted later,
that's a legitimate, buildable extension of `engine/case_graph.py`'s
union-find - flagged here rather than shipped half-real.
