# VAJRA - Virtual Asset Judicial Response & Attribution

A fund-flow tracing and attribution console for cryptocurrency fraud
investigation, built for SIH26183 ("Development of a Real-Time
Blockchain Transaction Tracing and Wallet Address Attribution Tool for
Fraud-linked Cryptocurrency Exchanges").

## Stack

- **Backend**: FastAPI, SQLite (WAL mode), scikit-learn, JWT auth
  (Argon2id password hashing), Server-Sent Events for live trace
  progress.
- **Frontend**: React (Vite), custom design system, dark/light themes.

## Run it (development)

Two terminals:

```bash
# terminal 1 - backend
cd backend
pip install -r requirements.txt
python3 main.py                 # http://localhost:8000

# terminal 2 - frontend
cd frontend
npm install
npm run dev                     # http://localhost:5173 (proxies /api to :8000)
```

Open `http://localhost:5173`. Seeded logins (password `vajra123` for all):
- `MHA-CY-08231` - Officer - R. Kulkarni
- `MHA-CY-04410` - Supervisor - S. Pillai
- `MHA-CY-00001` - Admin - I4C Admin Desk

Copy `.env.example` to `backend/.env` for live blockchain mode
(`ETHERSCAN_API_KEY` / `TRONGRID_API_KEY`).

## Run it (production-style, one port)

```bash
cd frontend && npm install && npm run build   # writes frontend/dist/
cd ../backend && python3 main.py              # now also serves the built React app
```

## Testing

```bash
cd backend
python3 -m unittest discover -s tests
```

359 tests covering the tracing pipeline, clustering, ML classifier,
chain adapters, caching, notice generation, JWT auth/RBAC, risk-pattern
detection, and full API integration tests (real HTTP requests via
FastAPI's TestClient against an isolated database). Run the command
above before your demo/submission to confirm the current pass count
on your machine.

## Project layout

```
backend/
  main.py            FastAPI app - all routes
  db.py, auth.py      database + authentication
  engine/             tracing, clustering, scoring, ML classifier,
                       notice generation, priority queue
  tests/               359 unit + integration tests
frontend/
  src/pages/          Login, Landing, Console
  src/components/      Dashboard (React)
  src/console-core/         view logic
  src/styles/         design system (dark/light themes)
docs/                  ARCHITECTURE.md, BUILT_VS_ROADMAP.md
```
