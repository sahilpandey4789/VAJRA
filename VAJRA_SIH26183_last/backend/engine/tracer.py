"""
Tracer - orchestrates the 6-stage pipeline from the Master Document,
section 4: Intake -> Collection -> Tracing -> Clustering -> Attribution
-> Reporting. This is the one function the API layer calls; everything
else in engine/ is a building block it composes.
"""
import hashlib
import json
import time

from engine import chain_adapters, clustering, scoring, ml_model, fixtures, case_graph, risk_patterns, copilot, ofac_sanctions, india_map

STAGES = ["collecting", "tracing", "clustering", "checking", "scoring"]


def _parse_iso(ts):
    """Best-effort ISO-8601 -> epoch seconds. Returns None on anything
    unparseable rather than raising, so a single malformed timestamp in a
    live-provider response can't take down the whole trace."""
    if not ts:
        return None
    try:
        return time.mktime(time.strptime(ts.replace("Z", "").split(".")[0], "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        return None


def apply_time_lock(transactions, incident_timestamp):
    """
    Time-lock pre-processor - Technical Defense Document evidentiary
    integrity check: any transaction dated *before* the victim-reported
    incident is noise, not signal. A transfer that happened before the
    fraud was even reported cannot be part of the fraud's fund flow, so
    it is dropped before clustering/scoring ever sees it, rather than
    left in to dilute or skew the confidence calculation.

    Fails open (returns transactions unchanged) if incident_timestamp is
    missing/unparseable - this is an evidentiary tightening, not a new
    way for the trace to silently produce an empty result.
    """
    cutoff = _parse_iso(incident_timestamp)
    if cutoff is None:
        return transactions, 0
    kept, dropped = [], 0
    for t in transactions:
        ts = _parse_iso(t.get("timestamp"))
        if ts is not None and ts < cutoff:
            dropped += 1
            continue
        kept.append(t)
    return kept, dropped


def _known_exchange_lookup(conn, address):
    row = conn.execute("SELECT exchange, chain FROM known_exchange_wallets WHERE address = ?", (address,)).fetchone()
    return dict(row) if row else None


def _known_mixer_lookup(conn, address):
    row = conn.execute("SELECT label, chain FROM known_mixer_contracts WHERE address = ?", (address,)).fetchone()
    return dict(row) if row else None


def run_trace(conn, case_row, max_hops=6, progress_cb=None):
    """
    Runs the full pipeline synchronously (each stage is fast against the
    fixture/mock data) while still emitting the same stage events a
    Celery+WebSocket production job would push, via progress_cb(stage,
    detail) - the SSE endpoint in server.py forwards these live so the
    UI's 5-step sequence reflects a pipeline that actually ran, not a
    canned animation timed against nothing.
    """
    def emit(stage, detail=""):
        if progress_cb:
            progress_cb(stage, detail)
        time.sleep(0.25)  # pacing so the live sequence is visible/legible, not instantaneous

    fixture_key = case_row["demo_fixture"]
    chain = case_row["chain"]
    suspect = case_row["suspect_wallet"]
    trace_started_at = time.monotonic()

    # --- Stage: collecting ---
    emit("collecting", f"Pulling transaction history for {suspect[:10]}… on {chain}")
    adapter = chain_adapters.get_adapter(chain, fixture_key)
    data_source = "offline-fixture"
    try:
        transactions = adapter.fetch_forward_transactions(suspect, max_hops=max_hops)
        data_source = getattr(adapter, "last_provider_used", None) or getattr(adapter, "provider_name", "offline-fixture")
    except chain_adapters.AdapterError as exc:
        # Every configured live provider failed - fall back to the
        # offline fixture rather than crashing the trace. Surfaced to
        # the UI via report["data_source"] == "offline-fixture-fallback"
        # so the investigator sees exactly why they're looking at cached
        # data instead of a silent live/offline swap.
        emit("collecting", f"Live providers unavailable ({exc}) - falling back to offline demo data")
        fallback = chain_adapters.MockAdapter(chain, fixture_key)
        transactions = fallback.fetch_forward_transactions(suspect, max_hops=max_hops)
        data_source = "offline-fixture-fallback"

    # --- Time-lock pre-processor: drop anything dated before the
    # victim-reported incident (falls back to the case's reported_at if
    # no explicit incident_timestamp was captured at intake). See
    # apply_time_lock()'s docstring for why this runs before tracing/
    # clustering ever sees the data, not as a post-hoc filter.
    incident_ts = case_row["incident_timestamp"] if "incident_timestamp" in case_row.keys() else None
    incident_ts = incident_ts or case_row["reported_at"]
    transactions, dropped_pre_incident = apply_time_lock(transactions, incident_ts)

    # --- Stage: tracing ---
    emit("tracing", f"{len(transactions)} transactions traced forward across {max_hops} max hops"
                     + (f" ({dropped_pre_incident} pre-incident transaction(s) excluded by time-lock)"
                        if dropped_pre_incident else ""))
    hops_reached = max((t["hop"] for t in transactions), default=0)

    # --- Stage: clustering ---
    emit("clustering", "Applying co-spend, change-address and deposit-fingerprint heuristics")
    clusters, ledger_events = clustering.build_clusters(transactions)
    if dropped_pre_incident:
        ledger_events.append({
            "type": "time_lock", "mark": "info",
            "text": f"{dropped_pre_incident} transaction(s) excluded - dated before the reported incident",
            "sub": f"Time-lock cutoff: {incident_ts}",
        })

    fx = fixtures.FIXTURE_MAP.get(fixture_key, {})
    deposit_stats = fx.get("deposit_stats")
    exchange_hit_address = fx.get("exchange_hit")

    df = clustering.deposit_fingerprint_score(deposit_stats)
    if df["event"]:
        ledger_events.append(df["event"])

    # --- Stage: checking (obfuscation / mixer check) ---
    emit("checking", "Checking path against known mixer/tumbler contract list")
    mixer_hit = None
    for t in transactions:
        for o in t["outputs"]:
            m = _known_mixer_lookup(conn, o["address"])
            if m:
                mixer_hit = {"address": o["address"], **m}
                break
        if mixer_hit:
            break
    mixer_penalty = 1.0 if mixer_hit else 0.0
    if mixer_hit:
        ledger_events.append({
            "type": "mixer", "mark": "flag",
            "text": f"Known mixer contract detected - {mixer_hit['label']}",
            "sub": f"Path enters {mixer_hit['address'][:12]}… ; deterministic trail stops here",
        })
    else:
        ledger_events.append({
            "type": "mixer_clear", "mark": "check",
            "text": "No mixer or tumbler hop found",
            "sub": "Path checked against known mixing-service list",
        })

    peel_hops = [t for t in transactions if len([o for o in t["outputs"]]) == 1 and t["outputs"][0]["value"] < 0.5]
    if len(peel_hops) >= 5:
        ledger_events.insert(0, {
            "type": "peel_chain", "mark": "flag",
            "text": f"Peel-chain pattern detected at hop {peel_hops[0]['hop']}",
            "sub": f"{len(peel_hops)} sequential small outflows, large balance continuing forward",
        })

    exchange_match = None
    for t in transactions:
        for o in t["outputs"]:
            ex = _known_exchange_lookup(conn, o["address"])
            if ex:
                exchange_match = {"address": o["address"], "matched_at": t["timestamp"], **ex}
                break
        if exchange_match:
            break
    if exchange_match:
        ledger_events.append({
            "type": "exchange_match", "mark": "info",
            "text": f"Terminal wallet matches known {exchange_match['exchange']} hot wallet",
            "sub": exchange_match["address"],
        })

    # --- Real OFAC SDN sanctions-list match. Distinct from exchange_match
    # above: this checks every address that actually appears in the trace
    # (inputs and outputs, every hop - a sanctioned wallet is meaningful
    # wherever it sits in the chain, not just at the terminal hop) against
    # engine/ofac_sanctions.py's real, government-published address list.
    # See that module's docstring for sourcing.
    sanctions_match = None
    for t in transactions:
        for addr in [t.get("inputs", [None])[0]] + [o["address"] for o in t["outputs"]]:
            hit = ofac_sanctions.lookup(addr)
            if hit:
                sanctions_match = hit
                break
        if sanctions_match:
            break
    if sanctions_match:
        ledger_events.append({
            "type": "sanctions_match", "mark": "flag",
            "text": f"Address matches OFAC SDN list entry: {sanctions_match['entity_name']}"
                    f" ({', '.join(sanctions_match['programs'])}, listed {sanctions_match['date_listed']})",
            "sub": sanctions_match["address"],
        })

    # --- cross-case linkage: real union-find graph query over every other
    # case's already-traced fund-flow, not a hardcoded fixture list. See
    # engine/case_graph.py's module docstring for why this is the same
    # graph query Neo4j would run at this data volume. Known exchange/mixer
    # addresses are excluded from the overlap check - millions of unrelated
    # people also send funds to WazirX; that is not evidence of a shared
    # laundering network the way a shared *intermediate* wallet is.
    infra_addrs = (
        {row["address"] for row in conn.execute("SELECT address FROM known_exchange_wallets").fetchall()}
        | {row["address"] for row in conn.execute("SELECT address FROM known_mixer_contracts").fetchall()}
    )
    current_addresses = case_graph.extract_addresses(
        {"suspect_wallet": suspect, "transactions": transactions}, exclude=infra_addrs
    )
    other_rows = conn.execute(
        """SELECT tr.case_id, tr.report_json, tr.version, c.ncrp_ref, c.chain, c.confidence
           FROM trace_reports tr JOIN cases c ON tr.case_id = c.id
           WHERE tr.case_id != ? ORDER BY tr.version ASC""",
        (case_row["id"],),
    ).fetchall()
    other_latest = {}
    for r in other_rows:
        other_latest[r["case_id"]] = r  # ascending version -> last write wins -> latest survives
    other_index = case_graph.build_case_index(other_latest.values(), exclude=infra_addrs)

    linked_case_details = []
    for other_id, info in other_index.items():
        shared = current_addresses & info["addresses"]
        if shared:
            linked_case_details.append({
                "case_id": other_id, "ncrp_ref": info["ncrp_ref"], "chain": info["chain"],
                "confidence": info["confidence"], "shared_addresses": sorted(shared),
            })
    linked_case_details.sort(key=lambda d: -(d["confidence"] or 0))
    linked_cases = [d["ncrp_ref"] for d in linked_case_details]

    # Note: this only sees cases already traced *before* this one - a real
    # limitation of a point-in-time ledger entry, same as an investigator
    # would have. The always-current picture (including links discovered
    # by a case traced *after* this one) lives in GET /api/cases/{id}/network
    # and GET /api/cases/network, which recompute fresh on every call
    # instead of freezing at trace time. See frontend/js/views/network.js.
    if linked_case_details:
        shared_sample = sorted({a for d in linked_case_details for a in d["shared_addresses"]})[:2]
        ledger_events.append({
            "type": "cross_case", "mark": "flag",
            "text": f"Suspect wallet linked to {len(linked_case_details)} other open case(s)",
            "sub": ", ".join(linked_cases) + f" - shared address(es): {', '.join(shared_sample)}",
        })

    # --- Stage: scoring ---
    emit("scoring", "Running illicit-probability classifier and computing attribution confidence")
    terminal_address = transactions[-1]["outputs"][0]["address"] if transactions else suspect
    features = ml_model.wallet_features_from_tx(terminal_address, transactions) if transactions else [0] * 8
    ai_illicit_prob = ml_model.predict_illicit_probability(features) if transactions else 0.5

    sender_z = clustering.sender_diversity_zscore(df["unique_senders"]) if df["unique_senders"] else -1.0
    cluster_quality = clustering.cluster_quality_score(clusters)
    confidence, breakdown = scoring.score(
        deposit_fingerprint=df["deposit_fingerprint"],
        sweep_regularity=df["sweep_regularity"],
        sender_diversity_z=sender_z,
        mixer_penalty=mixer_penalty,
        ai_illicit_probability=ai_illicit_prob,
        cluster_quality=cluster_quality,
    )
    decision = scoring.decide(confidence, mixer_penalty, exchange_matched=bool(exchange_match))
    attribution = scoring.attribution_tier(confidence, exchange_matched=bool(exchange_match), mixer_penalty=mixer_penalty,
                                            sanctions_matched=bool(sanctions_match))
    ai_explanation = ml_model.explain_prediction(features) if transactions else []

    cluster_summary = [
        {"root": root, "size": len(c["addresses"]), "edge_count": len(c["edges"])}
        for root, c in clusters.items()
    ]

    # --- Advanced risk-pattern detection (real, over the actual traced
    # transaction shape/timing) - see engine/risk_patterns.py module
    # docstring for what each detector actually checks.
    detected_patterns = risk_patterns.detect_all(
        transactions, mixer_hit=mixer_hit, exchange_match=exchange_match, origin_address=suspect,
    )

    report = {
        "case_id": case_row["id"],
        "ncrp_ref": case_row["ncrp_ref"],
        "suspect_wallet": suspect,
        "chain": chain,
        "hops_traced": hops_reached,
        "transactions": transactions,
        "clusters": cluster_summary,
        "ledger": ledger_events,
        "confidence": confidence,
        "confidence_breakdown": breakdown,
        "cluster_quality": cluster_quality,
        "ai_illicit_probability": round(ai_illicit_prob, 4),
        "ai_model_metrics": ml_model.get_metrics(),
        "ai_explanation": ai_explanation,
        "mixer_hit": mixer_hit,
        "exchange_match": exchange_match,
        "sanctions_match": sanctions_match,
        "linked_cases": linked_cases,
        "linked_case_details": linked_case_details,
        "risk_patterns": detected_patterns,
        "geo_trail": india_map.case_geo_trail(case_row["jurisdiction"], exchange_match, mixer_hit),
        "decision": decision,
        "attribution_tier": attribution["tier"],
        "attribution_reason": attribution["reason"],
        "dropped_pre_incident_tx": dropped_pre_incident,
        "data_source": data_source,
        "trace_duration_ms": round((time.monotonic() - trace_started_at) * 1000, 1),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    # Investigation Copilot: a reasoning layer over the fields already
    # above - see engine/copilot.py docstring for why this is narration
    # over real computed evidence, never a fresh black-box judgement.
    report["investigation_brief"] = copilot.generate_brief(report)
    report_json = json.dumps(report, sort_keys=True)
    report["report_hash"] = hashlib.sha256(report_json.encode()).hexdigest()
    return report
