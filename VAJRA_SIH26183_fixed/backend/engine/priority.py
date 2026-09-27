"""
Action Priority Engine.

The problem this solves: every other view in VAJRA (case list, exchange
board, network graph) shows the officer *everything*. None of them
answer the one question that actually matters at 9am with 40 open
cases: "which case do I touch first?"

This is a real, hard investigative problem, not a cosmetic sort order.
Crypto fraud recovery has a genuine time-decay curve - a "golden hour"
that exists for a concrete, mechanical reason: once traced funds sit in
a *known exchange's* hot wallet, that exchange can freeze/hold them on a
Section 102 CrPC notice - but only until the fraudster (or, more often,
an automated sweep the exchange itself runs) moves the balance out to
cold storage or the funds get further mixed with other users' deposits
in an omnibus wallet, at which point "freeze this specific balance"
stops being a request any exchange compliance desk can technically
fulfil. There is no public, precise SLA published by any exchange for
how long that window stays open - this build treats it as a soft,
labelled decay curve (fresh -> ageing -> stale) for triage/demo purposes,
not a claimed guarantee that funds vanish at any exact hour mark, and
the reason string always says so explicitly rather than implying a
guarantee.

compute_case_priority() is a pure function over already-computed data
(the case row, its latest trace report, its notices) - same "narrate,
don't re-decide" discipline as engine/copilot.py. It does not re-run
scoring or attribution; it reads what tracer.py and scoring.py already
decided and asks "given all of this, how urgent is it, right now?"
"""
import datetime

# Score weights are additive and intentionally simple/auditable - every
# point on the 0-100 scale traces back to one line below, so an officer
# (or a judge) can ask "why is this case #1?" and get a real answer,
# not a black-box number.
_TIER_POINTS = {"CONFIRMED": 45, "PROBABLE": 25, "UNATTRIBUTED": 8}
_RISK_POINTS = {"high": 20, "medium": 10, "low": 3}
_SYNDICATE_POINTS = {"CRITICAL": 15, "ESCALATE": 8, "WATCH": 3}

_TERMINAL_CASE_STATUSES = ("cleared", "closed")


def _hours_since(iso_ts, now=None):
    if not iso_ts:
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    try:
        ts = datetime.datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return (now - ts).total_seconds() / 3600.0


def _golden_hour_component(hours_elapsed):
    """Decay curve for the exchange-freeze window. Buckets, not a single
    cliff-edge - a real compliance desk doesn't act at a precise minute
    either. Returns (points, label)."""
    if hours_elapsed is None:
        return 0, None
    if hours_elapsed <= 6:
        return 15, f"reached the exchange {hours_elapsed:.1f}h ago - freeze window freshest"
    if hours_elapsed <= 24:
        return 10, f"reached the exchange {hours_elapsed:.0f}h ago - window still open"
    if hours_elapsed <= 72:
        return 5, f"reached the exchange {hours_elapsed / 24:.1f}d ago - window ageing"
    return 0, f"reached the exchange {hours_elapsed / 24:.0f}d ago - window likely stale"


