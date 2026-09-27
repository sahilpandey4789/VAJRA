"""
Advanced risk-pattern detection - real heuristics over the actual traced
transaction list (timestamps, hop numbers, input/output counts, values),
not a lookup table and not an LLM call. Mixer and exchange detection
already exist as their own real checks in tracer.py (known-contract
lookups against the database); this module adds the patterns that don't
need a known-address list, because they're detectable from *shape and
timing* alone:

  - rapid_transfers - funds move on within an unusually short window,
                        consistent with automated layering rather than a
                        human manually moving funds.
  - layering_depth - an unusually long hop chain before reaching a
                        resolvable terminal (exchange/mixer/unresolved).
  - structuring - repeated small, single-output transfers from the
                        same hop (a formalised version of the peel-chain
                        check tracer.py already ran inline; same
                        threshold, given its own name and evidence here).
  - high_fan_out - a single transaction splitting funds across an
                        unusually large number of outputs in one hop.
  - round_trip - funds return to the original suspect wallet
                        after crossing intermediate hops, a wash-
                        laundering / self-dealing signature.

Every pattern returned includes the transaction hashes / hop numbers
that triggered it - evidence an investigator can click through to on
the fund-flow graph, not a bare label.

Pure functions only - no DB, no HTTP. Unit-tested directly, same
convention as engine/case_graph.py and engine/exchange_board.py.
"""
from datetime import datetime, timezone


