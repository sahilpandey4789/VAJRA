import * as api from "../api.js";
import { relativeTime, chainLabel } from "../format.js";

/**
 * Exchange Risk Board - VAJRA's answer to the PS title read literally:
 * "Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges…"
 * Every other view traces one wallet at a time; this aggregates every
 * completed trace's exchange_match into a ranked list of exchanges that
 * keep reappearing across victim complaints, backed by GET
 * /api/exchanges/risk-board (see server.py) and live-refreshed in place
 * whenever a matching real-time alert arrives over /api/alerts/stream
 * while this view is open.
 */
export async function renderExchanges(container, ctx) {
  container.innerHTML = `
    <div class="view-head">
      <div>
        <div class="view-title">Exchange risk board</div>
        <div class="view-sub">Every complaint aggregated in real time - the actual criminal infrastructure, not just individual wallets.</div>
      </div>
      <button class="btn-secondary btn-sm" id="btnRefreshExchanges">Refresh</button>
    </div>
    <div id="exchangeBoardWrap"><div class="skel" style="height:120px;border-radius:8px;"></div></div>
  `;

  container.querySelector("#btnRefreshExchanges").addEventListener("click", () => draw());

  async function draw() {
    const wrap = container.querySelector("#exchangeBoardWrap");
    wrap.innerHTML = `<div class="skel" style="height:120px;border-radius:8px;"></div>`;
    const exchanges = await api.getExchangeRiskBoard();

    if (!exchanges.length) {
      wrap.innerHTML = `
        <div class="empty-state">
          <div class="t">No exchange matches yet</div>
          <div class="s">Run a trace whose fund flow terminates at a known exchange hot wallet - it'll show up here, ranked against every other complaint that touched the same exchange.</div>
        </div>
      `;
      return;
    }

    wrap.innerHTML = `
      <div class="table-wrap responsive-table">
        <table class="case-table">
          <thead>
            <tr>
              <th>Exchange</th>
              <th>Fraud-link score</th>
              <th>Linked cases</th>
              <th>Chains</th>
              <th>Avg. confidence</th>
              <th>Last seen</th>
            </tr>
          </thead>
          <tbody>
            ${exchanges.map((e) => `
              <tr>
                <td style="font-weight:600;">${e.exchange}</td>
                <td>
                  <div style="display:flex;align-items:center;gap:8px;min-width:120px;">
                    <div style="flex:1;height:6px;border-radius:3px;background:var(--line-soft);overflow:hidden;">
                      <div style="height:100%;width:${Math.round((e.fraud_link_score_normalized ?? 0) * 100)}%;background:var(--copper-deep);"></div>
                    </div>
                    <span class="mono" style="font-size:calc(11px * var(--fs-scale, 1));color:var(--text-soft);">${e.fraud_link_score.toFixed(2)}</span>
                  </div>
                </td>
                <td>${e.linked_cases}</td>
                <td>${(e.chains || []).map((c) => `<span class="chain-badge">${chainLabel(c)}</span>`).join(" ")}</td>
                <td>${Math.round((e.avg_confidence || 0) * 100)}%</td>
                <td>${relativeTime(e.last_seen)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      <div class="card" style="margin-top:16px;">
        <div class="card-title">Scoring formula</div>
        <div style="font-size:calc(12.5px * var(--fs-scale, 1));color:var(--text-soft);line-height:1.6;">
          <code class="mono">fraud_link_score = linked_cases × avg_confidence</code> - an exchange that keeps reappearing across many
          high-confidence victim complaints ranks above one that appears once, even at high confidence. Normalized 0–1 against the
          current maximum for the progress bar above. Computed live from every trace's <code class="mono">exchange_match</code> field
          (<code class="mono">GET /api/exchanges/risk-board</code>) - no separate infrastructure, same trace data every case already produces.
        </div>
      </div>
    `;
  }

  await draw();
  ctx.registerLiveRefresh && ctx.registerLiveRefresh("exchanges", draw);
}