def compute_case_priority(case_row, latest_report, case_notices, now=None):
    """
    case_row: sqlite3.Row / dict for the case (status, risk_band,
      attribution_tier, syndicate_alert_tier, confidence, ncrp_ref).
    latest_report: parsed report_json dict of the most recent trace for
      this case, or None if it hasn't been traced yet.
    case_notices: list of notice dicts/rows already drafted for this case
      (may be empty).
    Returns {"score": int 0-100, "urgency": "critical"|"high"|"medium"|"low",
             "reasons": [str, ...], "hours_since_exchange_hit": float|None}.
    """
    score = 0
    reasons = []

    tier = (case_row.get("attribution_tier") if isinstance(case_row, dict) else case_row["attribution_tier"]) or "UNATTRIBUTED"
    risk_band = (case_row.get("risk_band") if isinstance(case_row, dict) else case_row["risk_band"]) or "low"
    syn_tier = case_row.get("syndicate_alert_tier") if isinstance(case_row, dict) else case_row["syndicate_alert_tier"]
    status = case_row.get("status") if isinstance(case_row, dict) else case_row["status"]

    score += _TIER_POINTS.get(tier, 0)
    if tier == "CONFIRMED":
        reasons.append("attribution CONFIRMED")

    score += _RISK_POINTS.get(risk_band, 0)

    hours_elapsed = None
    exchange_match = (latest_report or {}).get("exchange_match")
    mixer_hit = (latest_report or {}).get("mixer_hit")

    already_sent = any((n.get("status") if isinstance(n, dict) else n["status"]) == "sent" for n in case_notices)
    already_pending = any(
        (n.get("status") if isinstance(n, dict) else n["status"]) in ("pending_approval", "approved")
        for n in case_notices
    )

    if exchange_match:
        matched_at = exchange_match.get("matched_at")
        hours_elapsed = _hours_since(matched_at, now)
        gh_points, gh_label = _golden_hour_component(hours_elapsed)
        exchange_name = exchange_match.get("exchange", "exchange")
        if already_sent:
            score -= 30
            reasons.append(f"notice already sent to {exchange_name} - monitoring only")
        elif already_pending:
            score -= 10
            reasons.append(f"notice for {exchange_name} awaiting approval")
        else:
            score += 20
            reasons.append(f"funds traced to {exchange_name}, no notice drafted yet - actionable now")
        score += gh_points
        if gh_label:
            reasons.append(gh_label)
    elif mixer_hit:
        score += 5
        reasons.append(f"path enters a known mixer ({mixer_hit.get('label', 'unlabelled')}) - deterministic trail ends there")
    elif latest_report is None:
        reasons.append("not traced yet")
    else:
        reasons.append("no exchange or mixer match on current trace")

    if syn_tier in _SYNDICATE_POINTS:
        score += _SYNDICATE_POINTS[syn_tier]
        reasons.append(f"{syn_tier} syndicate alert")

    score = max(0, min(100, score))
    if score >= 65:
        urgency = "critical"
    elif score >= 40:
        urgency = "high"
    elif score >= 20:
        urgency = "medium"
    else:
        urgency = "low"

    return {
        "score": score,
        "urgency": urgency,
        "reasons": reasons,
        "hours_since_exchange_hit": round(hours_elapsed, 1) if hours_elapsed is not None else None,
    }


def build_priority_queue(conn, limit=10, now=None):
    """
    Queries every non-terminal case, computes compute_case_priority()
    against its latest trace report (if any) and its notices, and
    returns the top `limit` sorted descending by score. Read-only,
    recomputes fresh every call (same "always current, never a frozen
    snapshot" discipline as the case-network endpoints) - cheap at this
    data volume (a few hundred cases, one indexed query per case), same
    reasoning as case_graph.py's module docstring about why an in-process
    computation is the right architectural choice here rather than a
    background job.
    """
    import json

    cases = conn.execute(
        f"SELECT * FROM cases WHERE status NOT IN ({','.join('?' * len(_TERMINAL_CASE_STATUSES))})",
        _TERMINAL_CASE_STATUSES,
    ).fetchall()

    results = []
    for case in cases:
        report_row = conn.execute(
            "SELECT report_json FROM trace_reports WHERE case_id=? ORDER BY version DESC LIMIT 1",
            (case["id"],),
        ).fetchone()
        latest_report = json.loads(report_row["report_json"]) if report_row else None

        notice_rows = conn.execute("SELECT * FROM notices WHERE case_id=?", (case["id"],)).fetchall()
        case_notices = [dict(n) for n in notice_rows]

        priority = compute_case_priority(case, latest_report, case_notices, now=now)
        results.append({
            "case_id": case["id"],
            "ncrp_ref": case["ncrp_ref"],
            "suspect_wallet": case["suspect_wallet"],
            "chain": case["chain"],
            "confidence": case["confidence"],
            "risk_band": case["risk_band"],
            "attribution_tier": case["attribution_tier"],
            "status": case["status"],
            **priority,
        })

    results.sort(key=lambda r: -r["score"])
    return results[:limit]
