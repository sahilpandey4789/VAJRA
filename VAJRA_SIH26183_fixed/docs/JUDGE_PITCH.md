# VAJRA - judge pitch & demo script (SIH26183)

Everything below points at real, running code - nothing here is a
slide-only claim. File paths are given so a judge who asks "show me"
can actually be shown.

## 30-second framing

> "VAJRA takes a victim's crypto-fraud complaint from a raw wallet
> address to a signed legal notice - tracing funds hop-by-hop across
> Ethereum, Bitcoin and Tron, clustering wallets, scoring attribution
> confidence, detecting mixers and known exchange hot-wallets, and
> drafting the freeze/KYC-disclosure notice - with maker-checker
> approval and a full audit trail, the way an actual cyber-cell
> workflow has to work."

## What to actually click through (5-minute demo path)

1. **Sign in** as Officer (`MHA-CY-08231` / `vajra123`) - point out RBAC:
   three real roles, permission table checked server-side
   (`backend/auth.py`).
2. **Dashboard** - hero banner leads with the Exchange Risk Board
   number, not a vanity stat. Stats are computed live from SQLite, not
   hardcoded.
3. **New trace** - paste a wallet address, watch the 5-stage SSE
   pipeline run live (`collecting → tracing → clustering → checking →
   scoring`) - this is a real pipeline running, not a timed animation.
4. **Trace report** - point out: confidence breakdown (explainable, not
   a bare %), AI illicit-probability with feature-level explanation,
   cluster quality score, cross-case link graph (shared wallets across
   other open cases), risk-pattern flags (peel chains, structuring,
   mixer hits) - each with the actual transaction hashes that
   triggered it.
5. **Draft a notice** (Officer) → **switch to Supervisor** → **approve**
   → **send**. This is the moment to say out loud: *"an Officer cannot
   approve their own draft - that's enforced in the backend, not just
   hidden in the UI"* (`403` if you try).
6. **Case network view** - the cross-case graph, recomputed live, not
   frozen at trace time.
7. **Exchange risk board** - ranks exchanges by `linked_cases ×
   avg_confidence`, directly answering the PS's literal ask to
   "identify fraud-linked cryptocurrency exchanges," not just trace one
   wallet.
8. *(If time)* **Reassign a case** as Supervisor - real RBAC-gated
   workflow action, not just a read view.

## Differentiators to say out loud

- **Explainability over black-box score** - every number in the report
  traces back to a real, inspectable field (`backend/engine/scoring.py`,
  `copilot.py`). No "trust the AI" moment in the whole demo.
- **Maker-checker is server-enforced**, not a UI convention - try to
  break it live if a judge asks; it holds.
- **Cross-case graph is a real graph query** (union-find over shared
  addresses), not a fixture - trace two wallets that share an
  intermediate address and watch the link appear.
- **Offline-first**: kill the backend mid-demo, the console degrades to
  a clearly labelled OFFLINE DEMO instead of crashing.

## If a judge asks "is the AI real"

Yes and be specific about *which* AI: a real `RandomForestClassifier`
runs at inference time for every trace (`ml_model.py`), trained on
synthetic-but-schema-matched data since the real Elliptic++ dataset
requires a separate licensed download. Separately, the real *published*
Elliptic dataset (203k transactions) was benchmarked end-to-end as
a credibility check - AUROC 0.937, F1 0.82 on 16,670 real held-out
transactions (`docs/BUILT_VS_ROADMAP.md`, "Real Elliptic dataset
benchmark"). Say both halves - it's a stronger answer than claiming
either one alone.

## If a judge asks "what's not built yet" - answer directly, don't dodge

- Real Elliptic++ training data for the live per-wallet classifier
  (roadmap, not hidden)
- Single-process today - Celery/Redis/WebSockets is the documented
  scale-out path
- SQLite today - schema is Postgres-portable, no SQLite-only features
- Refresh tokens aren't revocable before natural expiry (no server-side
  token store yet) - a stolen refresh token stays valid until it expires
- Direct Sahyog Portal API submission - currently a simulated "sent"
  status transition

Naming these unprompted, precisely, and moving on is a stronger look
than getting caught by a probing question. See
`docs/BUILT_VS_ROADMAP.md` for the complete, honest built-vs-roadmap
breakdown.

## One line if asked "why not build the What-If Simulator / chatbot copilot"

> "We scoped it down on purpose - an alternate-fund-route predictor
> with no real adversarial-routing model behind it would be a
> made-up number next to every real, inspectable number in this
> report. We built `engine/copilot.py` instead: real narration over
> data the pipeline already computed, not a free-text model that could
> say something the rest of the console can't back up." (See
> `docs/BUILT_VS_ROADMAP.md`, "Explicitly not built.")