def _parse_ts(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


RAPID_TRANSFER_THRESHOLD_MINUTES = 15
LAYERING_DEPTH_THRESHOLD_HOPS = 4
STRUCTURING_MIN_COUNT = 4
STRUCTURING_MAX_VALUE = 0.5
HIGH_FAN_OUT_THRESHOLD = 5
ROUND_TRIP_MIN_HOP = 2  # funds must cross at least one intermediate hop before "returning"


def detect_rapid_transfers(transactions):
    """
    Consecutive hops (by timestamp) less than
    RAPID_TRANSFER_THRESHOLD_MINUTES apart - funds swept onward faster
    than routine manual activity, a documented layering signature.
    """
    timed = sorted(
        ((_parse_ts(t.get("timestamp")), t) for t in transactions if _parse_ts(t.get("timestamp"))),
        key=lambda p: p[0],
    )
    hits = []
    for (t0, tx0), (t1, tx1) in zip(timed, timed[1:]):
        delta_minutes = (t1 - t0).total_seconds() / 60.0
        if 0 <= delta_minutes < RAPID_TRANSFER_THRESHOLD_MINUTES:
            hits.append({
                "tx_hashes": [tx0.get("tx_hash"), tx1.get("tx_hash")],
                "gap_minutes": round(delta_minutes, 2),
            })
    if not hits:
        return None
    fastest = min(hits, key=lambda h: h["gap_minutes"])
    return {
        "pattern": "rapid_transfers",
        "severity": "high" if fastest["gap_minutes"] < 5 else "medium",
        "label": "Rapid sequential transfers",
        "evidence": f"{len(hits)} hop-to-hop gap(s) under {RAPID_TRANSFER_THRESHOLD_MINUTES} min "
                    f"(fastest: {fastest['gap_minutes']} min)",
        "tx_hashes": sorted({h for hit in hits for h in hit["tx_hashes"] if h}),
    }


def detect_layering(transactions):
    """Hop chain longer than LAYERING_DEPTH_THRESHOLD_HOPS before the trail resolves."""
    hops = {t.get("hop") for t in transactions if t.get("hop") is not None}
    if not hops:
        return None
    depth = max(hops)
    if depth < LAYERING_DEPTH_THRESHOLD_HOPS:
        return None
    return {
        "pattern": "layering",
        "severity": "high" if depth >= 6 else "medium",
        "label": "Deep layering chain",
        "evidence": f"{depth} sequential hops before the trail resolves - beyond the "
                    f"{LAYERING_DEPTH_THRESHOLD_HOPS}-hop threshold for routine transfers",
        "tx_hashes": sorted({t.get("tx_hash") for t in transactions if t.get("tx_hash")}),
    }


def detect_structuring(transactions):
    """Repeated small single-output transfers from the same hop (peel chain / smurfing)."""
    by_hop = {}
    for t in transactions:
        outs = t.get("outputs") or []
        if len(outs) == 1 and len(t.get("inputs") or []) == 1 and outs[0].get("value", 0) < STRUCTURING_MAX_VALUE:
            by_hop.setdefault(t.get("hop"), []).append(t)
    worst = max(by_hop.values(), key=len, default=[])
    if len(worst) < STRUCTURING_MIN_COUNT:
        return None
    return {
        "pattern": "structuring",
        "severity": "high" if len(worst) >= 8 else "medium",
        "label": "Structuring / peel-chain pattern",
        "evidence": f"{len(worst)} sequential small transfers (each < {STRUCTURING_MAX_VALUE}) "
                    f"from the same hop - consistent with splitting funds to stay under reporting thresholds",
        "tx_hashes": sorted({t.get("tx_hash") for t in worst if t.get("tx_hash")}),
    }


def detect_high_fan_out(transactions):
    """A single transaction splitting funds across an unusually large number of outputs."""
    worst = max(transactions, key=lambda t: len(t.get("outputs") or []), default=None)
    if not worst or len(worst.get("outputs") or []) < HIGH_FAN_OUT_THRESHOLD:
        return None
    return {
        "pattern": "high_fan_out",
        "severity": "medium",
        "label": "High fan-out transaction",
        "evidence": f"One transaction splits funds across {len(worst['outputs'])} outputs in a single hop",
        "tx_hashes": [worst.get("tx_hash")] if worst.get("tx_hash") else [],
    }


def detect_round_trip(transactions, origin_address):
    """
    Round-trip / self-dealing (a.k.a. "boomerang") pattern: the suspect's
    own origin wallet reappears as a RECEIVING address later in its own
    traced fund-flow, after the funds already left it. A recognised
    wash-laundering technique - moving funds out through several hops and
    back to a wallet the same actor still controls, which manufactures
    transaction history and "ages" the funds without the actor ever
    actually losing control of them. Requires the funds to have crossed
    at least ROUND_TRIP_MIN_HOP intermediate hops first, so a same-hop or
    one-hop bounce (which can just be routine change-handling) doesn't
    false-positive.
    """
    if not origin_address:
        return None
    hits = []
    for t in transactions:
        hop = t.get("hop")
        if hop is None or hop < ROUND_TRIP_MIN_HOP:
            continue
        for o in (t.get("outputs") or []):
            if o.get("address") == origin_address:
                hits.append(t)
                break
    if not hits:
        return None
    max_hop = max(t["hop"] for t in hits)
    return {
        "pattern": "round_trip",
        "severity": "high",
        "label": "Round-trip / self-dealing pattern",
        "evidence": f"Funds return to the original suspect wallet at hop {max_hop} after leaving it "
                    f" - consistent with wash-laundering to manufacture transaction history while "
                    f"retaining control of the funds",
        "tx_hashes": sorted({t.get("tx_hash") for t in hits if t.get("tx_hash")}),
    }


def detect_all(transactions, mixer_hit=None, exchange_match=None, origin_address=None):
    """
    Runs every detector and folds in the mixer/exchange findings tracer.py
    already computed (so the frontend has one list to render instead of
    stitching several report fields together itself). Returns a list,
    highest severity first, empty if nothing fired.
    """
    patterns = [
        detect_rapid_transfers(transactions),
        detect_layering(transactions),
        detect_structuring(transactions),
        detect_high_fan_out(transactions),
        detect_round_trip(transactions, origin_address),
    ]
    if mixer_hit:
        patterns.append({
            "pattern": "mixer_hop", "severity": "high", "label": "Known mixer / tumbler hop",
            "evidence": f"Path enters {mixer_hit.get('label', 'a known mixer')} at {mixer_hit.get('address', '')[:12]}…",
            "tx_hashes": [],
        })
    if exchange_match:
        patterns.append({
            "pattern": "exchange_cashout", "severity": "medium", "label": "Exchange cash-out point",
            "evidence": f"Terminal wallet matches a known {exchange_match.get('exchange', 'exchange')} hot wallet",
            "tx_hashes": [],
        })
    patterns = [p for p in patterns if p]
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    patterns.sort(key=lambda p: severity_rank.get(p["severity"], 3))
    return patterns
