// Renders the fund-flow diagram from the real traced transaction list
// (report.transactions), not a fixed static drawing - so the shape of
// the graph always matches what was actually traced for this wallet.
// This module also owns the graph's interactivity: click-to-inspect
// popups, zoom, hop-by-hop timeline playback and a wallet search/filter
// - all driven off the same model built for the static SVG, cached by
// report hash so the interaction layer never has to re-derive it.

// Colors below are CSS custom properties (tokens.css), not literal hex - // this SVG is inserted inline into the live DOM (not a standalone .svg
// file), so fill="var(--x)" resolves against the page's own theme and
// genuinely flips with the dark/light toggle. This used to be hard-coded
// hex, which is exactly why the graph never responded to the theme
// toggle at all - the single most visible bug on the Trace screen.
const COLORS = {
  suspect: { fill: "var(--graph-suspect-fill)", stroke: "var(--graph-suspect-stroke)" },
  intermediate: { fill: "var(--graph-node-fill)", stroke: "var(--graph-node-stroke)" },
  peel: { fill: "var(--graph-node-fill)", stroke: "var(--graph-node-stroke)" },
  cluster: { fill: "var(--graph-cluster-fill)", stroke: "var(--graph-cluster-stroke)" },
  exchange: { fill: "var(--graph-exchange-fill)", stroke: "var(--graph-exchange-stroke)" },
  mixer: { fill: "var(--graph-mixer-fill)", stroke: "var(--graph-mixer-stroke)" },
  unresolved: { fill: "var(--graph-unresolved-fill)", stroke: "var(--graph-unresolved-stroke)" },
};

const LEGEND = [
  { type: "suspect", label: "Suspect wallet" },
  { type: "intermediate", label: "Intermediate hop" },
  { type: "cluster", label: "Cluster" },
  { type: "exchange", label: "Exchange match" },
  { type: "mixer", label: "Known mixer" },
  { type: "unresolved", label: "Unresolved" },
];

// layout cache, keyed by report_hash, so the interaction layer (popups,
// zoom, search, playback) doesn't have to recompute node positions - // it reads exactly what was drawn.
const _layoutCache = new Map();

function shortAddr(a) {
  if (!a) return "";
  return a.length > 16 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a;
}

function classify(address, report) {
  if (address === report.suspect_wallet) return "suspect";
  if (report.exchange_match && address === report.exchange_match.address) return "exchange";
  if (report.mixer_hit && address === report.mixer_hit.address) return "mixer";
  if (/cluster/i.test(address)) return "cluster";
  if (/unresolvedshard/i.test(address)) return "unresolved";
  return "intermediate";
}

/**
 * Builds { tiers: [[nodeId,...]], nodes: {id:{...}}, edges: [{from,to}] }
 * from the transaction list. Peel-chain destinations (>=4 same-hop single
 * -output small transfers from one address) are collapsed into a single
 * summary node so the diagram stays legible instead of drawing 11 dots.
 */
