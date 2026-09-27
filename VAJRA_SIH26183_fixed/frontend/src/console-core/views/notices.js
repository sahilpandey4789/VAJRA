import * as api from "../api.js";
import { relativeTime } from "../format.js";
import { toast } from "../components/toast.js";

const STATUS_LABEL = {
  pending_approval: { cls: "pending", text: "Pending supervisor approval" },
  approved: { cls: "ok", text: "Approved - ready to send" },
  sent: { cls: "ok", text: "Sent via Sahyog Portal" },
  acknowledged: { cls: "ok", text: "Acknowledged by exchange" },
};

export async function renderNotices(container, ctx) {
  container.innerHTML = `
    <div class="view-head">
      <div><div class="view-title">Notices</div><div class="view-sub">Auto-drafted legal notices, maker-checker workflow.</div></div>
    </div>
    <div class="filter-row">
      <button class="filter-chip active" data-f="all">All</button>
      <button class="filter-chip" data-f="pending_approval">Pending approval</button>
      <button class="filter-chip" data-f="approved">Approved</button>
      <button class="filter-chip" data-f="sent">Sent</button>
    </div>
    <div id="noticeList"><div class="skel" style="height:80px;border-radius:8px;"></div></div>
  `;

  const notices = await api.listNotices();
  const cases = ctx.state.cases.length ? ctx.state.cases : await api.listCases();

  const draw = (filter) => {
    const list = filter === "all" ? notices : notices.filter((n) => n.status === filter);
    const listEl = container.querySelector("#noticeList");
    if (!list.length) {
      listEl.innerHTML = `<div class="empty-state"><div class="t">No notices here</div><div class="s">Notices you draft from a trace's decision card will show up here.</div></div>`;
      return;
    }
    listEl.innerHTML = list.map((n) => {
      const c = cases.find((cc) => cc.id === n.case_id);
      const st = STATUS_LABEL[n.status] || { cls: "pending", text: n.status };
      return `
        <div class="card" style="margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;">
            <div>
              <div style="font-family:var(--font-mono);font-size:calc(13px * var(--fs-scale, 1));">${c ? c.ncrp_ref : n.case_id}</div>
              <div style="font-size:calc(12px * var(--fs-scale, 1));color:var(--text-soft);margin-top:2px;">${n.notice_type === "freeze_102_crpc" ? "Freeze notice (102 CrPC / 106 BNSS)" : "KYC-disclosure request"} → ${n.exchange_name || " - "}</div>
            </div>
            <span class="status-pill ${st.cls}"><span class="status-dot"></span>${st.text}</span>
          </div>
          <div style="font-size:calc(11.5px * var(--fs-scale, 1));color:var(--text-faint);margin-top:8px;">Drafted ${relativeTime(n.created_at)}${n.sahyog_sla_due ? ` · SLA due ${relativeTime(n.sahyog_sla_due)}` : ""}</div>
          <div class="action-row" style="margin-top:10px;">
            ${n.status === "pending_approval" && ctx.officer.role !== "officer" ? `<button class="btn-primary btn-sm" data-approve="${n.id}">Approve</button>` : ""}
            ${n.status === "approved" ? `<button class="btn-primary btn-sm" data-send="${n.id}">Send via Sahyog Portal</button>` : ""}
            <button class="btn-secondary btn-sm" data-view="${n.id}">View full text</button>
          </div>
        </div>
      `;
    }).join("");

    listEl.querySelectorAll("[data-approve]").forEach((btn) => btn.addEventListener("click", async () => {
      try { await api.approveNotice(btn.dataset.approve); toast("Notice approved.", "success"); renderNotices(container, ctx); }
      catch (e) { toast(e.message, "error"); }
    }));
    listEl.querySelectorAll("[data-send]").forEach((btn) => btn.addEventListener("click", async () => {
      try { await api.sendNotice(btn.dataset.send); toast("Notice sent.", "success"); renderNotices(container, ctx); }
      catch (e) { toast(e.message, "error"); }
    }));
    listEl.querySelectorAll("[data-view]").forEach((btn) => btn.addEventListener("click", () => {
      const n = notices.find((x) => x.id === btn.dataset.view);
      ctx.openNoticeText(n);
    }));
  };

  draw("all");
  container.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      container.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      draw(chip.dataset.f);
    });
  });
}
