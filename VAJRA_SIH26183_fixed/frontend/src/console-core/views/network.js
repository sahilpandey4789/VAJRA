import * as api from "../api.js";
import { chainLabel } from "../format.js";

/**
 * Case Network - the roadmap's "Neo4j for real-time cross-case graph
 * queries" item, actually built. At the scale one cyber cell's case list
 * runs at (not millions of nodes), the query Neo4j would answer - * "which other cases does this one connect to via a shared laundering
 * address, directly or transitively?" - is a union-find over each case's
 * traced address set. That's engine/case_graph.py; this view renders its
 * output as a real node-link graph, not a static illustration.
 *
 * Known exchange/mixer addresses are excluded from the link computation
 * server-side (case_graph.py), so an edge here always means a genuine
 * shared *laundering-path* wallet - never "both cases happened to end at
 * WazirX", which would be true of thousands of unrelated legitimate
 * deposits and is deliberately not treated as evidence.
 */
export async function renderNetwork(container, ctx) {
  container.innerHTML = `
    <div class="view-head">
      <div>
        <div class="view-title">Case network</div>
        <div class="view-sub">Cases linked by a shared laundering-path wallet - direct or transitive - recomputed live, not frozen at trace time.</div>
      </div>
      <button class="btn-secondary btn-sm" id="btnRefreshNetwork">Refresh</button>
    </div>
    <div id="networkWrap"><div class="skel" style="height:320px;border-radius:8px;"></div></div>
  `;

  container.querySelector("#btnRefreshNetwork").addEventListener("click", () => draw());

  async function draw() {
    const wrap = container.querySelector("#networkWrap");
    wrap.innerHTML = `<div class="skel" style="height:320px;border-radius:8px;"></div>`;
    const graph = await api.getCaseNetworkGraph();

    if (!graph.nodes.length) {
      wrap.innerHTML = `
        <div class="empty-state">
          <div class="t">No connected cases yet</div>
          <div class="s">Once two cases' traced fund flows share an intermediate wallet or cluster address - not just the same exchange - they'll appear here as a connected network, updated in real time as new traces complete.</div>
        </div>
      `;
      return;
    }

    wrap.innerHTML = `
      <div class="card" style="padding:20px;">
        <div id="networkSvgHost"></div>
      </div>
      <div class="card" style="margin-top:16px;">
        <div class="card-title">${graph.network_count} investigation network${graph.network_count === 1 ? "" : "s"} · ${graph.nodes.length} case${graph.nodes.length === 1 ? "" : "s"} connected</div>
        <div class="table-wrap responsive-table" style="margin-top:8px;">
          <table class="case-table">
            <thead><tr><th>Case A</th><th>Case B</th><th>Shared address(es)</th></tr></thead>
            <tbody>
              ${graph.edges.map((e) => {
                const a = graph.nodes.find((n) => n.case_id === e.source);
                const b = graph.nodes.find((n) => n.case_id === e.target);
                return `
                  <tr>
                    <td style="font-weight:600;">${a ? a.ncrp_ref : e.source}</td>
                    <td style="font-weight:600;">${b ? b.ncrp_ref : e.target}</td>
                    <td class="mono" style="font-size:calc(11.5px * var(--fs-scale, 1));">${e.shared_addresses.map((x) => `<div>${x}</div>`).join("")}</td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        </div>
        <div style="font-size:calc(12.5px * var(--fs-scale, 1));color:var(--text-soft);line-height:1.6;margin-top:12px;">
          Known exchange hot wallets and known mixer contracts are excluded from this link check server-side
          (<code class="mono">engine/case_graph.py</code>) - two cases both ending at the same exchange is not evidence
          of a shared network on its own; a shared <em>intermediate</em> wallet is. Recomputed on every request
          (<code class="mono">GET /api/cases/network</code>), so a case traced after this page loads can retroactively
          join a network without anything here going stale.
        </div>
      </div>
    `;

    renderGraphSvg(container.querySelector("#networkSvgHost"), graph, ctx);
  }

  await draw();
  ctx.registerLiveRefresh && ctx.registerLiveRefresh("network", draw);
}

function riskColor(confidence) {
  const c = confidence ?? 0;
  if (c >= 0.75) return { fill: "var(--graph-mixer-fill)", stroke: "var(--graph-mixer-stroke)" };
  if (c >= 0.4) return { fill: "var(--graph-unresolved-fill)", stroke: "var(--graph-unresolved-stroke)" };
  return { fill: "var(--graph-exchange-fill)", stroke: "var(--graph-exchange-stroke)" };
}

/**
 * Simple circular layout - deliberately not a force simulation. This
 * console has no build step and no bundled graphics library (see
 * README's "no npm install" design constraint), and a case list at one
 * cyber cell's scale is a handful of nodes at a time, not thousands - * a circle is legible and reads instantly, which a force-directed
 * layout at this node count would not obviously improve on.
 */
function renderGraphSvg(host, graph, ctx) {
  const W = 640, H = 360, cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 70;
  const n = graph.nodes.length;
  const pos = {};
  graph.nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    pos[node.case_id] = { x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle) };
  });

  const edgesSvg = graph.edges.map((e, i) => {
    const a = pos[e.source], b = pos[e.target];
    if (!a || !b) return "";
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    const len = Math.hypot(b.x - a.x, b.y - a.y);
    const delay = (n * 0.06 + i * 0.05).toFixed(2);
    return `
      <g class="net-edge" data-a="${e.source}" data-b="${e.target}" style="animation-delay:${delay}s;">
        <line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="var(--copper-deep)" stroke-width="${1 + e.shared_count}"
              stroke-dasharray="${len}" stroke-dashoffset="${len}" style="animation-delay:${delay}s;" />
        <circle cx="${mx}" cy="${my}" r="9" fill="var(--paper)" stroke="var(--copper-deep)" stroke-width="1" />
        <text x="${mx}" y="${my + 3.5}" text-anchor="middle" font-size="9" font-family="var(--font-mono, monospace)" fill="var(--copper-deep)">${e.shared_count}</text>
      </g>
    `;
  }).join("");

  const nodesSvg = graph.nodes.map((node, i) => {
    const p = pos[node.case_id];
    const col = riskColor(node.confidence);
    const label = node.ncrp_ref.replace("NCRP-2026-", "#");
    const isHot = (node.confidence ?? 0) >= 0.75;
    const halo = isHot
      ? `<circle class="graph-node-halo" cx="${p.x}" cy="${p.y}" r="31" fill="none" stroke="${col.stroke}" stroke-width="2"/>`
      : "";
    return `
      <g class="net-node${isHot ? " graph-node-hot" : ""}" data-case-id="${node.case_id}" style="cursor:pointer;animation-delay:${(i * 0.06).toFixed(2)}s;">
        ${halo}
        <circle cx="${p.x}" cy="${p.y}" r="26" fill="${col.fill}" stroke="${col.stroke}" stroke-width="1.6" />
        <text x="${p.x}" y="${p.y - 2}" text-anchor="middle" font-size="11" font-weight="600" fill="var(--ink)">${label}</text>
        <text x="${p.x}" y="${p.y + 12}" text-anchor="middle" font-size="9" fill="var(--text-soft)">${chainLabel(node.chain)}</text>
      </g>
    `;
  }).join("");

  host.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;max-height:400px;" role="img" aria-label="Cross-case investigation network">
      ${edgesSvg}
      ${nodesSvg}
    </svg>
    <div style="font-size:calc(11px * var(--fs-scale, 1));color:var(--text-soft);margin-top:6px;">
      Line thickness = number of shared addresses between the two cases. Node fill = that case's own risk band. Click a case to open its trace.
    </div>
  `;

  // Hover: lift the node, highlight its own edges + the cases they connect
  // to, dim everything else - makes the graph feel explorable instead of
  // a flat printed diagram.
  const allNodeEls = Array.from(host.querySelectorAll(".net-node"));
  const allEdgeEls = Array.from(host.querySelectorAll(".net-edge"));
  allNodeEls.forEach((g) => {
    const id = g.getAttribute("data-case-id");
    const connected = new Set([id]);
    graph.edges.forEach((e) => {
      if (e.source === id) connected.add(e.target);
      if (e.target === id) connected.add(e.source);
    });
    g.addEventListener("mouseenter", () => {
      allNodeEls.forEach((o) => o.classList.toggle("net-dim", !connected.has(o.getAttribute("data-case-id"))));
      allEdgeEls.forEach((e) => {
        const lit = e.dataset.a === id || e.dataset.b === id;
        e.classList.toggle("net-lit", lit);
        e.classList.toggle("net-dim", !lit);
      });
    });
    g.addEventListener("mouseleave", () => {
      allNodeEls.forEach((o) => o.classList.remove("net-dim"));
      allEdgeEls.forEach((e) => e.classList.remove("net-lit", "net-dim"));
    });
  });

  host.querySelectorAll(".net-node").forEach((g) => {
    g.addEventListener("click", () => {
      const caseId = g.getAttribute("data-case-id");
      if (ctx && ctx.openCase) ctx.openCase(caseId);
    });
  });
}
