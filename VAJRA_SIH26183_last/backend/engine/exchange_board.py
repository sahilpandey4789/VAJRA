"""
Exchange Risk Board - aggregation logic, pulled out of server.py's route
handler so it's a pure function that can be unit-tested without spinning up
an HTTP server or a database (see backend/tests/test_exchange_board.py).

Reads the PS title literally: "Real-Time Identification of Fraud-Linked
Cryptocurrency Exchanges…" - not just tracing one wallet. Every completed
trace already stores its exchange_match inside report_json (see
engine/tracer.py); this rolls all of them up into a ranked list.

Roadmap note (see docs/BUILT_VS_ROADMAP.md): on Postgres this becomes a
single `GROUP BY` with jsonb extraction. Kept as Python-side aggregation
here because the reference build targets stdlib sqlite3 without assuming
the json1 extension is compiled in on every platform - the row shape this
function takes in is exactly what that GROUP BY would project, so the
swap is a call-site change, not a rewrite of the scoring logic.
"""
import json


def aggregate_exchange_risk(rows):
    """
    rows: iterable of objects with keys/attributes report_json, generated_at,
    case_id, confidence (sqlite3.Row or dict both work - see server.py).

    Returns a list of dicts, sorted by fraud_link_score descending, each with
    fraud_link_score_normalized in [0, 1] relative to the current max.
    """
    exchanges = {}
    for r in rows:
        try:
            report = json.loads(r["report_json"])
        except (TypeError, json.JSONDecodeError, KeyError):
            continue
        match = report.get("exchange_match")
        if not match:
            continue
        name = match.get("exchange") or "Unknown exchange"
        entry = exchanges.setdefault(name, {
            "exchange": name, "chains": set(), "case_ids": set(),
            "addresses": set(), "confidence_sum": 0.0, "last_seen": r["generated_at"],
        })
        entry["chains"].add(match.get("chain") or report.get("chain") or "?")
        entry["case_ids"].add(r["case_id"])
        entry["addresses"].add(match.get("address"))
        conf = r["confidence"] if r["confidence"] is not None else report.get("confidence", 0)
        entry["confidence_sum"] += conf or 0
        if (r["generated_at"] or "") > (entry["last_seen"] or ""):
            entry["last_seen"] = r["generated_at"]

    # Score formula (kept simple and defensible, documented like every
    # other scoring path in this codebase):
    #   fraud_link_score = linked_cases * avg_confidence
    # An exchange that keeps reappearing across many high-confidence victim
    # complaints ranks above one that appears once even at high confidence.
    board = []
    for name, e in exchanges.items():
        linked = len(e["case_ids"])
        avg_conf = (e["confidence_sum"] / linked) if linked else 0.0
        board.append({
            "exchange": name,
            "linked_cases": linked,
            "chains": sorted(e["chains"]),
            "addresses": sorted(a for a in e["addresses"] if a),
            "avg_confidence": round(avg_conf, 4),
            "fraud_link_score": round(linked * avg_conf, 4),
            "last_seen": e["last_seen"],
            "case_ids": sorted(e["case_ids"]),
        })
    board.sort(key=lambda b: b["fraud_link_score"], reverse=True)
    max_score = max((b["fraud_link_score"] for b in board), default=0) or 1
    for b in board:
        b["fraud_link_score_normalized"] = round(b["fraud_link_score"] / max_score, 4)
    return board
