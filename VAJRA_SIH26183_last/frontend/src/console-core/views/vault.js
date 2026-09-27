import * as api from "../api.js";
import { relativeTime } from "../format.js";
import { toast } from "../components/toast.js";

export async function renderVault(container, ctx) {
  container.innerHTML = `
    <div class="view-head">
      <div><div class="view-title">Evidence vault</div><div class="view-sub">Every trace report is hash-anchored (SHA-256) at generation time for chain-of-custody.</div></div>
    </div>
    <div class="table-wrap responsive-table">
      <table class="case-table">
        <thead><tr><th>Case</th><th>Generated</th><th>SHA-256</th><th></th></tr></thead>
        <tbody id="vaultTbody"><tr><td colspan="4"><div class="skel" style="height:16px;"></div></td></tr></tbody>
      </table>
    </div>
    <div class="case-cards" id="vaultCards"></div>
  `;

  const cases = ctx.state.cases.length ? ctx.state.cases : await api.listCases();
  const reports = await api.listVault();

  if (!reports.length) {
    container.querySelector("#vaultTbody").innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-faint);padding:32px;">No evidence packs generated yet.</td></tr>`;
    return;
  }

  container.querySelector("#vaultTbody").innerHTML = reports.map((r) => {
    const c = cases.find((cc) => cc.id === r.case_id);
    const hash = r.report_hash ? `${r.report_hash.slice(0, 10)}…${r.report_hash.slice(-6)}` : "computed on view";
    return `
      <tr>
        <td class="mono">${r.ncrp_ref || (c && c.ncrp_ref) || r.case_id}</td>
        <td>${relativeTime(r.generated_at)}</td>
        <td class="mono" style="font-size:calc(11.5px * var(--fs-scale, 1));color:var(--text-soft);">${hash}</td>
        <td><button class="btn-secondary btn-sm" data-dl="${r.id}" data-case="${r.case_id}">Download</button></td>
      </tr>
    `;
  }).join("");

  container.querySelector("#vaultCards").innerHTML = reports.map((r) => {
    const c = cases.find((cc) => cc.id === r.case_id);
    return `
      <div class="case-card">
        <div class="case-card-top"><span class="case-card-id mono">${r.ncrp_ref || (c && c.ncrp_ref) || r.case_id}</span></div>
        <div style="font-size:calc(11px * var(--fs-scale, 1));color:var(--text-faint);">${relativeTime(r.generated_at)}</div>
        <button class="btn-secondary btn-sm" data-dl="${r.id}" data-case="${r.case_id}" style="align-self:flex-start;">Download</button>
      </div>
    `;
  }).join("");

  container.querySelectorAll("[data-dl]").forEach((btn) => btn.addEventListener("click", async () => {
    if (api.getMode() === "live") {
      const a = document.createElement("a");
      a.href = api.vaultDownloadUrl(btn.dataset.dl);
      a.click();
    } else {
      const report = await api.getCaseReport(btn.dataset.case);
      if (!report) { toast("No cached report for this case.", "error"); return; }
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${btn.dataset.case}-evidence.json`;
      a.click();
    }
    toast("Evidence pack downloaded.", "success");
  }));
}
