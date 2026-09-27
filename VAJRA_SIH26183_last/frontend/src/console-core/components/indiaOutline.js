// Background floor-plane for the Geographic Trail panel. Renders a
// perspective grid (converging lines + vignette) instead of any country
// silhouette or outline - no verified India GeoJSON/TopoJSON boundary
// data is bundled here, and this panel never claims to be a map. City
// dots, elevation stems and the trail arc (drawn by geoTrail.js) carry
// the real information; this is just a depth cue behind them.
//
// To add a real map later: swap this for an India TopoJSON (e.g.
// DataMeet's open India-maps project) via react-simple-maps, keyed to
// real (lat, lng) instead of the (x, y) positions in india_map.py.

/** @param opts.tone CSS color/var() for the grid lines (defaults to --copper) */
export function indiaOutlineSVG(opts = {}) {
  const tone = opts.tone || "var(--copper)";
  const cx = 50, horizon = 6, floorY = 100;

  // Horizontal grid lines get denser and tighter together near the
  // horizon (small step) and wider apart near the foreground (large
  // step) - that spacing gradient alone is what reads as a receding
  // floor plane instead of a flat square grid.
  let hLines = "";
  const rows = [6, 16, 28, 42, 58, 76, 96];
  for (const y of rows) {
    const spread = 4 + (y - horizon) * 0.42; // narrower near horizon, wider up front
    const op = 0.06 + (y - horizon) / (floorY - horizon) * 0.22;
    hLines += `<line x1="${cx - spread}" y1="${y}" x2="${cx + spread}" y2="${y}" stroke="${tone}" stroke-opacity="${op.toFixed(2)}" stroke-width="0.3"/>`;
  }

  // Vertical lines fan out from a vanishing point above the panel down
  // to the foreground edge - the other half of the perspective illusion.
  let vLines = "";
  for (const dx of [-36, -22, -10, 0, 10, 22, 36]) {
    vLines += `<line x1="${cx}" y1="${horizon}" x2="${cx + dx}" y2="${floorY}" stroke="${tone}" stroke-opacity="0.1" stroke-width="0.3"/>`;
  }

  return `
    <defs>
      <radialGradient id="geoFloorGlow" cx="50%" cy="15%" r="80%">
        <stop offset="0%" stop-color="${tone}" stop-opacity="0.10"/>
        <stop offset="60%" stop-color="${tone}" stop-opacity="0.02"/>
        <stop offset="100%" stop-color="${tone}" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <rect x="1" y="1" width="98" height="98" rx="3" fill="url(#geoFloorGlow)" stroke="${tone}" stroke-opacity="0.2" stroke-width="0.5"/>
    ${vLines}
    ${hLines}
    <text x="4" y="96.5" font-family="JetBrains Mono" font-size="2.2" fill="${tone}" fill-opacity="0.45">RELATIVE LAYOUT - NOT TO SCALE</text>
  `;
}