function buildGraphModel(report) {
  const txs = [...report.transactions].sort((a, b) => a.hop - b.hop);
  const nodes = {}; // id -> {id, tier, type, label, count}
  const edgeSet = new Map(); // "from|to" -> {from,to,count,hop,txHash}
  const addNode = (id, tier, type, label) => {
    if (!nodes[id]) nodes[id] = { id, tier, type, label: label || shortAddr(id), count: 1 };
  };
  const addEdge = (from, to, hop, txHash, value) => {
    const key = `${from}|${to}`;
    if (from === to) return;
    if (!edgeSet.has(key)) edgeSet.set(key, { from, to, hop, txHash, value });
  };

  addNode(report.suspect_wallet, 0, "suspect", "suspect");

  // group small (<0.5) single-output outflows from the same hop into one peel node
  const peelCandidates = txs.filter(t => t.outputs.length === 1 && t.outputs[0].value < 0.5 && t.inputs.length === 1);
  const peelByHop = {};
  peelCandidates.forEach(t => { (peelByHop[t.hop] = peelByHop[t.hop] || []).push(t); });
  const peelNodeIdByHop = {};
  Object.entries(peelByHop).forEach(([hop, list]) => {
    if (list.length >= 4) {
      const id = `__peel_summary_${hop}`;
      addNode(id, Number(hop), "peel", `peel chain (${list.length})`);
      nodes[id].count = list.length;
      peelNodeIdByHop[hop] = id;
      addEdge(list[0].inputs[0], id, Number(hop), list[0].tx_hash, list.reduce((s, t) => s + t.outputs[0].value, 0));
    }
  });
  const peelTxHashes = new Set(
    Object.entries(peelByHop).filter(([h, l]) => l.length >= 4).flatMap(([h, l]) => l.map(t => t.tx_hash))
  );

  txs.forEach(t => {
    if (peelTxHashes.has(t.tx_hash)) return; // already summarised
    t.inputs.forEach(inAddr => addNode(inAddr, Math.max(0, t.hop - 1), classify(inAddr, report)));
    t.outputs.forEach(o => {
      const type = classify(o.address, report);
      let label;
      if (type === "cluster") label = `cluster (${t.inputs.length >= 2 ? t.inputs.length : "?"} addr)`;
      else if (type === "exchange") label = report.exchange_match.exchange;
      else if (type === "mixer") label = report.mixer_hit.label.split(" ")[0];
      else if (type === "unresolved") label = "unresolved";
      addNode(o.address, t.hop, type, label);
      t.inputs.forEach(inAddr => addEdge(inAddr, o.address, t.hop, t.tx_hash, o.value));
    });
  });

  const maxTier = Math.max(...Object.values(nodes).map(n => n.tier));
  const tiers = Array.from({ length: maxTier + 1 }, () => []);
  Object.values(nodes).forEach(n => tiers[n.tier].push(n.id));

  return { nodes, tiers, edges: Array.from(edgeSet.values()) };
}

function radiusFor(type) {
  return { suspect: 15, cluster: 12, exchange: 17, mixer: 14, unresolved: 9, peel: 11, intermediate: 9 }[type] || 9;
}

/** Node fill intensity along the path leading to the terminal (risk heatmap):
 *  hotter (copper/crimson) the closer a node sits to a mixer or high-confidence
 *  exchange match, cooler (paper) further back. Suspect/exchange/mixer keep
 *  their semantic colours; only plain intermediate hops get heat-shaded.
 *  The interpolation endpoints come from --graph-heat-from/--graph-heat-to
 *  (tokens.css), read live off the document so the gradient itself flips
 *  with the theme instead of hard-coding one dark-only pair of RGB values. */
function heatFillFor(node, report, maxTier) {
  if (node.type !== "intermediate") return COLORS[node.type] || COLORS.intermediate;
  const proximity = maxTier > 0 ? node.tier / maxTier : 0;
  const risk = report.mixer_hit ? proximity : (report.exchange_match ? proximity * report.confidence : proximity * 0.4);
  const t = Math.min(1, Math.max(0, risk));
  // color-mix() keeps the fill live: it re-resolves when the theme toggles,
  // instead of freezing an rgb() computed at render time.
  const pct = Math.round(t * 100);
  return { fill: `color-mix(in srgb, var(--graph-heat-to) ${pct}%, var(--graph-heat-from))`, stroke: "var(--graph-node-stroke)" };
}

