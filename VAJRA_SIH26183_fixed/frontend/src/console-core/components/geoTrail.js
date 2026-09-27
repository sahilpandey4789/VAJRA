import { indiaOutlineSVG } from "./indiaOutline.js";

/**
 * Renders the per-case Geographic Trail: complaint-filed city to
 * resolved exchange HQ city (if any). Different from the National Case
 * Distribution view (console-core/views/nationalmap.js), which aggregates
 * case counts by city across the system - this shows one case's actual
 * journey.
 *
 * A wallet address has no inherent geography, so only the two real
 * anchors from backend/engine/india_map.py's case_geo_trail() get
 * plotted: origin jurisdiction and (when resolved) the exchange's HQ
 * city. See that function's docstring for what each trail_type means.
 *
 * Visual style: markers sit "raised" above the floor grid (a stem down
 * to a soft shadow ellipse at their true x,y) and the trail between them
 * arcs above the floor rather than lying flat on it - the usual fake-3D
 * pin/flight-path treatment, no WebGL/canvas needed.
 */

// How far a marker "floats" above its true floor position (y offset).
const LIFT = 6;

function marker(x, y, { r = 2.6, fill, ring = false } = {}) {
  const my = y - LIFT;
  return `
    <ellipse cx="${x}" cy="${y}" rx="${r * 0.9}" ry="${r * 0.32}" fill="#000" opacity="0.35"/>
    <line x1="${x}" y1="${y - 1}" x2="${x}" y2="${my + r * 0.4}" stroke="${fill}" stroke-width="0.4" opacity="0.55"/>
    ${ring ? `
    <circle cx="${x}" cy="${my}" r="${r * 1.7}" fill="none" stroke="${fill}" stroke-width="0.4" opacity="0.5">
      <animate attributeName="r" values="${r * 1.1};${r * 2.2};${r * 1.1}" dur="2.4s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.6;0;0.6" dur="2.4s" repeatCount="indefinite"/>
    </circle>` : ""}
    <circle cx="${x}" cy="${my}" r="${r}" fill="url(#pinGrad-${fill.replace(/[^a-zA-Z0-9]/g, "")})" stroke="var(--paper)" stroke-width="0.5"/>
  `;
}

function pinGradient(id, color) {
  return `
    <radialGradient id="pinGrad-${id}" cx="35%" cy="30%" r="70%">
      <stop offset="0%" stop-color="#fff" stop-opacity="0.9"/>
      <stop offset="35%" stop-color="${color}"/>
      <stop offset="100%" stop-color="${color}" stop-opacity="0.75"/>
    </radialGradient>
  `;
}

