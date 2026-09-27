import * as api from "../api.js";
import { riskChip, statusLabel, relativeTime, chainLabel, shortAddr } from "../format.js";

// Animates a numeric stat/hero value counting up from 0 on first render - // purely presentational, reads the number already rendered in the DOM and
// tweens the text content; never touches the underlying data.
function animateNumber(el, { duration = 900 } = {}) {
  if (!el || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
  const raw = el.textContent;
  const match = raw.match(/^-?\d[\d,]*(\.\d+)?/);
  if (!match) return;
  const numStr = match[0].replace(/,/g, "");
  const target = parseFloat(numStr);
  if (!isFinite(target)) return;
  const decimals = match[1] ? match[1].length - 1 : 0;
  const suffix = raw.slice(match[0].length);
  const start = performance.now();
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  function frame(now) {
    const p = Math.min(1, (now - start) / duration);
    const val = target * ease(p);
    el.textContent = (decimals ? val.toFixed(decimals) : Math.round(val).toLocaleString("en-IN")) + suffix;
    if (p < 1) requestAnimationFrame(frame);
    else el.textContent = raw;
  }
  requestAnimationFrame(frame);
}

export async function renderDashboard(container, ctx) {
  container.innerHTML = `
    <div class="view-head">
      <div>
        <div class="view-title">Case overview</div>
        <div class="view-sub">${ctx.officer.jurisdiction} &middot; ${new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}</div>
      </div>
      <button class="btn-primary" id="btnNewTrace">+ New trace</button>
    </div>
    <div class="hero-signal" id="heroSignal">
      <div class="skel" style="height:64px;width:100%;"></div>
    </div>
    <div class="stat-row" id="statRow">
      ${Array.from({ length: 9 }).map(() => `<div class="stat-card"><div class="skel" style="height:11px;width:60%;margin-bottom:10px;"></div><div class="skel" style="height:26px;width:40%;"></div></div>`).join("")}
    </div>
    <div class="dash-grid">
      <div>
        <div class="card-title" style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <span>Recent complaints</span>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <input type="text" id="caseSearch" placeholder="Search NCRP ref or wallet…" style="min-width:140px;flex:1;" />
            <select id="riskFilter">
              <option value="">All risk</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
        </div>
        <div class="table-wrap responsive-table">
          <table class="case-table">
            <thead><tr><th>Case ID</th><th>Suspect wallet</th><th>Chain</th><th>Reported</th><th>Risk</th><th>Status</th></tr></thead>
            <tbody id="caseTbody"><tr><td colspan="6"><div class="skel" style="height:16px;"></div></td></tr></tbody>
          </table>
        </div>
        <div class="case-cards" id="caseCards"></div>
      </div>
      <div class="card" id="alertsCard">
        <div class="card-title">Recent alerts</div>
        <div id="alertsList"><div class="skel" style="height:16px;margin-bottom:8px;"></div></div>
      </div>
    </div>
  `;

  container.querySelector("#btnNewTrace").addEventListener("click", () => ctx.navigate("trace"));

  const [stats, cases, exchanges] = await Promise.all([api.getStats(), api.listCases(), api.getExchangeRiskBoard()]);
  ctx.setCases(cases);

  const topExchange = exchanges[0];
  container.querySelector("#heroSignal").innerHTML = topExchange
    ? `
      <div class="hero-signal-main">
        <div class="hero-signal-label">Fraud-linked exchanges identified in your jurisdiction</div>
        <div class="hero-signal-value">${exchanges.length}</div>
        <div class="hero-signal-sub">Top repeat offender: <strong>${topExchange.exchange}</strong> - linked to ${topExchange.linked_cases} complaint${topExchange.linked_cases === 1 ? "" : "s"}, ${Math.round(topExchange.avg_confidence * 100)}% avg. confidence</div>
      </div>
      <button class="btn-secondary" id="btnHeroRiskBoard">View exchange risk board →</button>
    `
    : `
      <div class="hero-signal-main">
        <div class="hero-signal-label">Exchange risk board</div>
        <div class="hero-signal-value" style="font-size:var(--fs-lg);">No exchange matches yet</div>
        <div class="hero-signal-sub">Every trace whose fund flow reaches a known exchange wallet will appear here, ranked across all complaints.</div>
      </div>
      <button class="btn-secondary" id="btnHeroRiskBoard">Open board →</button>
    `;
  container.querySelector("#btnHeroRiskBoard").addEventListener("click", () => ctx.navigate("exchanges"));
  animateNumber(container.querySelector(".hero-signal-value"));

  const chainDist = stats.blockchain_distribution || {};
  const chainDistLabel = Object.entries(chainDist).map(([k, v]) => `${chainLabel(k)} ${v}`).join(" · ") || " - ";

  container.querySelector("#statRow").innerHTML = `
    <div class="stat-card"><div class="stat-label">Active cases</div><div class="stat-value">${stats.open_cases}</div><div class="stat-delta">across ${ctx.officer.jurisdiction.split(" - ")[1]?.trim() || "jurisdiction"}</div></div>
    <div class="stat-card"><div class="stat-label">Funds traced</div><div class="stat-value">${Number(stats.funds_traced || 0).toFixed(2)}</div><div class="stat-delta">native units, all chains</div></div>
    <div class="stat-card"><div class="stat-label">High-risk cases</div><div class="stat-value copper">${stats.high_risk_flags}</div><div class="stat-delta warn">needs review</div></div>
    <div class="stat-card"><div class="stat-label">Pending approvals</div><div class="stat-value">${stats.pending_approvals ?? 0}</div><div class="stat-delta">maker-checker queue</div></div>
    <div class="stat-card"><div class="stat-label">Exchange requests</div><div class="stat-value">${stats.exchange_requests ?? 0}</div><div class="stat-delta">KYC-disclosure notices</div></div>
    <div class="stat-card"><div class="stat-label">Avg. trace time</div><div class="stat-value">${stats.avg_trace_minutes} min</div><div class="stat-delta">was ${stats.manual_baseline_hours} hrs manual</div></div>
    <div class="stat-card"><div class="stat-label">Blockchain distribution</div><div class="stat-value" style="font-size:var(--fs-md);">${chainDistLabel}</div><div class="stat-delta">cases by chain</div></div>
    <div class="stat-card"><div class="stat-label">Today's activity</div><div class="stat-value">${stats.today_activity ?? 0}</div><div class="stat-delta">audit-logged actions</div></div>
    <div class="stat-card"><div class="stat-label">Notices issued</div><div class="stat-value">${stats.notices_issued_month}</div><div class="stat-delta">this month</div></div>
  `;
  container.querySelectorAll("#statRow .stat-card").forEach((card, i) => {
    card.classList.add("count-in");
    card.style.animationDelay = `${i * 45}ms`;
    animateNumber(card.querySelector(".stat-value"));
  });

  const alerts = stats.recent_alerts || [];
  container.querySelector("#alertsList").innerHTML = alerts.length
    ? alerts.map((a) => `
        <div class="alert-row" data-case="${a.id}">
          <span class="alert-dot"></span>
          <div>
            <div class="alert-title mono">${a.ncrp_ref}</div>
            <div class="alert-sub">${chainLabel(a.chain)} · ${a.confidence != null ? Math.round(a.confidence * 100) + "% confidence" : " - "} · ${relativeTime(a.updated_at)}</div>
          </div>
        </div>
      `).join("")
    : `<div style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-faint);">No high-risk alerts right now.</div>`;
  container.querySelectorAll("#alertsList [data-case]").forEach((el) => {
    el.addEventListener("click", () => ctx.openCase(el.dataset.case));
  });

  if (!cases.length) {
    container.querySelector("#caseTbody").innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-faint);padding:32px;">No cases in queue.</td></tr>`;
    return;
  }

  function renderCaseRows(list) {
    const tbody = container.querySelector("#caseTbody");
    const cardsWrap = container.querySelector("#caseCards");
    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-faint);padding:32px;">No cases match your search.</td></tr>`;
      cardsWrap.innerHTML = "";
      return;
    }
    tbody.innerHTML = list.map((c) => `
      <tr class="row-clickable" data-case="${c.id}">
        <td class="mono">${c.ncrp_ref}</td>
        <td class="case-wallet">${shortAddr(c.suspect_wallet)}</td>
        <td>${chainLabel(c.chain)}</td>
        <td>${relativeTime(c.reported_at)}</td>
        <td>${riskChip(c.risk_band, c.confidence)}</td>
        <td class="status-pill">${statusLabel(c.status)}</td>
      </tr>
    `).join("");

    cardsWrap.innerHTML = list.map((c) => `
      <div class="case-card" data-case="${c.id}">
        <div class="case-card-top"><span class="case-card-id mono">${c.ncrp_ref}</span>${riskChip(c.risk_band, c.confidence)}</div>
        <div class="case-card-wallet">${shortAddr(c.suspect_wallet)} &middot; ${chainLabel(c.chain)}</div>
        <div class="case-card-bottom"><span class="status-pill">${statusLabel(c.status)}</span><span style="font-size:calc(11px * var(--fs-scale, 1));color:var(--text-faint)">${relativeTime(c.reported_at)}</span></div>
      </div>
    `).join("");

    container.querySelectorAll("[data-case]").forEach((el) => {
      el.addEventListener("click", () => ctx.openCase(el.dataset.case));
    });
  }

  function applyFilters() {
    const q = (container.querySelector("#caseSearch").value || "").trim().toLowerCase();
    const riskWanted = container.querySelector("#riskFilter").value;
    const filtered = cases.filter((c) => {
      const matchesQuery = !q || c.ncrp_ref.toLowerCase().includes(q) || c.suspect_wallet.toLowerCase().includes(q);
      const matchesRisk = !riskWanted || c.risk_band === riskWanted;
      return matchesQuery && matchesRisk;
    });
    renderCaseRows(filtered);
  }

  container.querySelector("#caseSearch").addEventListener("input", applyFilters);
  container.querySelector("#riskFilter").addEventListener("change", applyFilters);

  renderCaseRows(cases);
}
