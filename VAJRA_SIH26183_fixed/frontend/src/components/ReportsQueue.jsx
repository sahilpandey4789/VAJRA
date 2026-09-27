import React, { useEffect, useState, useCallback } from "react";
import * as api from "../console-core/api.js";
import { shortAddr, chainLabel, relativeTime } from "../console-core/format.js";
import { toast } from "../console-core/components/toast.js";

/*
 * Officer-side triage queue for the citizen "reporter" intake flow
 * (see pages/Report.jsx). Lists unassigned, reporter-submitted cases
 * (GET /api/cases/unassigned) and lets any officer/supervisor/admin
 * claim one into their own jurisdiction (POST /api/cases/{id}/claim),
 * after which it behaves like any other case in the main queue.
 */

export default function ReportsQueue({ openCase, onClaimed }) {
  const [rows, setRows] = useState(null); // null = loading
  const [claiming, setClaiming] = useState(null); // case_id currently being claimed
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      const list = await api.listUnassignedCases();
      setRows(list);
    } catch (e) {
      setErr(e.message || "Couldn't load citizen reports.");
      setRows([]);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const claim = async (caseId) => {
    setClaiming(caseId);
    try {
      const claimed = await api.claimCase(caseId);
      setRows((prev) => prev.filter((r) => r.id !== caseId));
      toast(`Claimed ${claimed.ncrp_ref} into your queue.`, "default");
      if (onClaimed) onClaimed();
      if (openCase) openCase(claimed.id);
    } catch (e) {
      toast(e.message || "Couldn't claim this case.", "error");
    } finally {
      setClaiming(null);
    }
  };

  return (
    <div className="card" style={{ maxWidth: 820 }}>
      <div className="card-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span>Citizen-reported wallets</span>
        <span style={{ fontSize: "calc(11px * var(--fs-scale, 1))", color: "var(--text-faint)", fontWeight: 500 }}>
          unassigned &middot; no jurisdiction yet
        </span>
      </div>

      {rows === null && (
        <>
          <div className="skel" style={{ height: 16, marginBottom: 8 }} />
          <div className="skel" style={{ height: 16, width: "80%" }} />
        </>
      )}

      {rows !== null && err && (
        <div style={{ fontSize: "calc(12px * var(--fs-scale, 1))", color: "var(--risk-high)" }}>{err}</div>
      )}

      {rows !== null && !err && rows.length === 0 && (
        <div style={{ fontSize: "calc(12px * var(--fs-scale, 1))", color: "var(--text-faint)" }}>
          No citizen reports waiting for triage right now.
        </div>
      )}

      {rows !== null && rows.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 4 }}>
          {rows.map((r) => (
            <div key={r.id} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
              padding: "12px 14px", borderRadius: 10, border: "1px solid var(--line-strong)", background: "var(--panel)",
            }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: "calc(13px * var(--fs-scale, 1))", fontWeight: 600, color: "var(--text)" }}>
                  {r.ncrp_ref}
                  <span style={{ marginLeft: 8, fontWeight: 500, color: "var(--text-soft)" }}>{chainLabel(r.chain)}</span>
                </div>
                <div style={{ fontSize: "calc(12px * var(--fs-scale, 1))", color: "var(--text-soft)", marginTop: 2 }}>
                  {shortAddr(r.suspect_wallet)}
                  {r.typology ? ` · ${r.typology}` : ""}
                </div>
                <div style={{ fontSize: "calc(11px * var(--fs-scale, 1))", color: "var(--text-faint)", marginTop: 2 }}>
                  reported {relativeTime(r.reported_at)}
                </div>
              </div>
              <button
                className="l-btn l-btn-solid"
                style={{ padding: "8px 16px", fontSize: "calc(12.5px * var(--fs-scale, 1))", whiteSpace: "nowrap" }}
                disabled={claiming === r.id}
                onClick={() => claim(r.id)}
              >
                {claiming === r.id ? "Claiming…" : "Claim case"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
