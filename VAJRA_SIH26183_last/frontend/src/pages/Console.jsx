import React, { useEffect, useRef, useState, useCallback } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import * as api from "../console-core/api.js";
import { ICONS } from "../console-core/icons.js";
import { initials, shortAddr } from "../console-core/format.js";
import { toast } from "../console-core/components/toast.js";
import { openNoticeModal, openNoticeTextModal } from "../console-core/components/noticeModal.js";
import Dashboard from "../components/Dashboard.jsx";
import ReportsQueue from "../components/ReportsQueue.jsx";
import { useTheme, toggleTheme } from "../lib/prefs.js";

import { renderTrace } from "../console-core/views/trace.js";
import { renderNotices } from "../console-core/views/notices.js";
import { renderExchanges } from "../console-core/views/exchanges.js";
import { renderNetwork } from "../console-core/views/network.js";
import { renderSyndicates } from "../console-core/views/syndicates.js";
import { renderVault } from "../console-core/views/vault.js";
import { renderAudit } from "../console-core/views/audit.js";
import { renderAbout } from "../console-core/views/about.js";

const VIEW_RENDERERS = {
  trace: renderTrace, notices: renderNotices,
  exchanges: renderExchanges, network: renderNetwork, syndicates: renderSyndicates,
  vault: renderVault, audit: renderAudit, about: renderAbout,
};

const NAV_ITEMS = [
  { view: "dashboard", icon: "dashboard", label: "Dashboard" },
  { view: "reports", icon: "reports", label: "Citizen reports" },
  { view: "trace", icon: "trace", label: "Trace" },
  { view: "notices", icon: "notices", label: "Notices" },
  { view: "exchanges", icon: "exchange", label: "Exchange risk board" },
  { view: "network", icon: "network", label: "Case network" },
  { view: "syndicates", icon: "syndicate", label: "Syndicate score" },
  { view: "vault", icon: "vault", label: "Evidence vault" },
  { view: "audit", icon: "audit", label: "Audit log", adminOnly: true },
  { view: "about", icon: "about", label: "About this build" },
];
const BOTTOM_NAV_ITEMS = [
  { view: "dashboard", icon: "dashboard", label: "Home" },
  { view: "reports", icon: "reports", label: "Reports" },
  { view: "trace", icon: "trace", label: "Trace" },
  { view: "notices", icon: "notices", label: "Notices" },
];