export function renderFundFlowSVG(report, opts = {}) {
  const { width = 560, height = 230 } = opts;
  if (!report.transactions || report.transactions.length === 0) {
    return `<div class="graph-empty">No transactions traced on this path.</div>`;
  }
  const model = buildGraphModel(report);
  const marginX = 56, marginY = 40;
  const usableW = width - marginX * 2;
  const usableH = height - marginY * 2;
  const nTiers = model.tiers.length;

  const pos = {};
  model.tiers.forEach((ids, tierIdx) => {
    const x = nTiers === 1 ? width / 2 : marginX + (usableW * tierIdx) / (nTiers - 1);
    ids.forEach((id, i) => {
      const y = ids.length === 1 ? height / 2 : marginY + (usableH * i) / Math.max(1, ids.length - 1);
      pos[id] = { x, y };
    });
  });
  _layoutCache.set(report.report_hash, { model, pos, width, height, maxTier: nTiers - 1 });

  const hopLabelsSVG = model.tiers.map((_, tierIdx) => {
    const x = nTiers === 1 ? width / 2 : marginX + (usableW * tierIdx) / (nTiers - 1);
    return `<text x="${x}" y="16" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="var(--graph-hop-label)">HOP ${tierIdx}</text>`;
  }).join("");

  const edgesSVG = model.edges.map((e, i) => {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) return "";
    const isTerminal = model.nodes[e.to].type === "exchange" || model.nodes[e.to].type === "mixer";
    const stroke = isTerminal ? (model.nodes[e.to].type === "mixer" ? "var(--graph-edge-hot-mixer)" : "var(--graph-edge-hot-exchange)") : "var(--graph-edge)";
    const width_ = isTerminal ? 2.4 : 1.6;
    // shorten the line so the arrowhead marker doesn't overlap the target node
    const rTarget = radiusFor(model.nodes[e.to].type) + 7;
    const dx = b.x - a.x, dy = b.y - a.y;
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    const ex = b.x - (dx / len) * rTarget, ey = b.y - (dy / len) * rTarget;
    // gentle perpendicular bow, alternating side by edge index, so parallel
    // or crossing fund-flows read as distinct arcs instead of a flat grid
    // of overlapping straight lines - this was the single most "boring"
    // part of the diagram before.
    const mx = (a.x + ex) / 2, my = (a.y + ey) / 2;
    const nx = -dy / len, ny = dx / len;
    const bow = Math.min(20, len * 0.16) * (i % 2 === 0 ? 1 : -1);
    const cx = mx + nx * bow, cy = my + ny * bow;
    return `<path class="graph-edge" data-edge-idx="${i}" d="M ${a.x} ${a.y} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${ex} ${ey}" fill="none" ` +
      `stroke="${stroke}" stroke-width="${width_}" marker-end="url(#vajra-arrow${isTerminal ? "-hot" : ""})" style="cursor:pointer;"/>`;
  }).join("");

  // Terminal + suspect nodes are the whole point of a trace report, so
  // they get a radial-gradient fill (depth, instead of a flat disc), a
  // soft glow filter, a thin outer ring, and a pulsing "live signal"
  // halo (CSS, see components.css .graph-node-halo). Plain intermediate
  // hops keep the existing flat heat-shaded fill so the hot nodes still
  // read as the standout signal, not just more decoration everywhere.
  const GRADIENT_FOR = {
    suspect: "url(#vajra-grad-suspect)", cluster: "url(#vajra-grad-cluster)",
    exchange: "url(#vajra-grad-exchange)", mixer: "url(#vajra-grad-mixer)", unresolved: "url(#vajra-grad-unresolved)",
  };
  const HOT_TYPES = new Set(["suspect", "exchange", "mixer"]);

  const nodesSVG = Object.values(model.nodes).map(n => {
    const p = pos[n.id];
    if (!p) return "";
    const c = heatFillFor(n, report, nTiers - 1);
    const fill = GRADIENT_FOR[n.type] || c.fill;
    const r = radiusFor(n.type);
    const strokeW = n.type === "suspect" || n.type === "exchange" ? 1.8 : 1.4;
    const isHot = HOT_TYPES.has(n.type);
    const haloColor = n.type === "exchange" ? "var(--graph-glow-exchange)" : (n.type === "mixer" ? "var(--graph-glow-mixer)" : "var(--graph-glow-suspect)");
    let extra = "";
    if (n.type === "exchange" && report.confidence != null) {
      extra = `<text x="${p.x}" y="${p.y - r - 6}" text-anchor="middle" font-family="JetBrains Mono" font-size="10" fill="var(--graph-label-exchange)">${Math.round(report.confidence * 100)}%</text>`;
    }
    const halo = isHot
      ? `<circle class="graph-node-halo" cx="${p.x}" cy="${p.y}" r="${r + 5}" fill="none" stroke="${haloColor}" stroke-width="2"/>`
      : "";
    const outerRing = (n.type === "exchange" || n.type === "mixer")
      ? `<circle cx="${p.x}" cy="${p.y}" r="${r + 4}" fill="none" stroke="${c.stroke}" stroke-width="1" stroke-opacity="0.4"/>`
      : "";
    return `<g class="graph-node${isHot ? " graph-node-hot" : ""}" data-node-id="${encodeURIComponent(n.id)}" style="cursor:pointer;">` +
      halo + outerRing +
      `<circle cx="${p.x}" cy="${p.y}" r="${r}" fill="${fill}" stroke="${c.stroke}" stroke-width="${strokeW}"${isHot ? ' filter="url(#vajra-node-glow)"' : ""}/>` +
      `<text x="${p.x}" y="${p.y + r + 13}" text-anchor="middle" font-family="Inter" font-size="10" fill="${n.type === 'exchange' ? 'var(--graph-label-exchange)' : (n.type === 'mixer' ? 'var(--graph-label-mixer)' : 'var(--graph-label)')}">${n.label}</text>` +
      extra + `</g>`;
  }).join("");

  const defs = `
    <defs>
      <marker id="vajra-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="userSpaceOnUse">
        <path d="M0,0 L6,3 L0,6 Z" fill="var(--graph-edge)"/>
      </marker>
      <marker id="vajra-arrow-hot" markerWidth="9" markerHeight="9" refX="7" refY="3.5" orient="auto" markerUnits="userSpaceOnUse">
        <path d="M0,0 L7,3.5 L0,7 Z" fill="var(--graph-edge-hot-exchange)"/>
      </marker>
      <filter id="vajra-node-glow" x="-140%" y="-140%" width="380%" height="380%">
        <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur"/>
        <feMerge>
          <feMergeNode in="blur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
      <radialGradient id="vajra-grad-suspect" cx="35%" cy="28%" r="75%">
        <stop offset="0%" stop-color="var(--graph-suspect-stroke)" stop-opacity="0.55"/>
        <stop offset="100%" stop-color="var(--graph-suspect-fill)" stop-opacity="1"/>
      </radialGradient>
      <radialGradient id="vajra-grad-cluster" cx="35%" cy="28%" r="75%">
        <stop offset="0%" stop-color="var(--graph-cluster-stroke)" stop-opacity="0.4"/>
        <stop offset="100%" stop-color="var(--graph-cluster-fill)" stop-opacity="1"/>
      </radialGradient>
      <radialGradient id="vajra-grad-exchange" cx="35%" cy="28%" r="75%">
        <stop offset="0%" stop-color="var(--graph-exchange-stroke)" stop-opacity="0.55"/>
        <stop offset="100%" stop-color="var(--graph-exchange-fill)" stop-opacity="1"/>
      </radialGradient>
      <radialGradient id="vajra-grad-mixer" cx="35%" cy="28%" r="75%">
        <stop offset="0%" stop-color="var(--graph-mixer-stroke)" stop-opacity="0.55"/>
        <stop offset="100%" stop-color="var(--graph-mixer-fill)" stop-opacity="1"/>
      </radialGradient>
      <radialGradient id="vajra-grad-unresolved" cx="35%" cy="28%" r="75%">
        <stop offset="0%" stop-color="var(--graph-unresolved-stroke)" stop-opacity="0.4"/>
        <stop offset="100%" stop-color="var(--graph-unresolved-fill)" stop-opacity="1"/>
      </radialGradient>
    </defs>`;

  const svg = `<svg id="graphSvg-${report.report_hash?.slice(0, 8) || "x"}" class="graph-svg" viewBox="0 0 ${width} ${height}" role="img" ` +
    `aria-label="Fund flow diagram with ${model.tiers.length} hop tiers, from the suspect wallet to ${report.exchange_match ? report.exchange_match.exchange : (report.mixer_hit ? "a known mixer" : "an unresolved terminal wallet")}">` +
    `${defs}${hopLabelsSVG}${edgesSVG}${nodesSVG}</svg>`;

  const legendHTML = LEGEND.map(l => `<span><i style="background:${COLORS[l.type].fill};border:1px solid ${COLORS[l.type].stroke}"></i>${l.label}</span>`).join("");

  return `
    <div class="graph-toolbar" data-graph-hash="${report.report_hash}">
      <input type="search" placeholder="Search wallet address…" class="graph-search" />
      <button class="graph-btn" data-graph-action="zoom-in" title="Zoom in">+</button>
      <button class="graph-btn" data-graph-action="zoom-out" title="Zoom out">−</button>
      <button class="graph-btn" data-graph-action="zoom-reset" title="Reset zoom">Reset</button>
    </div>
    <div class="graph-svg-wrap" data-graph-wrap="${report.report_hash}">${svg}</div>
    <div class="graph-legend">${legendHTML}</div>
    ${renderTimelineReplay(report)}
  `;
}

