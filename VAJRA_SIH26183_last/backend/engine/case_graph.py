"""
Cross-case link graph - real graph traversal over the cases this cyber
cell actually has, replacing the old hardcoded fixture `linked_cases`
list (which used to point at "NCRP-71005" / "NCRP-68894" - two case
numbers that never existed anywhere else in this system; it was a
decorative string, not a computation).

The Master Document / original roadmap called for Neo4j here ("real-
time cross-case graph queries at scale"). At the data volumes a single
cyber cell actually works with - dozens to low hundreds of open cases,
not millions of nodes - the query that matters is: "find other cases
whose traced fund-flow graph touched an address this case's fund-flow
graph also touched, directly or through a chain of other cases." That
is a plain union-find over each case's address set, which is what this
module does. It is the *same graph query* Neo4j would run; standing up
a separate graph database only earns its keep at cross-jurisdiction
scale (thousands of concurrent cases, sub-second queries across a
national case index) - see docs/BUILT_VS_ROADMAP.md for exactly where
that line is and what the swap looks like when it's crossed.

Pure functions only - no DB connection, no HTTP - so this is unit-
tested directly (see tests/test_case_graph.py), the same convention
engine/exchange_board.py uses for the same reason.
"""
import json
from collections import defaultdict


def extract_addresses(report, exclude=None):
    """
    Every address a trace's fund-flow graph actually touched: the
    suspect wallet plus every input/output address across every traced
    hop. `exclude` is a set of addresses to drop before returning - pass known exchange hot wallets and known mixer contracts here,
    since those are shared infrastructure that thousands of unrelated,
    legitimate cases will also touch. Overlap *there* is not evidence
    of a shared laundering network; overlap at an intermediate wallet
    or cluster address is.
    """
    exclude = exclude or set()
    addrs = set()
    suspect = report.get("suspect_wallet")
    if suspect:
        addrs.add(suspect)
    for tx in report.get("transactions", []) or []:
        for inp in tx.get("inputs", []) or []:
            if inp:
                addrs.add(inp)
        for out in tx.get("outputs", []) or []:
            addr = out.get("address") if isinstance(out, dict) else None
            if addr:
                addrs.add(addr)
    return {a for a in addrs if a not in exclude}


class _UnionFind:
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


def _total_value(report):
    """Sum of every traced transaction's output value, in the case's
    native chain unit. Used by engine/syndicate.py's pooled_value() - kept here since it walks the same report["transactions"] shape
    extract_addresses() already walks. Returns None if no output in the
    report carries a "value" (rather than a misleading 0.0)."""
    total = 0.0
    found_any = False
    for tx in report.get("transactions", []) or []:
        for out in tx.get("outputs", []) or []:
            if isinstance(out, dict) and out.get("value") is not None:
                total += out["value"]
                found_any = True
    return round(total, 4) if found_any else None


def build_case_index(rows, exclude=None):
    """
    rows: iterable of objects with keys/attributes case_id, report_json,
    ncrp_ref, chain, confidence (sqlite3.Row or dict both work - same
    convention as exchange_board.aggregate_exchange_risk). Pass one row
    per case - the caller (server.py) is responsible for picking the
    latest trace_reports version per case before calling this, exactly
    like it already does for the exchange risk board.

    Returns {case_id: {"ncrp_ref", "chain", "confidence", "addresses",
    "total_value"}}. A row with unparseable report_json is skipped, not
    fatal, matching exchange_board's malformed-row handling.
    """
    index = {}
    for r in rows:
        try:
            report = json.loads(r["report_json"])
        except (TypeError, ValueError, KeyError):
            continue
        case_id = r["case_id"]
        index[case_id] = {
            "ncrp_ref": r["ncrp_ref"],
            "chain": r["chain"] if r["chain"] is not None else report.get("chain"),
            "confidence": r["confidence"] if r["confidence"] is not None else report.get("confidence"),
            "addresses": extract_addresses(report, exclude=exclude),
            "total_value": _total_value(report),
        }
    return index