export default function Console() {
  const { officer, logout } = useAuth();
  const [view, setView] = useState("dashboard");
  const [cases, setCases] = useState([]);
  const [activeCaseId, setActiveCaseId] = useState(null);
  const [highRisk, setHighRisk] = useState(0);
  const [mode, setMode] = useState(api.getMode());
  const [showNotif, setShowNotif] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const notifRef = useRef(null);

  const viewContainerRef = useRef(null);
  const liveRefreshHandlers = useRef({});
  const stateRef = useRef({ view, cases, activeCaseId });
  stateRef.current = { view, cases, activeCaseId };

  const navigate = useCallback((v) => {
    document.getElementById("stepperOverlay")?.classList.remove("show");
    document.getElementById("modalVeil")?.classList.remove("show");
    setShowMore(false);
    setView(v);
    document.getElementById("mainContent")?.scrollTo?.({ top: 0 });
  }, []);

  const openCase = useCallback((caseId) => {
    setActiveCaseId(caseId);
    setView("trace");
  }, []);

  const ctx = {
    get officer() { return officer; },
    get state() { return stateRef.current; },
    navigate,
    openCase,
    setCases: (c) => setCases(c),
    openNoticeModal: (caseRow, report, decision) => openNoticeModal(caseRow, report, decision, ctx),
    openNoticeText: (notice) => openNoticeTextModal(notice),
    registerLiveRefresh: (v, cb) => { liveRefreshHandlers.current[v] = cb; },
  };

  const loadQueue = useCallback(async () => {
    try {
      const list = await api.listCases();
      setCases(list);
      setHighRisk(list.filter((c) => c.risk_band === "high").length);
    } catch (e) {
      toast(e.message || "Couldn't load the case queue.", "error");
    }
  }, []);

  useEffect(() => { loadQueue(); }, [loadQueue]);
  useEffect(() => { setMode(api.getMode()); }, [view]);

  useEffect(() => {
    if (view !== "dashboard" && view !== "reports" && viewContainerRef.current) {
      const container = viewContainerRef.current;
      const renderedFor = view;
      container.innerHTML = "";
      Promise.resolve(VIEW_RENDERERS[view]?.(container, ctx)).then(() => {
        const stillCurrent = stateRef.current.view === renderedFor && viewContainerRef.current === container;
        if (!stillCurrent) container.innerHTML = "";
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, activeCaseId]);

  useEffect(() => {
    const handle = api.subscribeAlerts({
      onAlert: (event, data) => {
        if (event === "high_risk_case") {
          toast(`High-risk case flagged: ${data.ncrp_ref}${data.exchange ? ` → ${data.exchange}` : ""}`, "warn");
        } else if (event === "exchange_match") {
          toast(`Exchange match: ${data.ncrp_ref} linked to ${data.exchange}`, "info");
        }
        loadQueue();
        const current = stateRef.current.view;
        if (liveRefreshHandlers.current[current]) liveRefreshHandlers.current[current]();
      },
    });
    return () => handle.cancel();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadQueue]);

  const theme = useTheme();
  const activeCase = cases.find((c) => c.id === activeCaseId);
  const highRiskCases = cases.filter((c) => c.risk_band === "high");

  useEffect(() => {
    if (!showNotif) return;
    const onDocClick = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotif(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [showNotif]);

  return (
    <div id="app" className="active">
      <div className="gov-strip" aria-hidden="true"></div>
      <header className="topbar">
        <div className="brandmark">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="1.4"><path d="M12 2l7 3v6c0 5-3.2 8.4-7 11-3.8-2.6-7-6-7-11V5l7-3z"/><path d="M9 12l2 2 4-4"/></svg>
          <span className="brandmark-name">VAJRA</span>
          <span className="gov-badge"><span dangerouslySetInnerHTML={{ __html: ICONS.chakra }} />Govt. of India</span>
        </div>
        <span className={`tb-mode ${mode === "live" ? "live" : "cached"}`}>{mode === "live" ? "Live" : "Offline"}</span>
        {activeCase && <span className="tb-case">{activeCase.ncrp_ref}</span>}
        <div className="tb-spacer"></div>
        <button className="tb-icon-btn" title="Switch theme" aria-label="Toggle dark mode" onClick={toggleTheme}>
          {theme === "dark"
            ? <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><circle cx="10" cy="10" r="3.4"/><path d="M10 2.5v2M10 15.5v2M17.5 10h-2M4.5 10h-2M15.3 4.7l-1.4 1.4M6.1 13.9l-1.4 1.4M15.3 15.3l-1.4-1.4M6.1 6.1L4.7 4.7"/></svg>
            : <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"><path d="M17 11.2A7 7 0 1 1 8.8 3 5.6 5.6 0 0 0 17 11.2z"/></svg>}
        </button>
        <div ref={notifRef} style={{ position: "relative" }}>
          <button className="tb-icon-btn" title="High-risk flags" aria-label={highRisk > 0 ? `Notifications: ${highRisk} high-risk flags` : "Notifications"} onClick={() => setShowNotif((s) => !s)}>
            <span dangerouslySetInnerHTML={{ __html: ICONS.bell }} />
            {highRisk > 0 && <span className="tb-badge"></span>}
          </button>
          {showNotif && (
            <div className="notif-pop" style={{
              position: "absolute", top: "calc(100% + 8px)", right: 0, width: 300, maxHeight: 360, overflowY: "auto",
              background: "var(--ink-2, #12203a)", border: "1px solid var(--glass-border, rgba(255,255,255,.14))",
              borderRadius: "var(--r-lg, 10px)", boxShadow: "var(--shadow-lg, 0 10px 30px rgba(0,0,0,.4))", zIndex: 80,
            }}>
              <div style={{ padding: "10px 14px", fontSize: 12, fontWeight: 700, letterSpacing: ".04em", opacity: 0.7, borderBottom: "1px solid var(--glass-border, rgba(255,255,255,.1))" }}>
                {highRisk > 0 ? `${highRisk} HIGH-RISK CASE${highRisk > 1 ? "S" : ""}` : "NOTIFICATIONS"}
              </div>
              {highRiskCases.length === 0 ? (
                <div style={{ padding: "16px 14px", fontSize: 13, opacity: 0.6 }}>No high-risk flags right now.</div>
              ) : (
                highRiskCases.slice(0, 8).map((c) => (
                  <button key={c.id} onClick={() => { setShowNotif(false); openCase(c.id); }} style={{
                    display: "block", width: "100%", textAlign: "left", padding: "10px 14px", background: "none",
                    border: "none", borderBottom: "1px solid var(--glass-border, rgba(255,255,255,.06))", cursor: "pointer",
                    color: "inherit", font: "inherit",
                  }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{c.ncrp_ref}</div>
                    <div style={{ fontSize: 12, opacity: 0.6, fontFamily: "var(--font-mono)" }}>{shortAddr(c.suspect_wallet)}</div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
        <div className="tb-officer">
          <div className="tb-avatar">{initials(officer.name)}</div>
          <div className="tb-officer-text"><span className="tb-officer-name">{officer.name}</span><span className="tb-officer-role">{officer.role}</span></div>
        </div>
        <button className="tb-logout" onClick={async () => { await logout(); }}>Sign out</button>
      </header>

      {mode !== "live" && (
        <div className="offline-banner show">
          <span dangerouslySetInnerHTML={{ __html: ICONS.wifiOff }} />
          Backend unreachable - start the FastAPI server (<code>uvicorn main:app</code>) to reconnect.
        </div>
      )}

      <div className="shell">
        <nav className="sidebar" aria-label="Primary">
          <div className="nav-group-label">Console</div>
          {NAV_ITEMS.filter((n) => !n.adminOnly || officer.role === "admin").map((n) => (
            <button key={n.view} className={`nav-item ${view === n.view ? "active" : ""}`} onClick={() => navigate(n.view)}>
              <span dangerouslySetInnerHTML={{ __html: ICONS[n.icon] }} />{n.label}
            </button>
          ))}

          <div className="sidebar-divider"></div>
          <div className="nav-group-label">Case queue</div>
          <div className="queue-list">
            {cases.slice(0, 8).map((c) => (
              <button key={c.id} className={`queue-item ${activeCaseId === c.id ? "active" : ""}`} onClick={() => openCase(c.id)}>
                <div className="queue-id">{c.ncrp_ref}</div>
                <div className="queue-meta">
                  <span className="queue-risk-dot" style={{ background: c.risk_band === "high" ? "var(--risk-high)" : c.risk_band === "medium" ? "var(--risk-med)" : "var(--risk-low)" }}></span>
                  <span className="queue-wallet">{shortAddr(c.suspect_wallet)}</span>
                </div>
              </button>
            ))}
          </div>

          <div className="sidebar-foot">VAJRA console<br/>{officer.jurisdiction}</div>
        </nav>

        <main className="main" id="mainContent" tabIndex={-1}>
          <div className="main-body">
            {view === "dashboard" ? (
              <div className="view active" key="dashboard-view">
                <Dashboard
                  officer={officer}
                  navigate={navigate}
                  openCase={openCase}
                  setCases={setCases}
                  registerLiveRefresh={(v, cb) => { liveRefreshHandlers.current[v] = cb; }}
                />
              </div>
            ) : view === "reports" ? (
              <div className="view active" key="reports-view">
                <ReportsQueue openCase={openCase} onClaimed={loadQueue} />
              </div>
            ) : (
              <div className="view active" key="legacy-view" ref={viewContainerRef}></div>
            )}
          </div>
        </main>
      </div>

      {showMore && <div className="more-veil" onClick={() => setShowMore(false)} aria-hidden="true"></div>}
      {showMore && (
        <div className="more-sheet" role="dialog" aria-label="All sections">
          <div className="more-grip" aria-hidden="true"></div>
          <button className="more-close" aria-label="Close" onClick={() => setShowMore(false)}>
            <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M5 5l10 10M15 5L5 15"/></svg>
          </button>
          <div className="more-grid">
            {NAV_ITEMS.filter((n) => !n.adminOnly || officer.role === "admin").map((n) => (
              <button key={n.view} className={`more-item ${view === n.view ? "active" : ""}`} onClick={() => navigate(n.view)}>
                <span dangerouslySetInnerHTML={{ __html: ICONS[n.icon] }} />{n.label}
              </button>
            ))}
          </div>
          {cases.length > 0 && (
            <>
              <div className="more-label">Case queue</div>
              <div className="more-queue">
                {cases.slice(0, 8).map((c) => (
                  <button key={c.id} className="more-case" onClick={() => { setShowMore(false); openCase(c.id); }}>
                    <span className="queue-risk-dot" style={{ background: c.risk_band === "high" ? "var(--risk-high)" : c.risk_band === "medium" ? "var(--risk-med)" : "var(--risk-low)" }}></span>
                    <span className="queue-id">{c.ncrp_ref}</span>
                    <span className="queue-wallet">{shortAddr(c.suspect_wallet)}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
      <nav className="bottom-nav" aria-label="Primary mobile">
        {BOTTOM_NAV_ITEMS.map((n) => (
          <button key={n.view} className={`bn-item ${view === n.view ? "active" : ""}`} onClick={() => navigate(n.view)}>
            <span dangerouslySetInnerHTML={{ __html: ICONS[n.icon] }} />{n.label}
          </button>
        ))}
        <button className={`bn-item ${showMore || !BOTTOM_NAV_ITEMS.some((n) => n.view === view) ? "active" : ""}`} onClick={() => setShowMore((m) => !m)} aria-expanded={showMore}>
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><circle cx="4.5" cy="10" r="1.3"/><circle cx="10" cy="10" r="1.3"/><circle cx="15.5" cy="10" r="1.3"/></svg>More
        </button>
      </nav>
    </div>
  );
}
