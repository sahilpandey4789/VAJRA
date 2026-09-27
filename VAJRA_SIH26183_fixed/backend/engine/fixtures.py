"""
Offline-first demo dataset.

Per the Technical Defense Document section 12 (Demo Risk Mitigation),
the full stack must run with zero internet dependency and reproduce
three honest outcomes: a high-confidence match, a mixer-blocked partial
trace, and a cleared false-positive. This module is that dataset.

Every transaction below is *synthetic* (constructed to match documented
laundering typologies from published typology reports), not scraped
real-world data. When VAJRA_LIVE_MODE=1 and a chain API key is present,
engine/chain_adapters.py fetches real transactions instead and the
clustering/scoring engine runs unchanged over the real data - the
seed graphs below only feed the offline/demo path.
"""

KNOWN_EXCHANGE_WALLETS = [
    ("0x9f1c2a7e4b6d0f3c8a5e2b7d1f4c6a9e0b3d5f71", "ETHEREUM", "WazirX"),
    ("TXf7k2Lp9vR5j3Fq1sD6w4Yb9z0X88vRqM2n", "TRON", "CoinDCX"),
    ("bc1qexchangecolddepositaddr00000000xyz", "BITCOIN", "Binance"),
]

KNOWN_MIXER_CONTRACTS = [
    ("TMixerContractAddr7k2Lp9vR5j3Fq1sD6", "TRON", "TronMix (known tumbler)"),
    ("0xMixerContract4b6d0f3c8a5e2b7d1f4c6a9e", "ETHEREUM", "Generic ETH tumbler"),
]

# ---------------------------------------------------------------------------
# Case 1 - MATCHED. Ethereum. Peel chain -> co-spend cluster -> exchange.
# ---------------------------------------------------------------------------
CASE_88213_TXS = [
    # hop 0: suspect wallet peels off 11 small outflows (peel chain) then routes
    # the bulk of value into three intermediate addresses (fan-out)
    {"tx_hash": "0xaa01", "inputs": ["0x7a3f9c1b4d8e0261f5a3c7b91d4e8f02a3c9e91c"],
     "outputs": [{"address": "0xint1aaaa111111111111111111111111111111", "value": 4.10}],
     "fee": 0.0021, "timestamp": "2026-09-08T02:11:00Z", "hop": 1},
    {"tx_hash": "0xaa02", "inputs": ["0x7a3f9c1b4d8e0261f5a3c7b91d4e8f02a3c9e91c"],
     "outputs": [{"address": "0xint2bbbb222222222222222222222222222222", "value": 3.85}],
     "fee": 0.0019, "timestamp": "2026-09-08T02:14:00Z", "hop": 1},
    {"tx_hash": "0xaa03", "inputs": ["0x7a3f9c1b4d8e0261f5a3c7b91d4e8f02a3c9e91c"],
     "outputs": [{"address": "0xint3cccc333333333333333333333333333333", "value": 3.92}],
     "fee": 0.0018, "timestamp": "2026-09-08T02:19:00Z", "hop": 1},
    # 11 small peel outflows from the suspect wallet, interleaved in the same window
    *[{
        "tx_hash": f"0xpeel{i:02d}", "inputs": ["0x7a3f9c1b4d8e0261f5a3c7b91d4e8f02a3c9e91c"],
        "outputs": [{"address": f"0xpeel_dst_{i:02d}0000000000000000000000000", "value": 0.03 + 0.004 * i}],
        "fee": 0.0004, "timestamp": f"2026-09-08T02:{20 + i}:00Z", "hop": 1,
    } for i in range(11)],
    # hop 2: the three intermediates co-spend into the same downstream cluster tx
    # (shared input signer -> co-spend heuristic, weight 1.0)
    {"tx_hash": "0xbb01",
     "inputs": ["0xint1aaaa111111111111111111111111111111",
                "0xint2bbbb222222222222222222222222222222",
                "0xint3cccc333333333333333333333333333333"],
     "outputs": [{"address": "0xcluster9999999999999999999999999999999", "value": 11.71}],
     "fee": 0.0031, "timestamp": "2026-09-08T05:02:00Z", "hop": 2},
    # hop 3: cluster wallet sweeps to the exchange deposit wallet - this sweep
    # regularity + sender diversity is what the deposit-fingerprint heuristic reads
    {"tx_hash": "0xcc01",
     "inputs": ["0xcluster9999999999999999999999999999999"],
     "outputs": [{"address": "0x9f1c2a7e4b6d0f3c8a5e2b7d1f4c6a9e0b3d5f71", "value": 11.68}],
     "fee": 0.0027, "timestamp": "2026-09-08T11:14:00Z", "hop": 3},
]
CASE_88213_DEPOSIT_STATS = {
    "address": "0x9f1c2a7e4b6d0f3c8a5e2b7d1f4c6a9e0b3d5f71",
    "unique_senders_30d": 3412,
    "sweep_intervals_hours": [6.1, 7.4, 6.8, 8.2, 6.5, 7.1, 6.9, 7.6],  # low CV -> regular -> exchange-like
}
# Cross-case linkage used to be a hardcoded fixture here ("NCRP-71005",
# "NCRP-68894" - two case numbers that never existed anywhere else in
# this system, i.e. a decorative string, not a computation). It's now
# computed for real at trace time by engine/case_graph.py, which finds
# this case shares its downstream cluster wallet
# (0xcluster9999...) with CASE_91442 below - see that case's comment.

