import * as api from "../api.js";

const ROWS = [
  { area: "Clustering heuristics (co-spend, change-address, deposit-fingerprint)", built: "Implemented exactly as specified, real computation over traced transactions", roadmap: "Re-weight thresholds against a larger labelled case set" },
  { area: "Attribution confidence formula", built: "Real weighted sigmoid, fitted against the 3 known-outcome fixtures", roadmap: "Re-fit weights via logistic regression on investigator-confirmed outcomes" },
  { area: "AI illicit-probability classifier", built: "Real RandomForestClassifier, trained + serialized + loaded at inference time", roadmap: "Swap synthetic training data for the real Elliptic++ dataset" },
  { area: "Chain data", built: "Real Etherscan/Blockscout, Blockstream/mempool.space, TronGrid/TronScan adapters with retry + failover, gated behind VAJRA_LIVE_MODE - falls back to offline fixtures automatically", roadmap: "Run a live trace against real API keys before relying on this in production" },
  { area: "AI explainability", built: "Ranked feature-contribution reasons per trace (SHAP-style local approximation from the classifier's own feature importances)", roadmap: "Swap in exact Shapley values via the real `shap` package" },
  { area: "Evidence reports", built: "Real PDF generation (reportlab): hop diagram, confidence breakdown, AI reasons, SHA-256 hash, QR verification", roadmap: "Real DSC/eSign digital signature (currently a labelled placeholder box)" },
  { area: "Auto-drafted legal notices", built: "Real template engine, outcome-aware (freeze vs KYC-disclosure), CrPC/BNSS-cited", roadmap: "Direct Sahyog Portal API submission (currently simulated send)" },
  { area: "Maker-checker workflow", built: "Enforced server-side - officer drafts, Supervisor+ approves, RBAC-checked", roadmap: "Configurable approval chains per jurisdiction" },
  { area: "Auth & RBAC", built: "Real JWT (HMAC-SHA256), 3 roles, permission checks on every route, working refresh-token exchange", roadmap: "Move to Argon2id password hashing + a revocable refresh-token store" },
  { area: "Live progress updates", built: "Server-Sent Events streaming real per-stage pipeline progress", roadmap: "WebSocket + Redis pub/sub for multi-worker horizontal scaling" },
  { area: "Caching", built: "Redis-compatible cache layer for live API responses - real Redis if configured, in-memory TTL otherwise", roadmap: "Deploy a real shared Redis instance for multi-worker deployments" },
  { area: "Case/audit storage", built: "Real SQLite database, relational schema, foreign keys, searchable audit trail, real dashboard stats", roadmap: "PostgreSQL + read replicas at production scale" },
  { area: "Cross-case link detection", built: "Fixture-based demonstration of same-cluster linkage across cases", roadmap: "Neo4j graph store for real-time cross-case graph queries at scale" },
  { area: "Exchange Risk Board (PS's headline ask)", built: "Real aggregation of every trace's exchange_match into a ranked, scored list - GET /api/exchanges/risk-board, jurisdiction-filtered", roadmap: "SQL-side GROUP BY/json_extract once on Postgres, instead of Python-side aggregation over SQLite rows" },
  { area: "Real-time alert broadcast", built: "Global SSE fan-out (GET /api/alerts/stream) - any officer's completed trace pushes live to every connected officer's console instantly, not just their own session", roadmap: "Redis pub/sub or WebSocket hub for multi-worker horizontal scaling (same upgrade path as Live progress updates, above)" },
  { area: "Production hardening", built: "SQLite WAL mode (load-tested: 80 concurrent requests, 0 failures), connection-leak fix in the trace SSE endpoint, JWT-secret enforcement in VAJRA_ENV=production, login brute-force lockout, Argon2id password hashing, structured request logging with correlation IDs, a global exception handler, Pydantic request validation, pagination on case listings, and 359 passing tests", roadmap: "Docker packaging is written but should be build-tested on a machine with internet access; live blockchain APIs and the real Elliptic++ dataset should be verified against real traffic before production use" },
];