/**
 * Investigation Timeline Replay - scrubs through report.transactions in
 * chronological order (they already carry real timestamp + hop + value
 * data from the trace) and reveals the matching hop tier on the graph
 * above as the slider moves, with a live readout of the exact
 * transaction at that position. Not a canned animation: the slider
 * position IS the index into the real, already-traced transaction list.
 */
function renderTimelineReplay(report) {
  if (!report.transactions || report.transactions.length === 0) return "";
  const steps = [...report.transactions].sort((a, b) => {
    const ta = a.timestamp ? new Date(a.timestamp).getTime() : a.hop;
    const tb = b.timestamp ? new Date(b.timestamp).getTime() : b.hop;
    return ta - tb;
  });
  return `
    <div class="timeline-replay" data-timeline-hash="${report.report_hash}">
      <div class="timeline-replay-head">
        <span class="timeline-replay-title">Investigation timeline replay</span>
        <button class="graph-btn" data-timeline-action="play" title="Auto-play through every hop in order">▶ Play</button>
      </div>
      <input type="range" class="timeline-slider" min="0" max="${steps.length - 1}" value="0" step="1" />
      <div class="timeline-readout" data-timeline-readout></div>
    </div>
  `;
}

function timelineEventLabel(tx, report) {
  const flags = [];
  if (report.mixer_hit && tx.outputs.some((o) => o.address === report.mixer_hit.address)) flags.push({ cls: "mixer", label: "Mixer hop" });
  if (report.exchange_match && tx.outputs.some((o) => o.address === report.exchange_match.address)) flags.push({ cls: "exchange", label: "Exchange terminal" });
  if (tx.outputs.length === 1 && tx.outputs[0].value < 0.5 && tx.inputs.length === 1) flags.push({ cls: "structuring", label: "Structuring-pattern hop" });
  return flags;
}

