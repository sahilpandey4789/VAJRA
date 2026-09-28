import React, { useState } from "react";
import * as api from "../console-core/api.js";
import { ICONS } from "../console-core/icons.js";

/*
 * Citizen/victim intake - the literal "Victim-Reported Suspect Wallet
 * Addresses" flow the PS title names. Deliberately its own standalone
 * page, not routed through AuthContext/Console: a reporter account has
 * no case-list or officer visibility, so it must never become the
 * app's "officer" session. State (token/reporter) lives locally here
 * and is discarded when the citizen leaves the page - nothing is
 * persisted to sessionStorage, unlike the officer session.
 */

const CHAINS = [
  { value: "ETHEREUM", label: "Ethereum" },
  { value: "BITCOIN", label: "Bitcoin" },
  { value: "TRON", label: "Tron" },
];

export default function Report({ onBack }) {
  const [step, setStep] = useState("register"); // "register" | "report" | "done"
  const [session, setSession] = useState(null); // { token, reporter }

  // ---- step 1: register ----
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [password, setPassword] = useState("");
  const [regErr, setRegErr] = useState("");
  const [regBusy, setRegBusy] = useState(false);

  const submitRegister = async (e) => {
    e.preventDefault();
    setRegErr("");
    setRegBusy(true);
    try {
      const data = await api.registerReporter({ name: name.trim(), contact: contact.trim(), password });
      setSession({ token: data.access_token, reporter: data.reporter });
      setStep("report");
    } catch (err) {
      setRegErr(err.message || "Couldn't create the account.");
    } finally {
      setRegBusy(false);
    }
  };

  // ---- step 2: report ----
  const [wallet, setWallet] = useState("");
  const [chain, setChain] = useState("ETHEREUM");
  const [typology, setTypology] = useState("");
  const [incidentDate, setIncidentDate] = useState("");
  const [repErr, setRepErr] = useState("");
  const [repBusy, setRepBusy] = useState(false);
  const [result, setResult] = useState(null);

  const submitReport = async (e) => {
    e.preventDefault();
    setRepErr("");
    setRepBusy(true);
    try {
      const data = await api.submitPublicReport(session.token, {
        suspect_wallet: wallet.trim(),
        chain,
        typology: typology.trim() || undefined,
        incident_timestamp: incidentDate ? new Date(incidentDate).toISOString() : undefined,
      });
      setResult(data);
      setStep("done");
    } catch (err) {
      setRepErr(err.message || "Couldn't submit the report.");
    } finally {
      setRepBusy(false);
    }
  };

  const reportAnother = () => {
    setWallet(""); setChain("ETHEREUM"); setTypology(""); setIncidentDate("");
    setResult(null); setRepErr("");
    setStep("report");
  };

  return (
    <div id="reportScreen" className="show">
      <div className="gov-strip" aria-hidden="true"></div>
      <div className="login-shell">
        <div className="login-aside">
          <div className="brandmark">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="1.4"><path d="M12 2l7 3v6c0 5-3.2 8.4-7 11-3.8-2.6-7-6-7-11V5l7-3z"/><path d="M9 12l2 2 4-4"/></svg>
            <div><div className="brandmark-name">VAJRA</div><div className="brandmark-sub">Virtual Asset Judicial Response &amp; Attribution</div></div>
          </div>
          <span className="gov-badge" style={{ marginTop: 4 }}><span dangerouslySetInnerHTML={{ __html: ICONS.chakra }} />Govt. of India</span>
          <div className="login-aside-copy">
            <h1>Report a suspect<br/>wallet address.</h1>
            <p>If you've lost funds to a crypto scam or fraud, report the wallet
              address here. Your report goes straight into an officer's triage
              queue - no case details or investigator dashboard are exposed to
              you, only a reference number to track it.</p>
          </div>
          <div className="login-aside-foot">
            National Cyber-Crime Threat Analytics Unit<br/>
            <button type="button" className="back-to-site" onClick={onBack}>&larr; Back to overview</button>
          </div>
        </div>

        <div className="login-main">
        <div className="login-mobile-top">
          <button type="button" className="back-to-site" onClick={onBack}>&larr; Back</button>
          <div className="brandmark">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="1.4"><path d="M12 2l7 3v6c0 5-3.2 8.4-7 11-3.8-2.6-7-6-7-11V5l7-3z"/><path d="M9 12l2 2 4-4"/></svg>
            <span className="brandmark-name">VAJRA</span>
          </div>
        </div>
          <div className="login-card">
            {step === "register" && (
              <>
                <div className="title">Tell us who you are</div>
                <div className="sub">Step 1 of 2 &middot; used only to follow up on your report.</div>
                <div className={`login-error ${regErr ? "show" : ""}`}>{regErr}</div>
                <form onSubmit={submitRegister}>
                  <div className="field">
                    <label htmlFor="rName">Full name</label>
                    <input id="rName" type="text" placeholder="Your name" autoComplete="name" required
                           value={name} onChange={(e) => setName(e.target.value)} />
                  </div>
                  <div className="field">
                    <label htmlFor="rContact">Phone or email</label>
                    <input id="rContact" type="text" placeholder="you@example.com or 98xxxxxxxx" autoComplete="email" required
                           value={contact} onChange={(e) => setContact(e.target.value)} />
                  </div>
                  <div className="field">
                    <label htmlFor="rPassword">Set a password</label>
                    <input id="rPassword" type="password" placeholder="At least 8 characters" autoComplete="new-password" minLength={8} required
                           value={password} onChange={(e) => setPassword(e.target.value)} />
                  </div>
                  <button type="submit" className="login-submit" disabled={regBusy}>{regBusy ? "Creating account…" : "Continue"}</button>
                  <p className="demo-hint" style={{ marginTop: 12 }}>Are you an investigating officer? <button type="button" className="back-to-site" style={{ display: "inline", padding: 0 }} onClick={onBack}>Go to officer sign-in</button></p>
                </form>
              </>
            )}

            {step === "report" && (
              <>
                <div className="title">Report the suspect wallet</div>
                <div className="sub">Step 2 of 2 &middot; signed in as {session?.reporter?.name}.</div>
                <div className={`login-error ${repErr ? "show" : ""}`}>{repErr}</div>
                <form onSubmit={submitReport}>
                  <div className="field">
                    <label htmlFor="rChain">Blockchain</label>
                    <select id="rChain" required value={chain} onChange={(e) => setChain(e.target.value)}
                            style={{ width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid var(--line-strong)", background: "var(--panel)", color: "var(--text)", fontSize: "calc(13px * var(--fs-scale, 1))" }}>
                      {CHAINS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="rWallet">Suspect wallet address</label>
                    <input id="rWallet" type="text" placeholder="0x… / bc1… / T…" required
                           value={wallet} onChange={(e) => setWallet(e.target.value)} />
                  </div>
                  <div className="field">
                    <label htmlFor="rTypology">What happened? (optional)</label>
                    <input id="rTypology" type="text" placeholder="e.g. fake investment scheme, romance scam"
                           value={typology} onChange={(e) => setTypology(e.target.value)} />
                  </div>
                  <div className="field">
                    <label htmlFor="rDate">When did this happen? (optional)</label>
                    <input id="rDate" type="date" value={incidentDate} onChange={(e) => setIncidentDate(e.target.value)} />
                  </div>
                  <button type="submit" className="login-submit" disabled={repBusy}>{repBusy ? "Submitting…" : "Submit report"}</button>
                </form>
              </>
            )}

            {step === "done" && result && (
              <>
                <div className="title">Report received</div>
                <div className="sub">An investigating officer will triage this case.</div>
                <div style={{
                  border: "1px solid var(--line-strong)", borderRadius: 10, padding: 16, margin: "14px 0",
                  background: "var(--panel)",
                }}>
                  <div style={{ fontSize: "calc(11px * var(--fs-scale, 1))", color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: ".04em" }}>Your reference number</div>
                  <div style={{ fontSize: "calc(20px * var(--fs-scale, 1))", fontWeight: 700, color: "var(--copper)", marginTop: 4 }}>{result.ncrp_ref}</div>
                  <div style={{ fontSize: "calc(12.5px * var(--fs-scale, 1))", color: "var(--text-soft)", marginTop: 8 }}>Keep this number - quote it in any follow-up with the cyber-crime cell.</div>
                </div>
                <button type="button" className="login-submit" onClick={reportAnother}>Report another wallet</button>
                <p className="demo-hint" style={{ marginTop: 12 }}><button type="button" className="back-to-site" style={{ display: "inline", padding: 0 }} onClick={onBack}>&larr; Back to overview</button></p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