export async function renderAbout(container, ctx) {
  const mode = api.getMode();
  const status = mode === "live" ? await api.getSystemStatus() : null;
  const benchmark = mode === "live" ? await api.getModelBenchmark().catch(() => null) : null;
  container.innerHTML = `
    <div class="view-head"><div><div class="view-title">About this build</div><div class="view-sub">What's real vs. what's the documented next step - stated up front, not discovered under questioning.</div></div></div>
    <p class="about-lede">
      VAJRA is running in <strong>${mode === "live" ? "live mode" : "cached / offline-first mode"}</strong> right now.
      ${mode === "live"
        ? `The Python backend is up: every trace you run executes the real clustering, scoring and classifier code${status && status.live_mode ? ", pulling live blockchain data with automatic failover to offline fixtures" : " against the seeded offline transaction fixtures (set VAJRA_LIVE_MODE=1 to pull live data)"}.`
        : "The backend isn't reachable from this page, so the console is serving the exact same computed output from a bundled snapshot - start it with <code>python3 backend/main.py</code> for the live pipeline."}
      Nothing below is a placeholder pretending to be finished; it's an honest map of the two.
    </p>
    ${status ? `
    <div class="card" style="margin-bottom:var(--sp-5);">
      <div class="card-title">Live system status</div>
      <div style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-soft);margin-bottom:8px;">
        Cache backend: <strong>${status.cache_backend}</strong> &middot; Live mode: <strong>${status.live_mode ? "on" : "off"}</strong>
      </div>
      ${status.providers.length ? `
        <table class="split-table">
          <thead><tr><th>Chain</th><th>Provider</th><th>Status</th></tr></thead>
          <tbody>${status.providers.map((p) => `<tr><td>${p.chain}</td><td class="mono">${p.provider}</td><td>${p.status}</td></tr>`).join("")}</tbody>
        </table>` : ""}
    </div>` : ""}
    ${benchmark && benchmark.elliptic_benchmark ? `
    <div class="card" style="margin-bottom:var(--sp-5);">
      <div class="card-title">Model performance</div>
      <div style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-soft);margin-bottom:14px;line-height:1.6;">
        Two different numbers, shown side by side on purpose: the <strong style="color:var(--text);">live model</strong> is
        what's actually running inference right now, self-measured on its own synthetic training set - treat its near-perfect
        score as an optimistic-bias warning sign, not a boast. The <strong style="color:var(--text);">Elliptic benchmark</strong> is
        a one-time offline run of the identical architecture against the real, published Elliptic Bitcoin dataset
        (${benchmark.elliptic_benchmark.n_labeled.toLocaleString("en-IN")} real labelled transactions, paper-standard temporal
        train/test split) - this is the credible number.
      </div>
      <div class="model-metric-grid">
        ${["auroc", "precision", "recall", "f1"].map((k) => {
          const live = benchmark.live_model && benchmark.live_model[k] != null ? benchmark.live_model[k] : null;
          const real = benchmark.elliptic_benchmark[k] != null ? benchmark.elliptic_benchmark[k] : null;
          return `
            <div class="model-metric-row">
              <div class="model-metric-label">${k.toUpperCase()}</div>
              <div class="model-metric-bars">
                ${live != null ? `
                <div class="model-metric-bar-line">
                  <span class="model-metric-tag live">live</span>
                  <div class="factor-bar-track"><div class="factor-bar-fill live" style="width:${Math.round(live * 100)}%;"></div></div>
                  <span class="model-metric-val">${live.toFixed(3)}</span>
                </div>` : ""}
                <div class="model-metric-bar-line">
                  <span class="model-metric-tag real">real</span>
                  <div class="factor-bar-track"><div class="factor-bar-fill" style="width:${Math.round(real * 100)}%;"></div></div>
                  <span class="model-metric-val">${real.toFixed(4)}</span>
                </div>
              </div>
            </div>
          `;
        }).join("")}
      </div>
      <div style="font-size:calc(11px * var(--fs-scale, 1));color:var(--text-faint);margin-top:10px;">
        Real benchmark confusion matrix - TP ${benchmark.elliptic_benchmark.confusion_matrix.tp},
        FP ${benchmark.elliptic_benchmark.confusion_matrix.fp}, FN ${benchmark.elliptic_benchmark.confusion_matrix.fn},
        TN ${benchmark.elliptic_benchmark.confusion_matrix.tn} &middot;
        ${benchmark.elliptic_benchmark.n_features} features &middot; ${benchmark.elliptic_benchmark.split_method}
      </div>
    </div>` : ""}
    <div class="table-wrap">
      <table class="split-table">
        <thead><tr><th style="width:26%">Area</th><th>Built &amp; running now</th><th>Documented next step</th></tr></thead>
        <tbody>
          ${ROWS.map((r) => `
            <tr>
              <td><strong style="font-size:calc(12.5px * var(--fs-scale, 1));">${r.area}</strong></td>
              <td><span class="built-pill">BUILT</span><br/><span style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-soft);">${r.built}</span></td>
              <td><span class="roadmap-pill">ROADMAP</span><br/><span style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-soft);">${r.roadmap}</span></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}
