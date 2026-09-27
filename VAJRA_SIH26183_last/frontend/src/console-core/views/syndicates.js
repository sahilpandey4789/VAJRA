import * as api from "../api.js";
import { chainLabel } from "../format.js";

/**
 * Syndicate Score + Freeze Window - surfaces GET /api/syndicates
 * (engine/syndicate.py) as its own page instead of leaving it buried
 * behind the case-network graph. Turns "these N cases share a wallet
 * cluster" into one actionable signal: a WATCH / ESCALATE / CRITICAL
 * tier, how many victims and how much pooled value are involved, and
 * an explicit, labeled-as-a-heuristic freeze-window estimate an
 * officer can act on right now.
 */

const TIER_META = {
  CRITICAL: { chip: "high", cardClass: "tier-critical", label: "Critical" },
  ESCALATE: { chip: "med", cardClass: "tier-escalate", label: "Escalate" },
  WATCH: { chip: "low", cardClass: "tier-watch", label: "Watch" },
};

function freezeUrgency(hours) {
  if (hours <= 12) return "urgent";
  if (hours <= 24) return "soon";
  return "ok";
}

export async function renderSyndicates(container, ctx) {
  const isAdmin = ctx.officer.role === "admin";
  container.innerHTML = `
    <div class="view-head">
      <div>
        <div class="view-title">Syndicate Score &amp; Freeze Window</div>
        <div class="view-sub">Cases that share a wallet cluster, ranked as one organized operation - not triaged one isolated complaint at a time.</div>
      </div>
      <div style="display:flex;gap:8px;">
        ${isAdmin ? `<button class="btn-secondary btn-sm" id="btnScopeAll">All jurisdictions</button>` : ""}
        <button class="btn-secondary btn-sm" id="btnRefreshSyndicates">Refresh</button>
      </div>
    </div>
    <div id="syndicateWrap">
      <div class="syndicate-grid">
        ${Array.from({ length: 3 }).map(() => `<div class="card"><div class="skel" style="height:14px;width:50%;margin-bottom:12px;"></div><div class="skel" style="height:60px;"></div></div>`).join("")}
      </div>
    </div>
  `;

  let scopeAll = false;
  if (isAdmin) {
    container.querySelector("#btnScopeAll").addEventListener("click", () => {
      scopeAll = !scopeAll;
      container.querySelector("#btnScopeAll").textContent = scopeAll ? "My jurisdiction only" : "All jurisdictions";
      draw();
    });
  }
  container.querySelector("#btnRefreshSyndicates").addEventListener("click", () => draw());

  async function draw() {
    const wrap = container.querySelector("#syndicateWrap");
    const { syndicates, newly_escalated_case_ids } = await api.getSyndicates(scopeAll ? "all" : undefined);

    if (newly_escalated_case_ids && newly_escalated_case_ids.length && ctx.state.view === "syndicates") {
      // purely informational - the escalation + audit log entry already
      // happened server-side; this just tells the officer it occurred.
    }

    if (!syndicates.length) {
      wrap.innerHTML = `
        <div class="empty-state">
          <div class="t">No active syndicate signals</div>
          <div class="s">Once two or more complaints trace back to the same wallet cluster, that group shows up here - scored, tiered and given a freeze-window estimate automatically.</div>
        </div>
      `;
      return;
    }

    wrap.innerHTML = `
      <div class="syndicate-grid">
        ${syndicates.map((s, i) => {
          const meta = TIER_META[s.tier] || TIER_META.WATCH;
          const urgency = freezeUrgency(s.freeze_window_hours);
          const pct = Math.max(4, Math.min(100, Math.round((s.freeze_window_hours / 48) * 100)));
          return `
            <div class="syndicate-card ${meta.cardClass} count-in" style="animation-delay:${i * 60}ms;">
              <div class="syndicate-head">
                <div>
                  <div class="syndicate-score">${s.syndicate_score}</div>
                  <div class="syndicate-score-label">Syndicate score</div>
                </div>
                <span class="chip ${meta.chip}">${meta.label}</span>
              </div>
              <div class="syndicate-metrics">
                <div class="syndicate-metric"><div class="v">${s.victim_count}</div><div class="l">Victims</div></div>
                <div class="syndicate-metric"><div class="v">${chainLabel(s.chain)}</div><div class="l">Chain</div></div>
                <div class="syndicate-metric"><div class="v">${s.pooled_value != null ? s.pooled_value.toFixed(2) : " - "}</div><div class="l">Pooled value</div></div>
              </div>
              <div class="freeze-row">
                <div class="freeze-row-head">
                  <span>Estimated freeze window</span>
                  <strong>~${s.freeze_window_hours}h</strong>
                </div>
                <div class="freeze-bar-track"><div class="freeze-bar-fill ${urgency}" style="width:${pct}%;"></div></div>
              </div>
              <div class="syndicate-cases">
                ${s.case_ids.map((cid) => `<button class="syndicate-case-chip" data-case="${cid}">${cid}</button>`).join("")}
              </div>
            </div>
          `;
        }).join("")}
      </div>
      <div class="card" style="margin-top:16px;">
        <div class="card-title">How this is scored</div>
        <div style="font-size:calc(12.5px * var(--fs-scale, 1));color:var(--text-soft);line-height:1.6;">
          <code class="mono">syndicate_score = victim_count × (1 + avg_confidence)</code> - more victims hitting the same wallet
          cluster, at higher average attribution confidence, pushes a group from <span class="chip low">Watch</span> toward
          <span class="chip med">Escalate</span> and <span class="chip high">Critical</span>. The freeze window is an explicit
          <strong style="color:var(--text);">heuristic ordering signal, not a guarantee</strong> - it starts at 48h and shrinks as the
          group grows and confidence rises, on the reasoning that an actively-operated cluster with many recent victims cashes
          out faster than an isolated wallet. Crossing into a new, higher tier auto-escalates every linked case and writes one
          audit-log entry (<code class="mono">GET /api/syndicates</code>).
        </div>
      </div>
    `;

    wrap.querySelectorAll("[data-case]").forEach((el) => {
      el.addEventListener("click", () => ctx.openCase(el.dataset.case));
    });
  }

  await draw();
  ctx.registerLiveRefresh && ctx.registerLiveRefresh("syndicates", draw);
}