function renderTimelineStep(tx, idx, total, report) {
  const flags = timelineEventLabel(tx, report);
  const when = tx.timestamp ? new Date(tx.timestamp).toLocaleString() : `hop ${tx.hop}`;
  return `
    <div class="timeline-step">
      <div class="timeline-step-pos">Event ${idx + 1} of ${total} · Hop ${tx.hop}</div>
      <div class="timeline-step-flow mono">${shortAddr(tx.inputs[0] || "")} → ${shortAddr(tx.outputs[0]?.address || "")}</div>
      <div class="timeline-step-meta">
        <span>${when}</span>
        <span>${tx.outputs[0] ? Number(tx.outputs[0].value).toFixed(4) : " - "} value</span>
        <span class="mono">${tx.tx_hash || ""}</span>
      </div>
      ${flags.length ? `<div class="timeline-step-flags">${flags.map((f) => `<span class="timeline-flag ${f.cls}">${f.label}</span>`).join("")}</div>` : ""}
    </div>
  `;
}

function popupContent(node, report) {
  const isTx = false;
  if (node.type === "exchange") {
    return `<div class="t">Exchange match</div><div class="s">${report.exchange_match.exchange}</div><div class="s">${node.id}</div>`;
  }
  if (node.type === "mixer") {
    return `<div class="t">Known mixer / tumbler</div><div class="s">${report.mixer_hit.label}</div><div class="s">${node.id}</div>`;
  }
  if (node.type === "suspect") {
    return `<div class="t">Suspect wallet</div><div class="s">${node.id}</div>`;
  }
  if (node.type === "cluster") {
    return `<div class="t">Cluster</div><div class="s">${node.label}</div><div class="s">${node.id}</div>`;
  }
  if (node.type === "peel") {
    return `<div class="t">Peel-chain summary</div><div class="s">${node.count} sequential small outflows</div>`;
  }
  return `<div class="t">Intermediate wallet</div><div class="s">Hop ${node.tier}</div><div class="s">${node.id}</div>`;
}