def _pairwise_overlaps(index):
    """{(case_a, case_b): {shared addresses}} for every pair sharing >=1
    address, case ids ordered so each unordered pair appears once."""
    by_address = defaultdict(set)
    for case_id, info in index.items():
        for addr in info["addresses"]:
            by_address[addr].add(case_id)

    overlaps = defaultdict(set)
    for addr, case_ids in by_address.items():
        if len(case_ids) < 2:
            continue
        ids = sorted(case_ids)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                overlaps[(ids[i], ids[j])].add(addr)
    return overlaps


def build_networks(index):
    """
    Connected components of cases linked directly or transitively by at
    least one shared non-infrastructure address. Returns a list of
    networks (largest first), each:
      {"case_ids": [sorted ids], "edges": [{"a","b","shared_addresses"}]}
    A case with no overlap with anything else is not returned - an
    isolated case is not a network.
    """
    overlaps = _pairwise_overlaps(index)
    uf = _UnionFind()
    for case_id in index:
        uf.find(case_id)
    for (a, b) in overlaps:
        uf.union(a, b)

    groups = defaultdict(list)
    for case_id in index:
        groups[uf.find(case_id)].append(case_id)

    networks = []
    for members in groups.values():
        if len(members) < 2:
            continue
        member_set = set(members)
        edges = [
            {"a": a, "b": b, "shared_addresses": sorted(addrs)}
            for (a, b), addrs in overlaps.items()
            if a in member_set and b in member_set
        ]
        networks.append({"case_ids": sorted(members), "edges": edges})
    networks.sort(key=lambda n: len(n["case_ids"]), reverse=True)
    return networks


def linked_cases_for(index, case_id):
    """
    Every other case in the same connected network as `case_id` - direct
    or transitive - each annotated with the addresses it *directly*
    shares with `case_id` (empty list + link_type="transitive" if the
    link only exists through a third case). Direct links sort first,
    then by confidence descending. Returns [] if `case_id` is unknown or
    has no network.
    """
    if case_id not in index:
        return []
    network = next((n for n in build_networks(index) if case_id in n["case_ids"]), None)
    if not network:
        return []

    direct = {}
    for e in network["edges"]:
        if e["a"] == case_id:
            direct[e["b"]] = e["shared_addresses"]
        elif e["b"] == case_id:
            direct[e["a"]] = e["shared_addresses"]

    result = []
    for other_id in network["case_ids"]:
        if other_id == case_id:
            continue
        info = index[other_id]
        result.append({
            "case_id": other_id,
            "ncrp_ref": info["ncrp_ref"],
            "chain": info["chain"],
            "confidence": info["confidence"],
            "shared_addresses": direct.get(other_id, []),
            "link_type": "direct" if other_id in direct else "transitive",
        })
    result.sort(key=lambda r: (r["link_type"] != "direct", -(r["confidence"] or 0)))
    return result


def network_graph(index):
    """
    Full graph payload for the frontend Network view - every non-trivial
    network's nodes and edges in one structure: {"nodes", "edges",
    "network_count"}. Isolated cases (no shared-address link to anything)
    are omitted; they're not part of a network.
    """
    networks = build_networks(index)
    nodes = []
    edges = []
    seen = set()
    for net in networks:
        for cid in net["case_ids"]:
            if cid in seen:
                continue
            seen.add(cid)
            info = index[cid]
            nodes.append({
                "case_id": cid, "ncrp_ref": info["ncrp_ref"],
                "chain": info["chain"], "confidence": info["confidence"],
            })
        for e in net["edges"]:
            edges.append({
                "source": e["a"], "target": e["b"],
                "shared_addresses": e["shared_addresses"],
                "shared_count": len(e["shared_addresses"]),
            })
    return {"nodes": nodes, "edges": edges, "network_count": len(networks)}
