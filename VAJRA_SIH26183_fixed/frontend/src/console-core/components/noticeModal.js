import * as api from "../api.js";
import { toast } from "./toast.js";

export function openNoticeModal(caseRow, report, decision, ctx) {
  const veil = document.getElementById("modalVeil");
  const defaultType = decision.notice_type || "freeze_102_crpc";

  veil.innerHTML = `
    <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="noticeModalTitle">
      <h3 id="noticeModalTitle">Draft legal notice</h3>
      <div class="modal-sub">${caseRow.ncrp_ref} · ${report.exchange_match ? report.exchange_match.exchange : "Unknown VASP"}</div>
      <div class="notice-type-grid" id="noticeTypeGrid">
        <button type="button" class="notice-type-opt ${defaultType === "freeze_102_crpc" ? "selected" : ""}" data-type="freeze_102_crpc">
          <div class="t">Freeze notice</div><div class="s">Section 102 CrPC / 106 BNSS</div>
        </button>
        <button type="button" class="notice-type-opt ${defaultType === "kyc_disclosure" ? "selected" : ""}" data-type="kyc_disclosure">
          <div class="t">KYC-disclosure request</div><div class="s">Section 94 BNSS / 79(3)(b) IT Act</div>
        </button>
      </div>
      <div id="noticeModalBody"><button class="btn-primary" id="btnDraft">Generate draft</button></div>
      <div class="modal-actions" style="margin-top:16px;">
        <button class="btn-secondary" id="btnCancel">Close</button>
      </div>
    </div>
  `;
  veil.classList.add("show");

  let selectedType = defaultType;
  veil.querySelectorAll(".notice-type-opt").forEach((opt) => {
    opt.addEventListener("click", () => {
      veil.querySelectorAll(".notice-type-opt").forEach((o) => o.classList.remove("selected"));
      opt.classList.add("selected");
      selectedType = opt.dataset.type;
    });
  });

  veil.querySelector("#btnCancel").addEventListener("click", () => veil.classList.remove("show"));
  veil.querySelector("#btnDraft").addEventListener("click", async () => {
    const bodyEl = veil.querySelector("#noticeModalBody");
    bodyEl.innerHTML = `<div class="skel" style="height:160px;border-radius:6px;"></div>`;
    try {
      const notice = await api.draftNotice(caseRow.id, selectedType);
      renderDraftedNotice(veil, notice, ctx);
      toast("Notice drafted.", "success");
    } catch (e) {
      bodyEl.innerHTML = `<div class="approval-banner pending">${e.message}</div><button class="btn-primary" id="btnDraft2">Try again</button>`;
      const retry = bodyEl.querySelector("#btnDraft2");
      if (retry) retry.addEventListener("click", () => veil.querySelector("#btnDraft").click());
    }
  });
}

function renderDraftedNotice(veil, notice, ctx) {
  const bodyEl = veil.querySelector("#noticeModalBody");
  const banner = notice.status === "pending_approval"
    ? `<div class="approval-banner pending">Awaiting Supervisor approval before it can be sent (maker-checker).</div>`
    : notice.status === "approved"
      ? `<div class="approval-banner approved">Approved - ready to send.</div>`
      : `<div class="approval-banner sent">Sent via Sahyog Portal.</div>`;

  bodyEl.innerHTML = `
    ${banner}
    <div class="notice-doc" id="noticeDocText">${notice.body}</div>
    <div class="modal-actions">
      ${ctx.officer.role !== "officer" && notice.status === "pending_approval" ? `<button class="btn-primary" id="btnApprove">Approve</button>` : ""}
      ${notice.status === "approved" ? `<button class="btn-primary" id="btnSend">Send via Sahyog Portal</button>` : ""}
      <button class="btn-secondary" id="btnPrint">Print</button>
    </div>
  `;
  const approveBtn = bodyEl.querySelector("#btnApprove");
  if (approveBtn) approveBtn.addEventListener("click", async () => {
    try { const updated = await api.approveNotice(notice.id); toast("Approved.", "success"); renderDraftedNotice(veil, updated, ctx); }
    catch (e) { toast(e.message, "error"); }
  });
  const sendBtn = bodyEl.querySelector("#btnSend");
  if (sendBtn) sendBtn.addEventListener("click", async () => {
    try { const updated = await api.sendNotice(notice.id); toast("Notice sent via Sahyog Portal.", "success"); renderDraftedNotice(veil, updated, ctx); }
    catch (e) { toast(e.message, "error"); }
  });
  bodyEl.querySelector("#btnPrint").addEventListener("click", () => {
    let printArea = document.getElementById("printArea");
    if (!printArea) { printArea = document.createElement("div"); printArea.id = "printArea"; document.body.appendChild(printArea); }
    printArea.textContent = notice.body;
    window.print();
  });
}

export function openNoticeTextModal(notice) {
  const veil = document.getElementById("modalVeil");
  veil.innerHTML = `
    <div class="modal-box" role="dialog" aria-modal="true">
      <h3>Notice text</h3>
      <div class="modal-sub">${notice.exchange_name || " - "} &middot; ${notice.status.replace(/_/g, " ")}</div>
      <div class="notice-doc">${notice.body}</div>
      <div class="modal-actions"><button class="btn-secondary" id="btnClose">Close</button></div>
    </div>
  `;
  veil.classList.add("show");
  veil.querySelector("#btnClose").addEventListener("click", () => veil.classList.remove("show"));
}
