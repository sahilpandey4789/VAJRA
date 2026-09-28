import React, { useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { ICONS } from "../console-core/icons.js";

const ROLE_TAB_CODES = { officer: "MHA-CY-08231", supervisor: "MHA-CY-04410", admin: "MHA-CY-00001" };

export default function Login({ initialTab, onBack }) {
  const { login, register } = useAuth();
  const [tab, setTab] = useState(initialTab || "signin");

  // ---- sign-in form ----
  const [officerCode, setOfficerCode] = useState("");
  const [password, setPassword] = useState("");
  const [loginErr, setLoginErr] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);

  const submitLogin = async (e) => {
    e.preventDefault();
    setLoginErr("");
    setLoginBusy(true);
    try {
      await login(officerCode.trim(), password);
    } catch (err) {
      setLoginErr(err.message || "Sign-in failed.");
    } finally {
      setLoginBusy(false);
    }
  };

  const pickRole = (role) => {
    setOfficerCode(ROLE_TAB_CODES[role]);
    setPassword("vajra123");
  };

  // ---- register form ----
  const [regName, setRegName] = useState("");
  const [regCode, setRegCode] = useState("");
  const [regJurisdiction, setRegJurisdiction] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirm, setRegConfirm] = useState("");
  const [regErr, setRegErr] = useState("");
  const [regBusy, setRegBusy] = useState(false);

  const submitRegister = async (e) => {
    e.preventDefault();
    setRegErr("");
    if (regPassword !== regConfirm) { setRegErr("Passwords don't match."); return; }
    setRegBusy(true);
    try {
      await register({ name: regName.trim(), officer_code: regCode.trim(), jurisdiction: regJurisdiction.trim(), password: regPassword });
    } catch (err) {
      setRegErr(err.message || "Couldn't create the account.");
    } finally {
      setRegBusy(false);
    }
  };

  return (
    <div id="loginScreen" className="show">
      <div className="gov-strip" aria-hidden="true"></div>
      <div className="login-shell">
        <div className="login-aside">
          <div className="brandmark">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="1.4"><path d="M12 2l7 3v6c0 5-3.2 8.4-7 11-3.8-2.6-7-6-7-11V5l7-3z"/><path d="M9 12l2 2 4-4"/></svg>
            <div><div className="brandmark-name">VAJRA</div><div className="brandmark-sub">Virtual Asset Judicial Response &amp; Attribution</div></div>
          </div>
          <span className="gov-badge" style={{ marginTop: 4 }}><span dangerouslySetInnerHTML={{ __html: ICONS.chakra }} />Govt. of India</span>
          <div className="login-aside-copy">
            <h1>Trace the money.<br/>Name the exchange.</h1>
            <p>A single console for fund-flow attribution - from a victim's
              wallet complaint to a signed legal notice, with every hop and every
              confidence score on the record.</p>
          </div>
          <svg className="login-hopflow" viewBox="0 0 360 120" aria-hidden="true">
            <path id="hopPath" d="M28 90 C 90 20, 150 100, 200 40 S 300 20, 334 60" fill="none" stroke="rgba(227,185,140,.28)" strokeWidth="1.4" strokeDasharray="3 5"/>
            <circle cx="28" cy="90" r="4.5" fill="#22D3EE"/>
            <circle cx="200" cy="40" r="4.5" fill="#60A5FA"/>
            <circle cx="334" cy="60" r="5.5" fill="#FBBF24"/>
            <circle r="3.2" fill="#22D3EE" className="hop-pulse">
              <animateMotion dur="4.5s" repeatCount="indefinite" rotate="auto">
                <mpath href="#hopPath"/>
              </animateMotion>
            </circle>
          </svg>
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
            <div className="auth-tabs">
              <button type="button" className={`auth-tab ${tab === "signin" ? "active" : ""}`} onClick={() => setTab("signin")}>Sign in</button>
              <button type="button" className={`auth-tab ${tab === "signup" ? "active" : ""}`} onClick={() => setTab("signup")}>Create account</button>
            </div>

            <div className="title">Officer sign-in</div>
            <div className="sub">Secure access for authorised cyber-crime cell personnel only.</div>

            {tab === "signin" && (
              <>
                <div className={`login-error ${loginErr ? "show" : ""}`}>{loginErr}</div>
                <form onSubmit={submitLogin}>
                  <div className="field">
                    <label htmlFor="officerCode">Officer ID</label>
                    <input id="officerCode" type="text" placeholder="MHA-CY-08231"
                           autoComplete="username" required value={officerCode} onChange={(e) => setOfficerCode(e.target.value)} />
                  </div>
                  <div className="field">
                    <label htmlFor="password">Password</label>
                    <input id="password" type="password" placeholder="••••••••" autoComplete="current-password"
                           required value={password} onChange={(e) => setPassword(e.target.value)} />
                  </div>
                  <button type="submit" className="login-submit" disabled={loginBusy}>{loginBusy ? "Signing in…" : "Sign in"}</button>
                </form>

                <details className="demo-access">
                  <summary>Demo access for reviewers</summary>
                  <div className="role-tabs">
                    <button type="button" className="role-tab" onClick={() => pickRole("officer")}>Officer</button>
                    <button type="button" className="role-tab" onClick={() => pickRole("supervisor")}>Supervisor</button>
                    <button type="button" className="role-tab" onClick={() => pickRole("admin")}>Admin</button>
                  </div>
                  <p className="demo-hint">Fills a seeded reviewer account - password <code>vajra123</code> for all three.</p>
                </details>
              </>
            )}

            {tab === "signup" && (
              <form onSubmit={submitRegister}>
                <div className="field">
                  <label htmlFor="regName">Full name</label>
                  <input id="regName" type="text" placeholder="A. Sharma" autoComplete="name" required
                         value={regName} onChange={(e) => setRegName(e.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="regOfficerCode">Choose an officer ID</label>
                  <input id="regOfficerCode" type="text" placeholder="MHA-CY-XXXXX" autoComplete="username" required
                         value={regCode} onChange={(e) => setRegCode(e.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="regJurisdiction">Jurisdiction / cell</label>
                  <input id="regJurisdiction" type="text" placeholder="Cyber Crime Cell - Mumbai" autoComplete="organization" required
                         value={regJurisdiction} onChange={(e) => setRegJurisdiction(e.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="regPassword">Password</label>
                  <input id="regPassword" type="password" placeholder="At least 8 characters" autoComplete="new-password" minLength={8} required
                         value={regPassword} onChange={(e) => setRegPassword(e.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="regPasswordConfirm">Confirm password</label>
                  <input id="regPasswordConfirm" type="password" placeholder="••••••••" autoComplete="new-password" minLength={8} required
                         value={regConfirm} onChange={(e) => setRegConfirm(e.target.value)} />
                </div>
                <div className={`login-error ${regErr ? "show" : ""}`}>{regErr}</div>
                <button type="submit" className="login-submit" disabled={regBusy}>{regBusy ? "Creating account…" : "Create account"}</button>
                <p className="demo-hint" style={{ marginTop: 12 }}>New accounts are created as Officer role.</p>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}