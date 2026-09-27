# VAJRA frontend - React (Vite)

Dashboard, wallet trace with live SSE progress + interactive fund-flow
graph, notices with maker-checker approval, exchange risk board, case
network graph, evidence vault, audit log, about page.

## Architecture

The Dashboard is a real React component (`src/components/Dashboard.jsx`)
using standard hooks (`useState`/`useEffect`). The remaining views
(`trace`, `notices`, `network`, `vault`, `audit`, `exchanges`, `about`,
the notice modal, the fund-flow graph renderer, toast notifications)
live in `src/console-core/` as focused imperative-DOM view functions, each
mounted into a plain `<div>` via a React ref. This keeps the trace
pipeline and graph-rendering logic - the most complex and highest-risk
part of the app - in a simple, well-tested shape while the outer shell
(login, landing page, topbar/sidebar/routing, and the Dashboard) is
proper React.

`src/console-core/api.js` is the API client shared by every view. Notable
details:
- **Auth**: the access token is kept in memory only (not
  `sessionStorage`) - a page reload can't leak it from storage. Only
  the refresh token persists (`sessionStorage`, cleared when the tab
  closes), and it's used to silently restore a session on reload. A
  timer proactively refreshes the access token ~60s before expiry, so a
  long-open console session won't hit a 401 mid-use.
- Error responses follow FastAPI's `{"detail": "..."}` shape.

## Run it

```bash
cd frontend
npm install
npm run dev        # dev server on :5173, proxies /api to :8000
```

Make sure the FastAPI backend is running first (`cd ../backend &&
python3 main.py`) so the proxy has something to talk to.

## Build for production

```bash
npm run build       # outputs to frontend/dist/
```

`backend/main.py` serves `frontend/dist/` automatically if it exists - so after building, running the backend alone serves the whole app on
one port.
