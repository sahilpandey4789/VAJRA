import React, { useState } from "react";
import * as api from "../console-core/api.js";
import { ICONS } from "../console-core/icons.js";

/*
 * Citizen-facing status tracker for a reference number handed back by
 * the Report flow. Deliberately no login: knowing the exact NCRP
 * reference is the access control (same pattern as a courier tracking
 * number) - see the docstring on GET /api/public/report/{ncrp_ref}/status.
 * Kept as its own standalone screen, same shell as Report.jsx, so the
 * citizen-facing surface reads as one consistent product.
 */

export default function Track({ onBack }) {
  const [ncrpRef, setNcrpRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (!ncrpRef.trim()) return;
    setErr("");
    setBusy(true);
    try {
      const data = await api.trackPublicReport(ncrpRef);
      setResult(data);
    } catch (e2) {
      setResult(null);
      setErr(e2.message || "Couldn't look that reference number up.");
    } finally {
      setBusy(false);
    }
  };

  const trackAnother = () => { setResult(null); setErr(""); setNcrpRef(""); };

  return (
    <div id="trackScreen" className="show">
      <div className="gov-strip" aria-hidden="true"></div>
      <div className="login-shell">
        <div className="login-aside">
          <div className="brandmark">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="1.4"><path d="M12 2l7 3v6c0 5-3.2 8.4-7 11-3.8-2.6-7-6-7-11V5l7-3z"/><path d="M9 12l2 2 4-4"/></svg>
            <div><div className="brandmark-name">VAJRA</div><div className="brandmark-sub">Virtual Asset Judicial Response &amp; Attribution</div></div>
          </div>
          <span className="gov-badge" style={{ marginTop: 4 }}><span dangerouslySetInnerHTML={{ __html: ICONS.chakra }} />Govt. of India</span>
          <div className="login-aside-copy">
            <h1>Track your<br/>report.</h1>
            <p>Enter the reference number you were given when you reported a
              suspect wallet, to see where your case stands - no account or
              sign-in needed.</p>
          </div>
          <div className="login-aside-foot">
            National Cyber-Crime Threat Analytics Unit<br/>
            <button type="button" className="back-to-site" onClick={onBack}>&larr; Back to overview</button>
          </div>
        </div>

        <div className="login-main">
          <div className="login-card">
            {!result && (
              <>
                <div className="title">Check your report status</div>
                <div className="sub">Reference numbers look like NCRP-2026-A1B2C3.</div>
                <div className={`login-error ${err ? "show" : ""}`}>{err}</div>
                <form onSubmit={submit}>
                  <div className="field">
                    <label htmlFor="tRef">Reference number</label>
                    <input id="tRef" type="text" placeholder="NCRP-2026-A1B2C3" required autoComplete="off" autoCapitalize="characters"
                           value={ncrpRef} onChange={(e) => setNcrpRef(e.target.value)} />
                  </div>
                  <button type="submit" className="login-submit" disabled={busy}>{busy ? "Looking up…" : "Track report"}</button>
                  <p className="demo-hint" style={{ marginTop: 12 }}>Haven't reported yet? <button type="button" className="back-to-site" style={{ display: "inline", padding: 0 }} onClick={onBack}>Go back to report a wallet</button></p>
                </form>
              </>
            )}

            {result && (
              <>
                <div className="title">{result.ncrp_ref}</div>
                <div className="sub">{result.chain} &middot; reported {new Date(result.reported_at).toLocaleDateString()}</div>

                <div style={{
                  border: "1px solid var(--line-strong)", borderRadius: 10, padding: 16, margin: "14px 0",
                  background: "var(--panel)",
                }}>
                  <div style={{ fontSize: "calc(11px * var(--fs-scale, 1))", color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: ".04em" }}>Current status</div>
                  <div style={{ fontSize: "calc(18px * var(--fs-scale, 1))", fontWeight: 700, color: "var(--copper)", marginTop: 4 }}>{result.status_label}</div>
                  <div style={{ fontSize: "calc(12.5px * var(--fs-scale, 1))", color: "var(--text-soft)", marginTop: 8 }}>{result.message}</div>
                </div>

                <div style={{ margin: "18px 0 20px" }}>
                  {result.stages.map((s, i) => {
                    const done = i < result.stage_index;
                    const active = i === result.stage_index;
                    return (
                      <div key={s.key} style={{ display: "flex", alignItems: "flex-start", gap: 10, minHeight: 34 }}>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                          <div style={{
                            width: 16, height: 16, borderRadius: "50%", flexShrink: 0,
                            background: done || active ? "var(--copper)" : "transparent",
                            border: `1.6px solid ${done || active ? "var(--copper)" : "var(--line-strong)"}`,
                          }} />
                          {i < result.stages.length - 1 && (
                            <div style={{ width: 2, flex: 1, minHeight: 14, background: done ? "var(--copper)" : "var(--line-strong)" }} />
                          )}
                        </div>
                        <div style={{
                          fontSize: "calc(13px * var(--fs-scale, 1))", paddingBottom: 14,
                          color: active ? "var(--text)" : done ? "var(--text-soft)" : "var(--text-faint)",
                          fontWeight: active ? 600 : 400,
                        }}>{s.label}</div>
                      </div>
                    );
                  })}
                </div>

                <button type="button" className="login-submit" onClick={trackAnother}>Track another reference number</button>
                <p className="demo-hint" style={{ marginTop: 12 }}><button type="button" className="back-to-site" style={{ display: "inline", padding: 0 }} onClick={onBack}>&larr; Back to overview</button></p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
