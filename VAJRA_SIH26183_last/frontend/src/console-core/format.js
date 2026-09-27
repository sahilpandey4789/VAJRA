export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function shortAddr(a) {
  if (!a) return "";
  return a.length > 14 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a;
}

export function riskChip(band, confidence) {
  const pct = confidence != null ? Math.round(confidence * 100) : null;
  const labelMap = { high: "High", medium: "Medium", low: "Low" };
  const cls = band === "high" ? "high" : band === "medium" ? "med" : "low";
  return `<span class="chip ${cls}">${labelMap[band] || " - "}${pct != null ? ` · ${pct}` : ""}</span>`;
}

export function statusLabel(status) {
  const map = {
    new: "New", in_progress: "In progress", trace_complete: "Trace complete",
    notice_issued: "Notice issued", cleared: "Cleared", closed: "Closed",
  };
  return map[status] || status;
}

export function relativeTime(iso) {
  if (!iso) return " - ";
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = now - then;
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs === 1 ? "" : "s"} ago`;
  const days = Math.round(hrs / 24);
  if (days < 14) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function chainLabel(chain) {
  const map = { ETHEREUM: "ETH", TRON: "TRC-20", BITCOIN: "BTC" };
  return map[chain] || chain;
}

export function initials(name) {
  if (!name) return "?";
  return name.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
}