export function renderGeoTrail(geoTrail) {
  if (!geoTrail) return "";
  const { trail_type, exchange, origin, destination } = geoTrail;
  const oy = origin.y - LIFT;

  const originDot = `
    ${marker(origin.x, origin.y, { fill: "var(--slate)", ring: true })}
    <text x="${origin.x}" y="${oy - 4.5}" text-anchor="middle" font-family="Inter" font-size="3.4" fill="var(--text)">${origin.city}</text>
    <text x="${origin.x}" y="${origin.y + 4.5}" text-anchor="middle" font-family="JetBrains Mono" font-size="2.4" fill="var(--text-faint)">COMPLAINT FILED</text>
  `;

  let destinationSVG = "";
  let pathSVG = "";
  let statusLine = "";
  let grads = pinGradient("var(--slate)".replace(/[^a-zA-Z0-9]/g, ""), "var(--slate)");

  if (trail_type === "resolved") {
    const dy = destination.y - LIFT;
    // Floor projection (flat, dim) under the actual raised arc - reinforces the lift.
    const floorD = `M${origin.x},${origin.y} L${destination.x},${destination.y}`;
    const midX = (origin.x + destination.x) / 2;
    const midY = Math.max(2, Math.min(oy, dy) - 14);
    const arcD = `M${origin.x},${oy} Q${midX},${midY} ${destination.x},${dy}`;
    pathSVG = `
      <path d="${floorD}" fill="none" stroke="var(--risk-high)" stroke-width="0.3" stroke-dasharray="0.6 1.4" opacity="0.25"/>
      <path d="${arcD}" fill="none" stroke="var(--risk-high)" stroke-width="0.6" stroke-linecap="round"
            stroke-dasharray="1.6 1.6" opacity="0.85">
        <animate attributeName="stroke-dashoffset" values="0;-30" dur="2.2s" repeatCount="indefinite"/>
      </path>
      <path d="${arcD}" fill="none" stroke="var(--risk-high)" stroke-width="1.6" opacity="0.12"/>
    `;
    grads += pinGradient("var(--risk-high)".replace(/[^a-zA-Z0-9]/g, ""), "var(--risk-high)");
    destinationSVG = `
      ${marker(destination.x, destination.y, { r: 2.9, fill: "var(--risk-high)" })}
      <text x="${destination.x}" y="${dy - 4.5}" text-anchor="middle" font-family="Inter" font-size="3.4" fill="var(--text)">${destination.city}</text>
      <text x="${destination.x}" y="${destination.y + 4.5}" text-anchor="middle" font-family="JetBrains Mono" font-size="2.4" fill="var(--risk-high)">${exchange.toUpperCase()} - FUNDS TRACED HERE</text>
    `;
    statusLine = `Funds traced from <b>${origin.city}, ${origin.state}</b> to <b>${exchange}</b>'s registered office in <b>${destination.city}, ${destination.state}</b>.`;
  } else if (trail_type === "international") {
    // no fixed India destination to plot - an arrow lifting off the edge, not a guessed point.
    const ex = Math.min(96, origin.x + 30), ey = Math.max(4, oy - 14);
    const eMidY = Math.max(2, Math.min(oy, ey) - 10);
    pathSVG = `
      <path d="M${origin.x},${oy} Q${(origin.x + ex) / 2},${eMidY} ${ex},${ey}" fill="none"
            stroke="var(--brass)" stroke-width="0.6" stroke-linecap="round" stroke-dasharray="1.6 1.6" opacity="0.85" marker-end="url(#geoTrailArrow)">
        <animate attributeName="stroke-dashoffset" values="0;-20" dur="1.8s" repeatCount="indefinite"/>
      </path>
    `;
    statusLine = `Funds traced to <b>${exchange}</b>, which has no fixed India headquarters - trail leaves India's jurisdiction (international exchange, cross-border request required).`;
  } else if (trail_type === "mixer") {
    destinationSVG = `
      <text x="${origin.x + 10}" y="${oy + 1}" text-anchor="middle" font-family="JetBrains Mono" font-size="6" fill="var(--risk-high)">✕</text>
    `;
    statusLine = `Funds entered a known mixer after leaving <b>${origin.city}</b> - the deterministic trail ends there. No destination location to plot; see Risk Patterns for the mixer match.`;
  } else {
    statusLine = `Case reported in <b>${origin.city}, ${origin.state}</b>. No exchange or mixer match yet on the current trace.`;
  }

  return `
    <div class="card geo-trail-card" style="margin-top:var(--sp-4);">
      <div class="card-title">GEOGRAPHIC TRAIL</div>
      <svg viewBox="0 0 100 100" class="geo-trail-svg" role="img"
           aria-label="Geographic trail from ${origin.city} to ${trail_type === "resolved" ? destination.city : "unresolved"}">
        <defs>
          <marker id="geoTrailArrow" markerWidth="6" markerHeight="6" refX="4" refY="2" orient="auto" markerUnits="userSpaceOnUse">
            <path d="M0,0 L5,2 L0,4 Z" fill="var(--brass)"/>
          </marker>
          ${grads}
        </defs>
        ${indiaOutlineSVG()}
        ${pathSVG}
        ${originDot}
        ${destinationSVG}
      </svg>
      <div class="geo-trail-status">${statusLine}</div>
      <div class="geo-trail-note">Anchored in two real facts, not a wallet's guessed location: where the complaint was filed, and the receiving exchange's actual registered office.</div>
    </div>
  `;
}