# ---------------------------------------------------------------------------
# Case 4 - a second victim whose funds independently route through the
# SAME downstream cluster wallet as case_88213
# (0xcluster9999999999999999999999999999999) before reaching the same
# exchange. Two unrelated NCRP complaints, one shared laundering hub - # exactly the pattern engine/case_graph.py's union-find is meant to
# surface, and the reason CASE_88213's ledger will now show a *real*
# cross-case link instead of the old fixture placeholder.
# ---------------------------------------------------------------------------
CASE_91442_TXS = [
    {"tx_hash": "0xdd01", "inputs": ["0x2b8f1a4c7e9d3061f5a3c7b91d4e8f02a3c9e77b"],
     "outputs": [{"address": "0xcluster9999999999999999999999999999999", "value": 2.15}],
     "fee": 0.0016, "timestamp": "2026-09-10T03:05:00Z", "hop": 1},
    {"tx_hash": "0xdd02", "inputs": ["0xcluster9999999999999999999999999999999"],
     "outputs": [{"address": "0x9f1c2a7e4b6d0f3c8a5e2b7d1f4c6a9e0b3d5f71", "value": 2.10}],
     "fee": 0.0011, "timestamp": "2026-09-10T09:00:00Z", "hop": 2},
]
CASE_91442_DEPOSIT_STATS = None

# ---------------------------------------------------------------------------
# Case 2 - MIXER-BLOCKED. Tron. Path runs through a known tumbler contract.
# ---------------------------------------------------------------------------
CASE_77120_TXS = [
    {"tx_hash": "trx01", "inputs": ["TQn9kx7m2Lp5vR8j3Fq1sD6w4Yb9z0X88vR"],
     "outputs": [{"address": "TIntA1111111111111111111111111111111", "value": 18500.0}],
     "fee": 1.1, "timestamp": "2026-09-09T09:00:00Z", "hop": 1},
    {"tx_hash": "trx02", "inputs": ["TIntA1111111111111111111111111111111"],
     "outputs": [{"address": "TMixerContractAddr7k2Lp9vR5j3Fq1sD6", "value": 18470.0}],
     "fee": 0.9, "timestamp": "2026-09-09T09:22:00Z", "hop": 2},
    # funds re-emerge from the mixer in unlinkable shards - the trail is
    # deliberately not continued past this point; that break IS the point.
    {"tx_hash": "trx03", "inputs": ["TMixerContractAddr7k2Lp9vR5j3Fq1sD6"],
     "outputs": [{"address": "TUnresolvedShard0000000000000000000A", "value": 6100.0},
                 {"address": "TUnresolvedShard0000000000000000000B", "value": 6100.0},
                 {"address": "TUnresolvedShard0000000000000000000C", "value": 6100.0}],
     "fee": 0.7, "timestamp": "2026-09-09T09:40:00Z", "hop": 3},
]
CASE_77120_DEPOSIT_STATS = None  # trail breaks at the mixer - no deposit-side stats to compute

