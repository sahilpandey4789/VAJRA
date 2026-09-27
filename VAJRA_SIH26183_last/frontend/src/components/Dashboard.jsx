import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import * as api from "../console-core/api.js";
import { riskChip as riskChipHtml, statusLabel, relativeTime, chainLabel, shortAddr } from "../console-core/format.js";
import { toast } from "../console-core/components/toast.js";

/*
 * Real React version of the old console-core/views/dashboard.js (which built
 * this whole screen by hand-writing innerHTML strings into a mounted
 * div). Behaviour and CSS classes are kept identical on purpose - this
 * is a rewrite of the *implementation*, not a redesign - so it drops
 * into Console.jsx with no visual change, but is now a real controlled
 * React component: state lives in useState, not in the DOM.
 */

function RiskChip({ band, confidence }) {
  // riskChip() already returns a small trusted HTML string built from a
  // closed set of band/percentage values (no user-supplied text), so
  // reusing it via dangerouslySetInnerHTML here is safe and keeps the
  // exact same markup/CSS class the rest of the app already styles.
  return <span dangerouslySetInnerHTML={{ __html: riskChipHtml(band, confidence) }} />;
}

function StatCard({ label, value, delta, deltaClass, valueClass, delay }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), delay || 0);
    return () => clearTimeout(t);
  }, [delay]);
  return (
    <div className={`stat-card${mounted ? " count-in" : ""}`} style={{ animationDelay: `${delay || 0}ms` }}>
      <div className="stat-label">{label}</div>
      <div className={`stat-value${valueClass ? ` ${valueClass}` : ""}`}>{value}</div>
      <div className={`stat-delta${deltaClass ? ` ${deltaClass}` : ""}`}>{delta}</div>
    </div>
  );
}

// Same signal palette the rest of the console already uses for these three
// chains (see mapStyle.js / theme tokens) - the chart reads as part of the
// product instead of a generic library default.
const CHAIN_COLORS = { BITCOIN: "var(--brass)", ETHEREUM: "var(--copper)", TRON: "var(--violet)" };

