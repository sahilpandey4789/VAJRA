import json
import unittest

from engine import case_graph


def _row(case_id, report, ncrp_ref=None, chain=None, confidence=None):
    """Plain-dict stand-in for a sqlite3.Row - case_graph only ever does
    dict-style [] access, same convention as test_exchange_board.py."""
    return {
        "case_id": case_id,
        "report_json": json.dumps(report),
        "ncrp_ref": ncrp_ref or case_id.upper(),
        "chain": chain or report.get("chain", "ETHEREUM"),
        "confidence": confidence if confidence is not None else report.get("confidence"),
    }


def _report(suspect, addresses, confidence=0.5):
    """A minimal fake report: one tx per extra address so extract_addresses
    picks them all up, plus the suspect wallet itself."""
    txs = [
        {"inputs": [suspect], "outputs": [{"address": a}]}
        for a in addresses
    ]
    return {"suspect_wallet": suspect, "transactions": txs, "confidence": confidence}


class TestExtractAddresses(unittest.TestCase):
    def test_includes_suspect_and_all_hop_addresses(self):
        report = _report("S1", ["A", "B"])
        addrs = case_graph.extract_addresses(report)
        self.assertEqual(addrs, {"S1", "A", "B"})

    def test_excludes_given_addresses(self):
        report = _report("S1", ["A", "EXCHANGE"])
        addrs = case_graph.extract_addresses(report, exclude={"EXCHANGE"})
        self.assertEqual(addrs, {"S1", "A"})

    def test_empty_report_is_not_fatal(self):
        self.assertEqual(case_graph.extract_addresses({}), set())


class TestBuildCaseIndex(unittest.TestCase):
    def test_builds_one_entry_per_case(self):
        rows = [
            _row("c1", _report("S1", ["A"])),
            _row("c2", _report("S2", ["B"])),
        ]
        index = case_graph.build_case_index(rows)
        self.assertEqual(set(index.keys()), {"c1", "c2"})
        self.assertEqual(index["c1"]["addresses"], {"S1", "A"})

    def test_malformed_report_json_is_skipped_not_fatal(self):
        rows = [{"case_id": "bad", "report_json": "{not json", "ncrp_ref": "X", "chain": "ETHEREUM", "confidence": None}]
        self.assertEqual(case_graph.build_case_index(rows), {})


class TestBuildNetworks(unittest.TestCase):
    def test_no_overlap_means_no_networks(self):
        index = case_graph.build_case_index([
            _row("c1", _report("S1", ["A"])),
            _row("c2", _report("S2", ["B"])),
        ])
        self.assertEqual(case_graph.build_networks(index), [])

    def test_direct_overlap_forms_a_network(self):
        index = case_graph.build_case_index([
            _row("c1", _report("S1", ["SHARED"])),
            _row("c2", _report("S2", ["SHARED"])),
        ])
        nets = case_graph.build_networks(index)
        self.assertEqual(len(nets), 1)
        self.assertEqual(nets[0]["case_ids"], ["c1", "c2"])
        self.assertEqual(nets[0]["edges"][0]["shared_addresses"], ["SHARED"])

    def test_transitive_overlap_forms_one_network_of_three(self):
        # c1<->c2 share X, c2<->c3 share Y, c1 and c3 share nothing directly.
        index = case_graph.build_case_index([
            _row("c1", _report("S1", ["X"])),
            _row("c2", _report("S2", ["X", "Y"])),
            _row("c3", _report("S3", ["Y"])),
        ])
        nets = case_graph.build_networks(index)
        self.assertEqual(len(nets), 1)
        self.assertEqual(nets[0]["case_ids"], ["c1", "c2", "c3"])

    def test_known_exchange_wallet_excluded_does_not_falsely_link_cases(self):
        # Both cases end at the same exchange hot wallet - that alone must
        # NOT create a network once it's passed in `exclude`.
        index = case_graph.build_case_index(
            [
                _row("c1", _report("S1", ["EXCHANGE"])),
                _row("c2", _report("S2", ["EXCHANGE"])),
            ],
            exclude={"EXCHANGE"},
        )
        self.assertEqual(case_graph.build_networks(index), [])


class TestLinkedCasesFor(unittest.TestCase):
    def test_unknown_case_returns_empty(self):
        index = case_graph.build_case_index([_row("c1", _report("S1", ["A"]))])
        self.assertEqual(case_graph.linked_cases_for(index, "does-not-exist"), [])

    def test_isolated_case_has_no_links(self):
        index = case_graph.build_case_index([
            _row("c1", _report("S1", ["A"])),
            _row("c2", _report("S2", ["B"])),
        ])
        self.assertEqual(case_graph.linked_cases_for(index, "c1"), [])

    def test_direct_link_reports_shared_addresses(self):
        index = case_graph.build_case_index([
            _row("c1", _report("S1", ["SHARED"]), ncrp_ref="NCRP-1"),
            _row("c2", _report("S2", ["SHARED"]), ncrp_ref="NCRP-2"),
        ])
        linked = case_graph.linked_cases_for(index, "c1")
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]["case_id"], "c2")
        self.assertEqual(linked[0]["ncrp_ref"], "NCRP-2")
        self.assertEqual(linked[0]["shared_addresses"], ["SHARED"])
        self.assertEqual(linked[0]["link_type"], "direct")

    def test_transitive_link_has_no_shared_addresses_but_is_listed(self):
        index = case_graph.build_case_index([
            _row("c1", _report("S1", ["X"])),
            _row("c2", _report("S2", ["X", "Y"])),
            _row("c3", _report("S3", ["Y"])),
        ])
        linked = case_graph.linked_cases_for(index, "c1")
        c3_entry = next(l for l in linked if l["case_id"] == "c3")
        self.assertEqual(c3_entry["shared_addresses"], [])
        self.assertEqual(c3_entry["link_type"], "transitive")

    def test_direct_links_sort_before_transitive(self):
        index = case_graph.build_case_index([
            _row("c1", _report("S1", ["X", "Z"])),
            _row("c2", _report("S2", ["X", "Y"])),
            _row("c3", _report("S3", ["Y"])),      # transitive to c1, direct to c2
            _row("c4", _report("S4", ["Z"])),      # direct to c1
        ])
        linked = case_graph.linked_cases_for(index, "c1")
        self.assertEqual(linked[0]["link_type"], "direct")
        self.assertEqual(linked[1]["link_type"], "direct")
        self.assertEqual(linked[2]["link_type"], "transitive")


class TestNetworkGraph(unittest.TestCase):
    def test_empty_index_gives_empty_graph(self):
        graph = case_graph.network_graph({})
        self.assertEqual(graph, {"nodes": [], "edges": [], "network_count": 0})

    def test_isolated_cases_are_not_included(self):
        index = case_graph.build_case_index([
            _row("c1", _report("S1", ["A"])),
            _row("c2", _report("S2", ["B"])),
        ])
        graph = case_graph.network_graph(index)
        self.assertEqual(graph["nodes"], [])
        self.assertEqual(graph["network_count"], 0)

    def test_linked_cases_appear_as_nodes_and_edges(self):
        index = case_graph.build_case_index([
            _row("c1", _report("S1", ["SHARED"]), ncrp_ref="NCRP-1"),
            _row("c2", _report("S2", ["SHARED"]), ncrp_ref="NCRP-2"),
        ])
        graph = case_graph.network_graph(index)
        self.assertEqual(graph["network_count"], 1)
        self.assertEqual({n["case_id"] for n in graph["nodes"]}, {"c1", "c2"})
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["edges"][0]["shared_count"], 1)


if __name__ == "__main__":
    unittest.main()