# ---------------------------------------------------------------------------
# Case 3 - CLEARED. Bitcoin. Short trace, dead-ends at an unremarkable wallet.
# ---------------------------------------------------------------------------
CASE_65904_TXS = [
    {"tx_hash": "btc01", "inputs": ["bc1q4x9m2vklp8r5dqzn3w7e6y0c1u9f2a"],
     "outputs": [{"address": "bc1qquietwallet00000000000000000000aa", "value": 0.041}],
     "fee": 0.00004, "timestamp": "2026-09-06T14:02:00Z", "hop": 1},
    {"tx_hash": "btc02", "inputs": ["bc1qquietwallet00000000000000000000aa"],
     "outputs": [{"address": "bc1qmerchantpaymentproc0000000000bb", "value": 0.0405}],
     "fee": 0.00003, "timestamp": "2026-09-07T08:44:00Z", "hop": 2},
    # trail ends at a wallet with no exchange fingerprint, no mixer contact,
    # low sender diversity, irregular timing - nothing to attribute.
]
CASE_65904_DEPOSIT_STATS = {
    "address": "bc1qmerchantpaymentproc0000000000bb",
    "unique_senders_30d": 6,
    "sweep_intervals_hours": [220.0, 41.0, 900.0],  # sparse & irregular -> not exchange-like
}
SEED_CASES = [
    {
        # Traced first so that when case-88213 is traced next, the real
        # cross-case link check (engine/case_graph.py) finds this one
        # already in trace_reports and reports a genuine shared-address
        # match - not a fixture placeholder. See CASE_91442_TXS above.
        "id": "case-91442",
        "ncrp_ref": "NCRP-2026-91442",
        "suspect_wallet": "0x2b8f1a4c7e9d3061f5a3c7b91d4e8f02a3c9e77b",
        "chain": "ETHEREUM",
        "typology": "Investment scam",
        "jurisdiction": "Cyber Crime Cell - Delhi",
        "reported_at": "2026-09-10T02:50:00Z",
        "status": "trace_complete",
        "outcome": "matched",
        "confidence": 0.7,
        "risk_band": "high",
        "demo_fixture": "case_91442",
        "seed_notice": None,
    },
    {
        "id": "case-88213",
        "ncrp_ref": "NCRP-2026-88213",
        "suspect_wallet": "0x7a3f9c1b4d8e0261f5a3c7b91d4e8f02a3c9e91c",
        "chain": "ETHEREUM",
        "typology": "Investment scam",
        "jurisdiction": "Cyber Crime Cell - Delhi",
        "reported_at": "2026-09-08T01:40:00Z",
        "status": "trace_complete",
        "outcome": "matched",
        "confidence": 0.87,
        "risk_band": "high",
        "demo_fixture": "case_88213",
        "seed_notice": None,
    },
    {
        "id": "case-77120",
        "ncrp_ref": "NCRP-2026-77120",
        "suspect_wallet": "TQn9kx7m2Lp5vR8j3Fq1sD6w4Yb9z0X88vR",
        "chain": "TRON",
        "typology": "Task-based fraud",
        "jurisdiction": "Cyber Crime Cell - Delhi",
        "reported_at": "2026-09-09T08:50:00Z",
        "status": "in_progress",
        "outcome": "mixer_blocked",
        "confidence": 0.31,
        "risk_band": "medium",
        "demo_fixture": "case_77120",
        "seed_notice": None,
    },
    {
        "id": "case-65904",
        "ncrp_ref": "NCRP-2026-65904",
        "suspect_wallet": "bc1q4x9m2vklp8r5dqzn3w7e6y0c1u9f2a",
        "chain": "BITCOIN",
        "typology": "Phishing / drainer",
        "jurisdiction": "Cyber Crime Cell - Delhi",
        "reported_at": "2026-09-06T13:55:00Z",
        "status": "cleared",
        "outcome": "cleared",
        "confidence": 0.14,
        "risk_band": "low",
        "demo_fixture": "case_65904",
        "seed_notice": None,
    },
    {
        "id": "case-59117",
        "ncrp_ref": "NCRP-2026-59117",
        "suspect_wallet": "0x1c9d3f7a2b5e8d01c4f6a9b2e5d8f1c4a7b0e123",
        "chain": "ETHEREUM",
        "typology": "Investment scam",
        "jurisdiction": "Cyber Crime Cell - Delhi",
        "reported_at": "2026-09-05T10:00:00Z",
        "status": "notice_issued",
        "outcome": "matched",
        "confidence": 0.91,
        "risk_band": "high",
        "demo_fixture": None,
        "seed_notice": {
            "notice_type": "freeze_102_crpc",
            "exchange_name": "WazirX",
            "status": "acknowledged",
            "body": "To: Nodal Officer, WazirX (Zanmai Labs Pvt Ltd)\nRe: Preservation & freeze request under Section 102 CrPC / 106 BNSS\nCase reference: NCRP-2026-59117\n(auto-generated - see full record in Notices)",
            "created_at": "2026-09-08T10:00:00Z",
            "approved_at": "2026-09-08T12:00:00Z",
            "sent_at": "2026-09-08T12:05:00Z",
            "sla_due": "2026-09-15T12:05:00Z",
        },
    },
    {
        "id": "case-44802",
        "ncrp_ref": "NCRP-2026-44802",
        "suspect_wallet": "TFq8m2vklp5dqzn3w7e6y0c1u9f2a00022cE",
        "chain": "TRON",
        "typology": "Sextortion payment",
        "jurisdiction": "Cyber Crime Cell - Delhi",
        "reported_at": "2026-09-04T09:00:00Z",
        "status": "trace_complete",
        "outcome": "matched",
        "confidence": 0.61,
        "risk_band": "medium",
        "demo_fixture": None,
        "seed_notice": None,
    },
    # ---------------------------------------------------------------------
    # Jurisdiction-diverse seed cases - added for the National Case Map.
    # Same lightweight pattern as case-59117/case-44802 above (demo_fixture:
    # None, so the pipeline is never re-run against these at seed time - # confidence/risk_band are static seed values, not live-computed). This
    # is what gives the map an honest multi-state distribution instead of
    # the demo looking artificially Delhi-only.
    # ---------------------------------------------------------------------
    {
        "id": "case-31287", "ncrp_ref": "NCRP-2026-31287",
        "suspect_wallet": "0x4e8b2f1a9c6d3057e1a3c7b91d4e8f02a3c9e451",
        "chain": "ETHEREUM", "typology": "Investment scam",
        "jurisdiction": "Cyber Crime Cell - Mumbai",
        "reported_at": "2026-09-11T06:20:00Z", "status": "trace_complete", "outcome": "matched",
        "confidence": 0.79, "risk_band": "high", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-30115", "ncrp_ref": "NCRP-2026-30115",
        "suspect_wallet": "TWk3m2vklp5dqzn3w7e6y0c1u9f2a00099bX",
        "chain": "TRON", "typology": "Task-based fraud",
        "jurisdiction": "Cyber Crime Cell - Mumbai",
        "reported_at": "2026-09-13T11:05:00Z", "status": "in_progress", "outcome": None,
        "confidence": 0.44, "risk_band": "medium", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-28940", "ncrp_ref": "NCRP-2026-28940",
        "suspect_wallet": "0x6a1c8d3f2b5e9d04c1f6a9b2e5d8f1c4a7b0e908",
        "chain": "ETHEREUM", "typology": "Pig-butchering",
        "jurisdiction": "Cyber Crime Cell - Bengaluru",
        "reported_at": "2026-09-12T14:40:00Z", "status": "trace_complete", "outcome": "matched",
        "confidence": 0.83, "risk_band": "high", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-27554", "ncrp_ref": "NCRP-2026-27554",
        "suspect_wallet": "bc1q7n2m9vklp8r5dqzn3w7e6y0c1u9f2a7",
        "chain": "BITCOIN", "typology": "Phishing / drainer",
        "jurisdiction": "Cyber Crime Cell - Bengaluru",
        "reported_at": "2026-09-07T09:15:00Z", "status": "cleared", "outcome": "cleared",
        "confidence": 0.09, "risk_band": "low", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-26018", "ncrp_ref": "NCRP-2026-26018",
        "suspect_wallet": "0x2f9c4b1a7e6d3058f1a3c7b91d4e8f02a3c9e772",
        "chain": "ETHEREUM", "typology": "Investment scam",
        "jurisdiction": "Cyber Crime Cell - Hyderabad",
        "reported_at": "2026-09-10T16:00:00Z", "status": "trace_complete", "outcome": "matched",
        "confidence": 0.68, "risk_band": "high", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-24773", "ncrp_ref": "NCRP-2026-24773",
        "suspect_wallet": "TZq1m2vklp5dqzn3w7e6y0c1u9f2a00071fL",
        "chain": "TRON", "typology": "Sextortion payment",
        "jurisdiction": "Cyber Crime Cell - Chennai",
        "reported_at": "2026-09-09T07:30:00Z", "status": "trace_complete", "outcome": "matched",
        "confidence": 0.52, "risk_band": "medium", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-23310", "ncrp_ref": "NCRP-2026-23310",
        "suspect_wallet": "0x8d3f7a2b5e9d04c1f6a9b2e5d8f1c4a7b0e6234c",
        "chain": "ETHEREUM", "typology": "Task-based fraud",
        "jurisdiction": "Cyber Crime Cell - Kolkata",
        "reported_at": "2026-09-06T12:10:00Z", "status": "in_progress", "outcome": None,
        "confidence": 0.37, "risk_band": "medium", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-21987", "ncrp_ref": "NCRP-2026-21987",
        "suspect_wallet": "bc1q3k9m2vklp8r5dqzn3w7e6y0c1u9f2a1",
        "chain": "BITCOIN", "typology": "Investment scam",
        "jurisdiction": "Cyber Crime Cell - Pune",
        "reported_at": "2026-09-05T18:45:00Z", "status": "trace_complete", "outcome": "matched",
        "confidence": 0.71, "risk_band": "high", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-20456", "ncrp_ref": "NCRP-2026-20456",
        "suspect_wallet": "0x9e2b8f1a4c7d3061f5a3c7b91d4e8f02a3c9e365",
        "chain": "ETHEREUM", "typology": "Phishing / drainer",
        "jurisdiction": "Cyber Crime Cell - Ahmedabad",
        "reported_at": "2026-09-03T10:25:00Z", "status": "cleared", "outcome": "cleared",
        "confidence": 0.12, "risk_band": "low", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-19203", "ncrp_ref": "NCRP-2026-19203",
        "suspect_wallet": "TPn8m2vklp5dqzn3w7e6y0c1u9f2a00054dK",
        "chain": "TRON", "typology": "Pig-butchering",
        "jurisdiction": "Cyber Crime Cell - Jaipur",
        "reported_at": "2026-09-08T15:50:00Z", "status": "trace_complete", "outcome": "matched",
        "confidence": 0.59, "risk_band": "medium", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-18077", "ncrp_ref": "NCRP-2026-18077",
        "suspect_wallet": "0x1a7b3f9c2e5d8061f4a3c7b91d4e8f02a3c9e198",
        "chain": "ETHEREUM", "typology": "Investment scam",
        "jurisdiction": "Cyber Crime Cell - Lucknow",
        "reported_at": "2026-09-11T20:10:00Z", "status": "trace_complete", "outcome": "matched",
        "confidence": 0.88, "risk_band": "high", "demo_fixture": None, "seed_notice": None,
    },
    {
        "id": "case-16944", "ncrp_ref": "NCRP-2026-16944",
        "suspect_wallet": "bc1q9p2m2vklp8r5dqzn3w7e6y0c1u9f2a3",
        "chain": "BITCOIN", "typology": "Task-based fraud",
        "jurisdiction": "Cyber Crime Cell - Chandigarh",
        "reported_at": "2026-09-04T13:35:00Z", "status": "in_progress", "outcome": None,
        "confidence": 0.41, "risk_band": "medium", "demo_fixture": None, "seed_notice": None,
    },
]

FIXTURE_MAP = {
    "case_91442": {
        "transactions": CASE_91442_TXS,
        "deposit_stats": CASE_91442_DEPOSIT_STATS,
        "exchange_hit": "0x9f1c2a7e4b6d0f3c8a5e2b7d1f4c6a9e0b3d5f71",
    },
    "case_88213": {
        "transactions": CASE_88213_TXS,
        "deposit_stats": CASE_88213_DEPOSIT_STATS,
        "exchange_hit": "0x9f1c2a7e4b6d0f3c8a5e2b7d1f4c6a9e0b3d5f71",
    },
    "case_77120": {
        "transactions": CASE_77120_TXS,
        "deposit_stats": CASE_77120_DEPOSIT_STATS,
        "exchange_hit": None,
    },
    "case_65904": {
        "transactions": CASE_65904_TXS,
        "deposit_stats": CASE_65904_DEPOSIT_STATS,
        "exchange_hit": None,
    },
}
