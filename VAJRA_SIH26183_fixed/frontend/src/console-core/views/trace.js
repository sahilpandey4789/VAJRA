import * as api from "../api.js";
import { renderFundFlowSVG, mountGraphInteractions } from "../components/graph.js";
import { renderGeoTrail } from "../components/geoTrail.js";
import { toast } from "../components/toast.js";
import { shortAddr, chainLabel, relativeTime } from "../format.js";

const STAGE_LABELS = {
  collecting: "Collecting transaction history",
  tracing: "Tracing funds hop by hop",
  clustering: "Clustering related wallets",
  checking: "Checking for obfuscation (mixers)",
  scoring: "Scoring attribution confidence",
};
const STAGE_ORDER = ["collecting", "tracing", "clustering", "checking", "scoring"];

const ACTION_BADGE = {
  suggest_freeze: { cls: "freeze", label: "Freeze recommended" },
  suggest_kyc: { cls: "kyc", label: "KYC disclosure recommended" },
  manual_review: { cls: "review", label: "Manual review" },
  insufficient_evidence: { cls: "insufficient", label: "Insufficient evidence" },
};

let _activeTraceHandle = null;

export async function renderTrace(container, ctx) {
  const caseId = ctx.state.activeCaseId;
  const cases = ctx.state.cases.length ? ctx.state.cases : await api.listCases();
  if (!ctx.state.cases.length) ctx.setCases(cases);

  container.innerHTML = `
    <div class="view-head">
      <div>
        <div class="view-title" id="traceTitle">Trace wallet</div>
        <div class="view-sub" id="traceSub">Select a case from the queue, or paste any wallet address to start a new trace.</div>
      </div>
      <div id="reassignWrap"></div>
    </div>

    <div class="card" style="margin-bottom:var(--sp-5);">
      <div class="card-title">Wallet lookup</div>
      <form class="new-trace-form" id="lookupForm">
        <input type="text" id="walletInput" placeholder="Paste an Ethereum, Bitcoin or Tron wallet address…" autocomplete="off" spellcheck="false" />
        <button type="submit" class="btn-primary" id="lookupSubmit">Trace</button>
      </form>
    </div>

    <div class="card" style="margin-bottom:var(--sp-5);">
      <div class="card-title">Batch upload</div>
      <div style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-soft);margin-bottom:10px;">
        CSV with columns <code class="mono">suspect_wallet, chain, typology</code> (typology optional) - up to 200 wallets in one file, each validated exactly like a single manual entry.
      </div>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <input type="file" id="batchCsvInput" accept=".csv,text/csv" style="display:none;" />
        <button type="button" class="btn-secondary btn-sm" id="batchCsvBtn">Choose CSV file</button>
        <span id="batchCsvFilename" style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-faint);"></span>
      </div>
      <div id="batchResult" style="margin-top:12px;"></div>
    </div>

    <div id="traceBody"></div>
  `;

  const ADDR_PATTERNS = {
    ETHEREUM: /^0x[a-fA-F0-9]{40}$/,
    TRON: /^T[a-zA-Z0-9]{33}$/,
    BITCOIN: /^(bc1[ac-hj-np-z02-9]{20,60}|[13][a-km-zA-HJ-NP-Z1-9]{20,40})$/,
  };
  function detectChain(addr) {
    for (const [chain, re] of Object.entries(ADDR_PATTERNS)) if (re.test(addr)) return chain;
    return null;
  }

  container.querySelector("#lookupForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const val = container.querySelector("#walletInput").value.trim();
    if (!val) return;

    const match = cases.find((c) => c.suspect_wallet.toLowerCase() === val.toLowerCase());
    if (match) { ctx.openCase(match.id); return; }

    const chain = detectChain(val);
    if (!chain) {
      toast("That doesn't look like a valid Ethereum, Bitcoin or Tron address - check for typos.", "error", 4200);
      return;
    }

    const submitBtn = container.querySelector("#lookupSubmit");
    submitBtn.disabled = true;
    submitBtn.textContent = "Starting…";
    try {
      const created = await api.createCase({ suspect_wallet: val, chain });
      ctx.setCases([created, ...ctx.state.cases]);
      ctx.openCase(created.id);
    } catch (err) {
      toast(err.message || "Couldn't start a trace on that address.", "error", 4200);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Trace";
    }
  });

  container.querySelector("#batchCsvBtn").addEventListener("click", () => {
    container.querySelector("#batchCsvInput").click();
  });
  container.querySelector("#batchCsvInput").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    container.querySelector("#batchCsvFilename").textContent = file.name;
    const resultBox = container.querySelector("#batchResult");
    const btn = container.querySelector("#batchCsvBtn");
    btn.disabled = true;
    btn.textContent = "Uploading…";
    resultBox.innerHTML = "";
    try {
      const { created, errors, submitted } = await api.createCasesBatch(file);
      if (created.length) ctx.setCases([...created, ...ctx.state.cases]);
      resultBox.innerHTML = `
        <div class="approval-banner ${errors.length ? "pending" : "approved"}">
          <span>${created.length} of ${submitted} rows created${errors.length ? `, ${errors.length} rejected` : ""}.</span>
        </div>
        ${errors.length ? `
          <div class="table-wrap" style="margin-top:8px;">
            <table class="case-table">
              <thead><tr><th>Row</th><th>Wallet</th><th>Error</th></tr></thead>
              <tbody>
                ${errors.map((e2) => `<tr><td>${e2.row}</td><td class="mono">${(e2.input.suspect_wallet || "").slice(0, 20)}</td><td style="color:var(--risk-high);">${e2.error}</td></tr>`).join("")}
              </tbody>
            </table>
          </div>
        ` : ""}
      `;
    } catch (err) {
      resultBox.innerHTML = `<div class="approval-banner pending">${err.message || "Batch upload failed."}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "Choose CSV file";
      e.target.value = "";
    }
  });

  if (caseId) {
    await loadCase(container, ctx, caseId, cases);
  } else {
    container.querySelector("#traceBody").innerHTML = emptyState();
  }
}

function emptyState() {
  return `
    <div class="empty-state">
      <svg width="42" height="42" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="4" cy="10" r="2"/><circle cx="16" cy="5" r="2"/><circle cx="16" cy="15" r="2"/><path d="M6 10h5M10 10l4.5-4M10 10l4.5 4"/></svg>
      <div class="t">No case selected</div>
      <div class="s">Pick a case from the sidebar queue or the dashboard table, or paste a wallet address above.</div>
    </div>
  `;
}

async function loadCase(container, ctx, caseId, casesList) {
  const caseRow = (casesList || ctx.state.cases).find((c) => c.id === caseId);
  const body = container.querySelector("#traceBody");
  const reassignWrap = container.querySelector("#reassignWrap");
  if (!caseRow) { body.innerHTML = emptyState(); if (reassignWrap) reassignWrap.innerHTML = ""; return; }

  container.querySelector("#traceTitle").textContent = caseRow.ncrp_ref;
  container.querySelector("#traceSub").textContent =
    `Reported ${relativeTime(caseRow.reported_at)} · ${caseRow.typology} · officer ${ctx.officer.name}`;

  if (reassignWrap && (ctx.officer.role === "supervisor" || ctx.officer.role === "admin")) {
    renderReassignControl(reassignWrap, ctx, caseRow);
  } else if (reassignWrap) {
    reassignWrap.innerHTML = "";
  }

  body.innerHTML = `<div class="skel" style="height:220px;border-radius:8px;"></div>`;

  const report = await api.getCaseReport(caseId);
  if (!report) {
    body.innerHTML = `
      <div class="empty-state">
        <div class="t">No trace report yet</div>
        <div class="s">This case hasn't been traced. Run the pipeline to collect, cluster and score this wallet.</div>
        <button class="btn-primary" id="btnRunTrace" style="margin-top:14px;">Run trace</button>
      </div>`;
    body.querySelector("#btnRunTrace").addEventListener("click", () => runTraceFlow(container, ctx, caseRow));
    return;
  }
  renderReport(body, ctx, caseRow, report);
}

function renderReassignControl(wrap, ctx, caseRow) {
  wrap.innerHTML = `<button class="btn-secondary" id="btnReassign" title="Reassign this case to another officer">Reassign</button>`;
  wrap.querySelector("#btnReassign").addEventListener("click", async () => {
    wrap.innerHTML = `
      <form id="reassignForm" style="display:flex;gap:6px;align-items:center;">
        <select id="reassignSelect" style="min-width:180px;"><option value="">Loading officers…</option></select>
        <button type="submit" class="btn-primary" id="reassignSubmit" disabled>Move</button>
        <button type="button" class="btn-secondary" id="reassignCancel">Cancel</button>
      </form>`;
    const select = wrap.querySelector("#reassignSelect");
    const submitBtn = wrap.querySelector("#reassignSubmit");
    wrap.querySelector("#reassignCancel").addEventListener("click", () => renderReassignControl(wrap, ctx, caseRow));
    try {
      const officers = await api.listOfficers();
      const eligible = officers.filter((o) => o.id !== caseRow.assigned_officer_id);
      select.innerHTML = eligible.length
        ? eligible.map((o) => `<option value="${o.officer_code}">${o.name} · ${o.role} · ${o.jurisdiction}</option>`).join("")
        : `<option value="">No other officers available</option>`;
      submitBtn.disabled = !eligible.length;
    } catch (e) {
      select.innerHTML = `<option value="">Couldn't load officers</option>`;
      toast(e.message || "Couldn't load the officer list.", "error");
      return;
    }
    wrap.querySelector("#reassignForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const code = select.value;
      if (!code) return;
      submitBtn.disabled = true;
      submitBtn.textContent = "Moving…";
      try {
        const updated = await api.reassignCase(caseRow.id, code);
        toast(`Case ${caseRow.ncrp_ref} reassigned.`, "success");
        ctx.setCases(ctx.state.cases.map((c) => (c.id === updated.id ? updated : c)));
        renderReassignControl(wrap, ctx, updated);
      } catch (err) {
        toast(err.message || "Couldn't reassign this case.", "error");
        submitBtn.disabled = false;
        submitBtn.textContent = "Move";
      }
    });
  });
}

