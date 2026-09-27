import * as api from "../api.js";

export async function renderAudit(container, ctx) {
  if (ctx.officer.role !== "admin") {
    container.innerHTML = `
      <div class="empty-state">
        <div class="t">Admin access required</div>
        <div class="s">The audit log is restricted to the Admin role, per role-based access control. Sign in as I4C Admin Desk to view it.</div>
      </div>`;
    return;
  }

  container.innerHTML = `
    <div class="view-head">
      <div><div class="view-title">Audit log</div><div class="view-sub">Every login, trace run, notice action and vault download - immutable, timestamped.</div></div>
    </div>
    <div class="table-wrap" id="auditWrap"><div style="padding:16px;"><div class="skel" style="height:16px;"></div></div></div>
  `;

  const entries = await api.listAudit();
  const wrap = container.querySelector("#auditWrap");
  if (!entries.length) {
    wrap.innerHTML = `<div class="empty-state"><div class="t">No activity yet</div></div>`;
    return;
  }
  wrap.innerHTML = entries.map((e) => `
    <div class="audit-row">
      <div class="audit-time">${new Date(e.created_at).toLocaleString("en-IN")}</div>
      <div class="audit-actor">${e.officer_id || "system"}</div>
      <div>
        <span class="audit-action">${e.action}</span>${e.target ? ` &middot; ${e.target}` : ""}
        ${e.detail ? `<div class="audit-detail">${typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail)}</div>` : ""}
      </div>
    </div>
  `).join("");
}
