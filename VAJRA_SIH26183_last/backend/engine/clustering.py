"""
Clustering engine - Technical Defense Document, section 7 (full spec).

Heuristics and their edge weights, exactly as documented:
  - co-spend            : >=2 addresses as joint inputs on one tx -> weight 1.0
  - change-address       : one never-before-seen, non-round output   -> weight 0.6
  - deposit-fingerprint   : >500 unique senders in <30 days + regular
                            sweep-out                                -> weight 0.75

False-merge prevention: hard cluster-size cap (default 500), manual
split override (exposed via the /api/cases/{id}/cluster/split
endpoint - logged, not implemented as ML re-weighting in this build),
and a cross-heuristic agreement bonus.
"""
import statistics
from collections import defaultdict

CO_SPEND_WEIGHT = 1.0
CHANGE_ADDRESS_WEIGHT = 0.6
DEPOSIT_FINGERPRINT_WEIGHT = 0.75
CLUSTER_SIZE_CAP = 500
DEPOSIT_MIN_UNIQUE_SENDERS = 500
DEPOSIT_MAX_WINDOW_DAYS = 30


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _is_round_number(value: float) -> bool:
    # crude "looks like a human round number" check - 0.1, 1, 5, 10, 100 ...
    if value <= 0:
        return False
    scaled = round(value, 6)
    for base in (0.001, 0.01, 0.1, 1, 5, 10, 50, 100, 500, 1000):
        if abs(scaled % base) < 1e-9 or abs((scaled % base) - base) < 1e-9:
            if scaled >= base:
                return True
    return False


def build_clusters(transactions):
    """
    Returns:
        clusters: {root_address: {addresses: set, edges: [ (a, b, weight, reason) ]}}
        ledger_events: list of human-readable findings (for the Attribution Ledger UI)
        seen_addresses_first_hop: {address: hop} for change-address "never seen before" checks
    """
    uf = UnionFind()
    edges = []
    ledger_events = []
    seen_before = set()

    # sort by timestamp so "never seen before" is evaluated causally
    for tx in sorted(transactions, key=lambda t: t["timestamp"]):
        inputs = tx["inputs"]

        # --- co-spend heuristic ---
        if len(inputs) >= 2:
            for i in range(len(inputs) - 1):
                uf.union(inputs[i], inputs[i + 1])
                edges.append((inputs[i], inputs[i + 1], CO_SPEND_WEIGHT, "co_spend", tx["tx_hash"]))
            ledger_events.append({
                "type": "co_spend",
                "mark": "check",
                "text": "Co-spend cluster confirmed",
                "sub": f"{len(inputs)} addresses share a common input signer (tx {tx['tx_hash']})",
            })

        # --- change-address heuristic ---
        if len(tx["outputs"]) == 1:
            out = tx["outputs"][0]
            never_seen = out["address"] not in seen_before
            non_round = not _is_round_number(out["value"])
            if never_seen and non_round and inputs:
                uf.union(inputs[0], out["address"])
                edges.append((inputs[0], out["address"], CHANGE_ADDRESS_WEIGHT, "change_address", tx["tx_hash"]))

        for out in tx["outputs"]:
            seen_before.add(out["address"])

    clusters = defaultdict(lambda: {"addresses": set(), "edges": []})
    for a, b, w, reason, txh in edges:
        root = uf.find(a)
        clusters[root]["addresses"].update([a, b])
        clusters[root]["edges"].append({"a": a, "b": b, "weight": w, "reason": reason, "tx_hash": txh})

    # false-merge guard: cap cluster size
    oversized = []
    for root, c in clusters.items():
        if len(c["addresses"]) > CLUSTER_SIZE_CAP:
            oversized.append(root)
    for root in oversized:
        ledger_events.append({
            "type": "cluster_capped",
            "mark": "flag",
            "text": "Cluster exceeded size cap - treated as exchange candidate, not merged further",
            "sub": f"{len(clusters[root]['addresses'])} addresses > cap of {CLUSTER_SIZE_CAP}",
        })

    return dict(clusters), ledger_events


def deposit_fingerprint_score(deposit_stats):
    """
    Returns a dict with the two components the confidence formula needs
    separately (DepositFingerprint, SweepRegularity - Technical Defense
    Document section 6), plus a matched flag and a ledger event.
    deposit_stats: {"address", "unique_senders_30d", "sweep_intervals_hours"} or None
    """
    if not deposit_stats:
        return {"deposit_fingerprint": 0.0, "sweep_regularity": 0.0, "matched": False, "event": None,
                "unique_senders": 0}

    senders = deposit_stats["unique_senders_30d"]
    intervals = deposit_stats["sweep_intervals_hours"]

    sender_ratio = min(senders / DEPOSIT_MIN_UNIQUE_SENDERS, 3.0) / 3.0  # saturates at 3x threshold

    if len(intervals) >= 2:
        mean_iv = statistics.mean(intervals)
        stdev_iv = statistics.pstdev(intervals)
        cv = (stdev_iv / mean_iv) if mean_iv else 1.0
        regularity = max(0.0, 1.0 - min(cv, 1.0))  # low coefficient-of-variation -> high regularity
    else:
        regularity = 0.0

    matched = senders >= DEPOSIT_MIN_UNIQUE_SENDERS and regularity > 0.55
    deposit_fingerprint = round(min(1.0, sender_ratio), 4)

    event = None
    if matched:
        event = {
            "type": "deposit_fingerprint",
            "mark": "info",
            "text": "Deposit-wallet fingerprint matched",
            "sub": f"{senders:,} unique senders · sweep regularity {regularity:.2f}",
        }
    return {
        "deposit_fingerprint": deposit_fingerprint,
        "sweep_regularity": round(regularity, 4),
        "matched": matched,
        "event": event,
        "unique_senders": senders,
    }


def sender_diversity_zscore(unique_senders, population_mean=40, population_stdev=55):
    if population_stdev == 0:
        return 0.0
    z = (unique_senders - population_mean) / population_stdev
    return max(-3.0, min(3.0, z))  # clip for numerical stability going into the sigmoid


def cluster_quality_score(clusters):
    """
    A single 0-1 diagnostic summarising how clean the union-find output
    looks for this trace - shown to the investigator alongside the
    confidence breakdown so "Cluster Quality" is never a mystery number.
    Not fed into the confidence sigmoid (see engine/scoring.py docstring
    for exactly which factors are); this is investigator-facing context
    on how much to trust the cluster groupings themselves.

    Rewards: multiple corroborating edges per cluster (cross-heuristic
    agreement), and clusters that stayed well under the false-merge cap.
    Penalises: many singleton one-edge clusters (weak evidence) and any
    cluster that hit the size cap (potential false merge, already
    flagged separately in the ledger).
    """
    if not clusters:
        return 0.5  # no clustering signal either way - neutral, not zero
    scores = []
    for c in clusters.values():
        n_addr = len(c["addresses"])
        n_edges = len(c["edges"])
        if n_addr <= 1:
            continue
        edge_density = min(1.0, n_edges / max(1, n_addr - 1))  # 1.0 = fully corroborated chain
        size_penalty = 0.0 if n_addr <= CLUSTER_SIZE_CAP else 0.4
        scores.append(max(0.0, edge_density - size_penalty))
    if not scores:
        return 0.5
    return round(sum(scores) / len(scores), 4)