function runTraceFlow(container, ctx, caseRow) {
  showStepper(container, caseRow);
  if (_activeTraceHandle) _activeTraceHandle.cancel();
  _activeTraceHandle = api.runTrace(caseRow.id, {
    onStage: (evt) => updateStepper(container, evt.stage, evt.detail),
    onError: (msg) => { hideStepper(container); toast(msg, "error"); },
    onResult: (report) => {
      hideStepper(container);
      const body = container.querySelector("#traceBody");
      renderReport(body, ctx, caseRow, report);
      toast("Trace complete.", "success");
    },
  });
}

function showStepper(container, caseRow) {
  let overlay = document.getElementById("stepperOverlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "stepperOverlay";
    overlay.className = "stepper-overlay";
    document.body.appendChild(overlay);
  }
  overlay.innerHTML = `
    <div class="stepper-box">
      <div class="stepper-title">Tracing ${caseRow.ncrp_ref}</div>
      <div class="stepper-sub">${shortAddr(caseRow.suspect_wallet)} · ${chainLabel(caseRow.chain)}</div>
      <div id="stepRows">
        ${STAGE_ORDER.map((s) => `
          <div class="step-row" data-stage="${s}">
            <div class="step-dot"></div>
            <div class="step-label">${STAGE_LABELS[s]}</div>
          </div>
          <div class="step-detail" data-stage-detail="${s}"></div>
        `).join("")}
      </div>
      <button class="stepper-cancel" id="stepperCancel">Cancel trace</button>
    </div>
  `;
  overlay.classList.add("show");
  overlay.querySelector("#stepperCancel").addEventListener("click", () => {
    if (_activeTraceHandle) _activeTraceHandle.cancel();
    hideStepper(container);
  });
}
function updateStepper(container, stage, detail) {
  const overlay = document.getElementById("stepperOverlay");
  if (!overlay) return;
  const idx = STAGE_ORDER.indexOf(stage);
  STAGE_ORDER.forEach((s, i) => {
    const row = overlay.querySelector(`.step-row[data-stage="${s}"]`);
    if (!row) return;
    row.classList.remove("active", "done");
    if (i < idx) row.classList.add("done");
    if (i === idx) row.classList.add("active");
  });
  const doneRow = overlay.querySelector(`.step-row[data-stage="${stage}"]`);
  if (doneRow) doneRow.querySelector(".step-dot").innerHTML = "";
  const detailEl = overlay.querySelector(`[data-stage-detail="${stage}"]`);
  if (detailEl) detailEl.textContent = detail || "";
  if (idx === STAGE_ORDER.length - 1) {
    setTimeout(() => {
      const row = overlay.querySelector(`.step-row[data-stage="scoring"]`);
      if (row) { row.classList.remove("active"); row.classList.add("done"); }
    }, 250);
  }
}
function hideStepper() {
  const overlay = document.getElementById("stepperOverlay");
  if (overlay) overlay.classList.remove("show");
}