function edgePopupContent(edge) {
  return `<div class="t">Transaction</div><div class="s">tx ${edge.txHash ? edge.txHash.slice(0, 18) + "…" : " - "}</div>` +
    `<div class="s">hop ${edge.hop}${edge.value != null ? ` · value ${Number(edge.value).toFixed(4)}` : ""}</div>`;
}

/**
 * Wires up interactivity on a freshly-inserted graph: node/edge click
 * popups, zoom controls, wallet search/filter (dims non-matching
 * nodes), and a hop-by-hop timeline playback that reveals tiers in
 * sequence. Call once, right after the HTML from renderFundFlowSVG()
 * has been inserted into the DOM.
 */
export function mountGraphInteractions(container, report) {
  const cached = _layoutCache.get(report.report_hash);
  if (!cached) return;
  const { model } = cached;
  const wrap = container.querySelector(`[data-graph-wrap="${report.report_hash}"]`);
  const toolbar = container.querySelector(`[data-graph-hash="${report.report_hash}"]`);
  if (!wrap || !toolbar) return;
  const svg = wrap.querySelector("svg");

  let popupEl = null;
  const closePopup = () => { if (popupEl) { popupEl.remove(); popupEl = null; } };
  const showPopup = (html, evt) => {
    closePopup();
    popupEl = document.createElement("div");
    popupEl.className = "graph-node-popup";
    popupEl.innerHTML = html;
    wrap.appendChild(popupEl);
    const wrapRect = wrap.getBoundingClientRect();
    const x = Math.min(evt.clientX - wrapRect.left + 10, wrapRect.width - 200);
    const y = Math.max(evt.clientY - wrapRect.top - 10, 4);
    popupEl.style.left = `${Math.max(4, x)}px`;
    popupEl.style.top = `${y}px`;
  };

  svg.querySelectorAll(".graph-node").forEach((g) => {
    g.addEventListener("click", (evt) => {
      evt.stopPropagation();
      const id = decodeURIComponent(g.dataset.nodeId);
      const node = model.nodes[id];
      if (node) showPopup(popupContent(node, report), evt);
    });
  });
  svg.querySelectorAll(".graph-edge").forEach((line) => {
    line.addEventListener("click", (evt) => {
      evt.stopPropagation();
      const edge = model.edges[Number(line.dataset.edgeIdx)];
      if (edge) showPopup(edgePopupContent(edge), evt);
    });
  });
  document.addEventListener("click", closePopup, { once: false });

  // --- zoom ---
  let scale = 1;
  const baseViewBox = svg.getAttribute("viewBox");
  const [vx, vy, vw, vh] = baseViewBox.split(" ").map(Number);
  const applyZoom = () => {
    const nw = vw / scale, nh = vh / scale;
    const cx = vx + vw / 2, cy = vy + vh / 2;
    svg.setAttribute("viewBox", `${cx - nw / 2} ${cy - nh / 2} ${nw} ${nh}`);
  };
  toolbar.querySelector('[data-graph-action="zoom-in"]').addEventListener("click", () => { scale = Math.min(3, scale + 0.35); applyZoom(); });
  toolbar.querySelector('[data-graph-action="zoom-out"]').addEventListener("click", () => { scale = Math.max(0.6, scale - 0.35); applyZoom(); });
  toolbar.querySelector('[data-graph-action="zoom-reset"]').addEventListener("click", () => { scale = 1; svg.setAttribute("viewBox", baseViewBox); });

  // --- search / filter: dim nodes+edges not matching the query ---
  const searchInput = toolbar.querySelector(".graph-search");
  searchInput.addEventListener("input", () => {
    const q = searchInput.value.trim().toLowerCase();
    svg.querySelectorAll(".graph-node").forEach((g) => {
      const id = decodeURIComponent(g.dataset.nodeId).toLowerCase();
      g.style.opacity = !q || id.includes(q) ? "1" : "0.15";
    });
    svg.querySelectorAll(".graph-edge").forEach((line) => {
      const edge = model.edges[Number(line.dataset.edgeIdx)];
      const match = !q || edge.from.toLowerCase().includes(q) || edge.to.toLowerCase().includes(q);
      line.style.opacity = match ? "1" : "0.1";
    });
  });

  // --- Investigation Timeline Replay: scrubbable slider + auto-play,
  // both driving the same `revealUpTo(index)` so dragging and playing
  // stay perfectly in sync with the real chronological transaction order.
  const timelineHost = container.querySelector(`[data-timeline-hash="${report.report_hash}"]`);
  if (timelineHost) {
    const steps = [...report.transactions].sort((a, b) => {
      const ta = a.timestamp ? new Date(a.timestamp).getTime() : a.hop;
      const tb = b.timestamp ? new Date(b.timestamp).getTime() : b.hop;
      return ta - tb;
    });
    const slider = timelineHost.querySelector(".timeline-slider");
    const readout = timelineHost.querySelector("[data-timeline-readout]");
    const playBtn = timelineHost.querySelector('[data-timeline-action="play"]');
    const allNodes = Array.from(svg.querySelectorAll(".graph-node"));
    const allEdges = Array.from(svg.querySelectorAll(".graph-edge"));
    allNodes.forEach((n) => { n.style.transition = "opacity 220ms ease"; });
    allEdges.forEach((e) => { e.style.transition = "opacity 220ms ease"; });

    const revealUpTo = (index) => {
      const currentHop = steps[index].hop;
      allNodes.forEach((n) => {
        const id = decodeURIComponent(n.dataset.nodeId);
        const node = model.nodes[id];
        n.style.opacity = node && node.tier <= currentHop ? "1" : "0.08";
      });
      allEdges.forEach((e) => {
        const edge = model.edges[Number(e.dataset.edgeIdx)];
        e.style.opacity = edge && edge.hop <= currentHop ? "1" : "0.08";
      });
      readout.innerHTML = renderTimelineStep(steps[index], index, steps.length, report);
    };

    slider.addEventListener("input", () => revealUpTo(Number(slider.value)));
    revealUpTo(0);

    let playing = false;
    playBtn.addEventListener("click", () => {
      if (playing) return;
      playing = true;
      playBtn.classList.add("active");
      playBtn.textContent = "● Playing…";
      slider.value = "0";
      revealUpTo(0);
      let i = 0;
      const step = () => {
        i += 1;
        if (i >= steps.length) {
          playing = false;
          playBtn.classList.remove("active");
          playBtn.textContent = "▶ Play";
          return;
        }
        slider.value = String(i);
        revealUpTo(i);
        setTimeout(step, 550);
      };
      setTimeout(step, 550);
    });
  }
}