function ChainDistributionChart({ chainDist }) {
  const data = Object.entries(chainDist).map(([chain, count]) => ({
    name: chainLabel(chain), chain, value: count,
  }));
  if (data.length === 0) {
    return <div style={{ fontSize: "calc(12px * var(--fs-scale, 1))", color: "var(--text-faint)" }}>No cases yet.</div>;
  }
  return (
    <div style={{ width: "100%", height: 190 }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={44} outerRadius={68} paddingAngle={3} stroke="none">
            {data.map((d) => <Cell key={d.chain} fill={CHAIN_COLORS[d.chain] || "var(--slate)"} />)}
          </Pie>
          <Tooltip
            contentStyle={{ background: "var(--panel)", border: "1px solid var(--line-strong)", borderRadius: 8, fontSize: "calc(12px * var(--fs-scale, 1))" }}
            labelStyle={{ color: "var(--text)" }}
          />
          <Legend wrapperStyle={{ fontSize: "calc(12px * var(--fs-scale, 1))", color: "var(--text-soft)" }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

const URGENCY_DOT = { critical: "var(--risk-high)", high: "var(--risk-med)", medium: "var(--slate)", low: "var(--text-faint)" };

function PriorityQueue({ queue, openCase }) {
  if (!queue) {
    return (
      <div className="card priority-queue-card">
        <div className="card-title">Priority queue</div>
        <div className="skel" style={{ height: 16, marginBottom: 8 }} />
        <div className="skel" style={{ height: 16, width: "80%" }} />
      </div>
    );
  }
  return (
    <div className="card priority-queue-card">
      <div className="card-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span>Priority queue</span>
        <span style={{ fontSize: "calc(11px * var(--fs-scale, 1))", color: "var(--text-faint)", fontWeight: 500 }}>which case first, and why</span>
      </div>
      {queue.length === 0 ? (
        <div style={{ fontSize: "calc(12px * var(--fs-scale, 1))", color: "var(--text-faint)" }}>No open cases need attention right now.</div>
      ) : (
        queue.map((q, i) => (
          <div
            key={q.case_id}
            className="priority-row"
            onClick={() => openCase(q.case_id)}
            style={{
              display: "flex", gap: 10, alignItems: "flex-start", padding: "10px 0",
              borderTop: i === 0 ? "none" : "1px solid var(--line-soft)", cursor: "pointer",
            }}
          >
            <span style={{
              flexShrink: 0, marginTop: 5, width: 8, height: 8, borderRadius: "50%",
              background: URGENCY_DOT[q.urgency] || "var(--text-faint)",
              boxShadow: q.urgency === "critical" ? `0 0 8px ${URGENCY_DOT.critical}` : "none",
            }} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span className="mono" style={{ fontSize: "calc(12.5px * var(--fs-scale, 1))", fontWeight: 600 }}>{q.ncrp_ref}</span>
                <span style={{ fontSize: "calc(11px * var(--fs-scale, 1))", fontFamily: "var(--font-mono)", color: URGENCY_DOT[q.urgency], fontWeight: 700 }}>
                  {q.score}
                </span>
              </div>
              <div style={{ fontSize: "calc(11.5px * var(--fs-scale, 1))", color: "var(--text-soft)", marginTop: 2, lineHeight: 1.4 }}>
                {q.reasons?.[0] || " - "}
                {q.reasons?.[1] ? ` · ${q.reasons[1]}` : ""}
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default function Dashboard({ officer, navigate, openCase, setCases, registerLiveRefresh }) {
  const [stats, setStats] = useState(null);
  const [cases, setLocalCases] = useState(null);
  const [exchanges, setExchanges] = useState(null);
  const [priorityQueue, setPriorityQueue] = useState(null);
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("");

  const load = useCallback(async () => {
    try {
      const [s, c, e, pq] = await Promise.all([
        api.getStats(), api.listCases(), api.getExchangeRiskBoard(), api.getPriorityQueue(5),
      ]);
      setStats(s);
      setLocalCases(c);
      setExchanges(e);
      setPriorityQueue(pq);
      setCases(c); // keep the sidebar queue / bell badge in sync, same as before
    } catch (err) {
      toast(err.message || "Couldn't load the dashboard.", "error");
    }
  }, [setCases]);

  useEffect(() => { load(); }, [load]);

  // same real-time-alert hook the legacy view registered with Console
  useEffect(() => {
    registerLiveRefresh?.("dashboard", load);
    return () => registerLiveRefresh?.("dashboard", null);
  }, [registerLiveRefresh, load]);

  const filteredCases = useMemo(() => {
    if (!cases) return [];
    const q = search.trim().toLowerCase();
    return cases.filter((c) => {
      const matchesQuery = !q || c.ncrp_ref.toLowerCase().includes(q) || c.suspect_wallet.toLowerCase().includes(q);
      const matchesRisk = !riskFilter || c.risk_band === riskFilter;
      return matchesQuery && matchesRisk;
    });
  }, [cases, search, riskFilter]);

  const topExchange = exchanges?.[0];
  const chainDist = stats?.blockchain_distribution || {};
  const alerts = stats?.recent_alerts || [];

  return (
    <>
      <div className="view-head">
        <div>
          <div className="view-title">Case overview</div>
          <div className="view-sub">
            {officer.jurisdiction} &middot; {new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}
          </div>
        </div>
        <button className="btn-primary" onClick={() => navigate("trace")}>+ New trace</button>
      </div>

      <div className="hero-signal">
        {!exchanges ? (
          <div className="skel" style={{ height: 64, width: "100%" }} />
        ) : topExchange ? (
          <>
            <div className="hero-signal-main">
              <div className="hero-signal-label">Fraud-linked exchanges identified in your jurisdiction</div>
              <div className="hero-signal-value">{exchanges.length}</div>
              <div className="hero-signal-sub">
                Top repeat offender: <strong>{topExchange.exchange}</strong> - linked to {topExchange.linked_cases} complaint{topExchange.linked_cases === 1 ? "" : "s"}, {Math.round(topExchange.avg_confidence * 100)}% avg. confidence
              </div>
            </div>
            <button className="btn-secondary" onClick={() => navigate("exchanges")}>View exchange risk board →</button>
          </>
        ) : (
          <>
            <div className="hero-signal-main">
              <div className="hero-signal-label">Exchange risk board</div>
              <div className="hero-signal-value" style={{ fontSize: "var(--fs-lg)" }}>No exchange matches yet</div>
              <div className="hero-signal-sub">Every trace whose fund flow reaches a known exchange wallet will appear here, ranked across all complaints.</div>
            </div>
            <button className="btn-secondary" onClick={() => navigate("exchanges")}>Open board →</button>
          </>
        )}
      </div>

      <PriorityQueue queue={priorityQueue} openCase={openCase} />

      <div className="stat-row">
        {!stats
          ? Array.from({ length: 9 }).map((_, i) => (
              <div className="stat-card" key={i}>
                <div className="skel" style={{ height: 11, width: "60%", marginBottom: 10 }} />
                <div className="skel" style={{ height: 26, width: "40%" }} />
              </div>
            ))
          : [
              { label: "Active cases", value: stats.open_cases, delta: `across ${officer.jurisdiction.split(" - ")[1]?.trim() || "jurisdiction"}` },
              { label: "Funds traced", value: Number(stats.funds_traced || 0).toFixed(2), delta: "native units, all chains" },
              { label: "High-risk cases", value: stats.high_risk_flags, delta: "needs review", deltaClass: "warn", valueClass: "copper" },
              { label: "Pending approvals", value: stats.pending_approvals ?? 0, delta: "maker-checker queue" },
              { label: "Exchange requests", value: stats.exchange_requests ?? 0, delta: "KYC-disclosure notices" },
              { label: "Avg. trace time", value: `${stats.avg_trace_minutes} min`, delta: `was ${stats.manual_baseline_hours} hrs manual` },
              { label: "Today's activity", value: stats.today_activity ?? 0, delta: "audit-logged actions" },
              { label: "Notices issued", value: stats.notices_issued_month, delta: "this month" },
            ].map((s, i) => <StatCard key={s.label} {...s} delay={i * 45} />)}
      </div>

      <div className="dash-grid">
        <div>
          <div className="card-title" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
            <span>Recent complaints</span>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <input
                type="text"
                placeholder="Search NCRP ref or wallet…"
                style={{ minWidth: 140, flex: 1 }}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
                <option value="">All risk</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>

          <div className="table-wrap responsive-table">
            <table className="case-table">
              <thead>
                <tr><th>Case ID</th><th>Suspect wallet</th><th>Chain</th><th>Reported</th><th>Risk</th><th>Status</th></tr>
              </thead>
              <tbody>
                {!cases ? (
                  <tr><td colSpan={6}><div className="skel" style={{ height: 16 }} /></td></tr>
                ) : filteredCases.length === 0 ? (
                  <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--text-faint)", padding: 32 }}>
                    {cases.length === 0 ? "No cases in queue." : "No cases match your search."}
                  </td></tr>
                ) : filteredCases.map((c) => (
                  <tr key={c.id} className="row-clickable" onClick={() => openCase(c.id)}>
                    <td className="mono">{c.ncrp_ref}</td>
                    <td className="case-wallet">{shortAddr(c.suspect_wallet)}</td>
                    <td>{chainLabel(c.chain)}</td>
                    <td>{relativeTime(c.reported_at)}</td>
                    <td><RiskChip band={c.risk_band} confidence={c.confidence} /></td>
                    <td className="status-pill">{statusLabel(c.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="case-cards">
            {(cases || []).length > 0 && filteredCases.map((c) => (
              <div className="case-card" key={c.id} onClick={() => openCase(c.id)}>
                <div className="case-card-top">
                  <span className="case-card-id mono">{c.ncrp_ref}</span>
                  <RiskChip band={c.risk_band} confidence={c.confidence} />
                </div>
                <div className="case-card-wallet">{shortAddr(c.suspect_wallet)} &middot; {chainLabel(c.chain)}</div>
                <div className="case-card-bottom">
                  <span className="status-pill">{statusLabel(c.status)}</span>
                  <span style={{ fontSize: "calc(11px * var(--fs-scale, 1))", color: "var(--text-faint)" }}>{relativeTime(c.reported_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Recent alerts</div>
          {!stats ? (
            <div className="skel" style={{ height: 16, marginBottom: 8 }} />
          ) : alerts.length === 0 ? (
            <div style={{ fontSize: "calc(12px * var(--fs-scale, 1))", color: "var(--text-faint)" }}>No high-risk alerts right now.</div>
          ) : (
            alerts.map((a) => (
              <div className="alert-row" key={a.id} onClick={() => openCase(a.id)}>
                <span className="alert-dot" />
                <div>
                  <div className="alert-title mono">{a.ncrp_ref}</div>
                  <div className="alert-sub">
                    {chainLabel(a.chain)} · {a.confidence != null ? `${Math.round(a.confidence * 100)}% confidence` : " - "} · {relativeTime(a.updated_at)}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="card">
          <div className="card-title">Cases by chain</div>
          {!stats ? <div className="skel" style={{ height: 190 }} /> : <ChainDistributionChart chainDist={chainDist} />}
        </div>
      </div>
    </>
  );
}