function renderReport(body, ctx, caseRow, report) {
  const decision = report.decision;
  const badge = ACTION_BADGE[decision.action] || ACTION_BADGE.manual_review;
  const isLiveData = (report.data_source || "").startsWith("offline") === false;
  const dataBadge = isLiveData
    ? `<span class="mode-flag live">● LIVE DATA <span class="mono" style="opacity:.75">· ${report.data_source}</span></span>`
    : `<span class="mode-flag cached">◆ OFFLINE DEMO <span class="mono" style="opacity:.75">· ${report.data_source || "offline-fixture"}</span></span>`;
  const health = api.getApiHealth();

  body.innerHTML = `
    <div class="wallet-strip">
      <span class="mono">${caseRow.suspect_wallet}</span>
      <span class="chain-badge">${caseRow.chain}</span>
      ${dataBadge}
      <span class="spacer"></span>
      ${health.responseMs != null ? `<span class="api-health mono" title="Last API response time">${health.responseMs}ms</span>` : ""}
      ${health.lastSyncAt ? `<span class="api-health" title="Last synchronised">synced ${new Date(health.lastSyncAt).toLocaleTimeString()}</span>` : ""}
      <button class="btn-secondary btn-sm" id="btnRerun">Re-run trace</button>
    </div>

    <div class="trace-grid">
      <div>
        <div class="card graph-card">
          <div class="card-title">FUND FLOW - ${report.hops_traced} HOP${report.hops_traced === 1 ? "" : "S"} TRACED</div>
          ${renderFundFlowSVG(report)}
        </div>

        ${renderGeoTrail(report.geo_trail)}

        ${report.sanctions_match ? `
          <div class="sanctions-banner">
            <div class="sanctions-banner-icon">⚠</div>
            <div>
              <div class="sanctions-banner-title">OFAC SDN LIST MATCH - ${report.sanctions_match.entity_name}</div>
              <div class="sanctions-banner-sub">
                Programs: <span class="mono">${report.sanctions_match.programs.join(", ")}</span> ·
                Listed ${report.sanctions_match.date_listed} ·
                <span class="mono">${report.sanctions_match.address}</span>
              </div>
              <div class="sanctions-banner-note">Real, first-party U.S. Treasury designation - not a heuristic. See attribution tier below.</div>
            </div>
          </div>
        ` : ""}

        <div class="attribution-card">
          <span class="action-badge ${badge.cls}">${badge.label}</span>
          <div class="head">
            <div class="name">${report.sanctions_match ? `OFAC-sanctioned entity - ${report.sanctions_match.entity_name}` : (report.exchange_match ? `Exchange match - ${report.exchange_match.exchange}` : (report.mixer_hit ? "Trail blocked at mixer" : "No pattern match"))}</div>
            <div class="conf">${Math.round(report.confidence * 100)}% confidence</div>
          </div>
          <div class="desc">${decision.rationale}</div>
          <div class="action-row">
            ${decision.notice_type ? `<button class="btn-primary" id="btnIssueNotice">Issue ${decision.action === "suggest_freeze" ? "freeze" : "KYC-disclosure"} notice</button>` : ""}
            <button class="btn-secondary" id="btnExport">Export evidence pack</button>
          </div>
        </div>

        <div class="card copilot-card" style="margin-top:var(--sp-4);">
          <div class="card-title">INVESTIGATION COPILOT</div>
          <div class="copilot-headline">
            <span class="conf-pill conf-${(report.investigation_brief?.confidence_label || "low").toLowerCase()}">${report.investigation_brief?.confidence_label || " - "}</span>
            <span>${report.investigation_brief?.headline || ""}</span>
          </div>

          ${(report.risk_patterns || []).length ? `
            <div class="risk-pattern-row">
              ${report.risk_patterns.map((p) => `
                <span class="risk-chip risk-${p.severity}" title="${p.evidence.replace(/"/g, "&quot;")}">${p.label}</span>
              `).join("")}
            </div>
          ` : `<div style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-faint);margin-bottom:10px;">No advanced risk patterns (rapid transfers / layering / structuring / high fan-out) detected on this trail.</div>`}

          <div class="copilot-section-label">Why this wallet is flagged - ranked by evidence</div>
          ${(report.investigation_brief?.why_suspicious || []).map((w) => `
            <div class="copilot-evidence-row">
              <div class="sig">${w.signal}</div>
              <div class="ev mono">${w.evidence}</div>
            </div>
          `).join("") || `<div style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-faint);">No scored evidence available.</div>`}

          <div class="copilot-section-label">Recommended next steps</div>
          ${(report.investigation_brief?.next_steps || []).map((s, i) => `
            <div class="copilot-step-row">
              <div class="n">${i + 1}</div>
              <div><div class="step">${s.step}</div><div class="why">${s.why}</div></div>
            </div>
          `).join("") || `<div style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-faint);">No next steps generated.</div>`}
        </div>

        <div class="card" style="margin-top:var(--sp-4);">
          <div class="card-title">ATTRIBUTION CONFIDENCE - FORMULA</div>
          <div class="formula-line">confidence = σ(w₁·DF + w₂·SR + w₃·SDZ + w₄·(1−MP) + w₅·AI⁻¹ + bias)</div>
          ${report.confidence_breakdown.map((f) => `
            <div class="factor-row">
              <div class="factor-name">${f.factor} <span style="color:var(--text-faint)">(w=${f.weight})</span></div>
              <div class="factor-value">${f.value} → ${f.contribution >= 0 ? "+" : ""}${f.contribution}</div>
              <div class="factor-bar-track"><div class="factor-bar-fill" style="width:${Math.min(100, Math.max(2, Math.abs(f.contribution) * 22))}%"></div></div>
            </div>
          `).join("")}
          <div style="margin-top:10px;font-size:calc(11px * var(--fs-scale, 1));color:var(--text-faint);">
            AI illicit-probability classifier: AUROC ${report.ai_model_metrics.auroc} on held-out data
            (${report.ai_model_metrics.trained_on}).
          </div>
        </div>

        <div class="card" style="margin-top:var(--sp-4);">
          <div class="card-title">AI RISK ENGINE - WHY THIS PREDICTION</div>
          <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">
            <span style="font-family:var(--font-serif);font-size:var(--fs-2xl);color:var(--copper);">${Math.round(report.ai_illicit_probability * 100)}%</span>
            <span style="font-size:calc(11px * var(--fs-scale, 1));color:var(--text-faint);">illicit-probability score (not a black box - reasons below)</span>
          </div>
          ${(report.ai_explanation || []).length ? `
          <div class="shap-chart">
            ${(() => {
              const items = report.ai_explanation;
              const maxMag = Math.max(...items.map((r) => Math.abs(r.magnitude)), 0.001);
              return items.map((r) => {
                const pct = Math.min(48, (Math.abs(r.magnitude) / maxMag) * 48);
                const isUp = r.direction === "+";
                return `
                  <div class="shap-row">
                    <div class="shap-label" title="${r.reason}">${r.reason}</div>
                    <div class="shap-track">
                      <div class="shap-zero"></div>
                      ${isUp
                        ? `<div class="shap-bar up" style="width:${pct}%;left:50%;"></div>`
                        : `<div class="shap-bar down" style="width:${pct}%;right:50%;"></div>`}
                    </div>
                    <div class="shap-mag mono ${isUp ? "up" : "down"}">${isUp ? "+" : "−"}${Math.abs(r.magnitude)}</div>
                  </div>
                `;
              }).join("");
            })()}
            <div class="shap-axis"><span>← reduces risk</span><span>increases risk →</span></div>
          </div>
          ` : ""}
          ${(report.ai_explanation || []).map((r) => `
            <div class="ai-reason ${r.direction === "+" ? "up" : "down"}">
              <span class="ai-reason-sign">${r.direction}</span>
              <span>${r.reason}</span>
              <span class="ai-reason-mag mono">${r.magnitude}</span>
            </div>
          `).join("") || `<div style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-faint);">No AI explanation available for this trace.</div>`}
        </div>
      </div>

      <div class="card">
        <div class="card-title">ATTRIBUTION LEDGER</div>
        ${report.ledger.map((e) => `
          <div class="ledger-entry">
            <div class="ledger-mark ${e.mark}">${e.mark === "check" ? "✓" : e.mark === "flag" ? "!" : "i"}</div>
            <div><div class="ledger-text">${e.text}</div><div class="ledger-sub">${e.sub || ""}</div></div>
          </div>
        `).join("") || `<div style="font-size:calc(12.5px * var(--fs-scale, 1));color:var(--text-faint);">No findings.</div>`}
      </div>
    </div>
  `;

  body.querySelector("#btnRerun").addEventListener("click", () => runTraceFlow(body.closest(".view") || document, ctx, caseRow));
  mountGraphInteractions(body, report);
  const noticeBtn = body.querySelector("#btnIssueNotice");
  if (noticeBtn) noticeBtn.addEventListener("click", () => ctx.openNoticeModal(caseRow, report, decision));
  body.querySelector("#btnExport").addEventListener("click", async () => {
    const filename = `${caseRow.ncrp_ref}-evidence-${report.report_hash.slice(0, 8)}.pdf`;
    try {
      if (api.getMode() !== "live") throw new Error("offline");
      await api.downloadEvidencePdf(caseRow.id, filename);
      toast("Evidence PDF downloaded.", "success");
    } catch {
      // Cached-mode / no live backend: fall back to the raw JSON pack so
      // export still works, just without the rendered PDF layout.
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${caseRow.ncrp_ref}-evidence-${report.report_hash.slice(0, 8)}.json`;
      a.click();
      toast("Live backend unavailable - downloaded JSON evidence pack instead.", "info", 3600);
    }
  });
}
