import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.clustering import (
    build_clusters, deposit_fingerprint_score, sender_diversity_zscore,
    cluster_quality_score, UnionFind, _is_round_number, CO_SPEND_WEIGHT,
    CHANGE_ADDRESS_WEIGHT, CLUSTER_SIZE_CAP, DEPOSIT_MIN_UNIQUE_SENDERS,
)


def _tx(tx_hash, ts, inputs, outputs, hop=1):
    return {"tx_hash": tx_hash, "timestamp": ts, "inputs": inputs, "hop": hop,
            "outputs": [{"address": a, "value": v} for a, v in outputs]}


class TestUnionFind(unittest.TestCase):
    def test_find_on_unseen_element_returns_itself(self):
        uf = UnionFind()
        self.assertEqual(uf.find("a"), "a")

    def test_union_makes_two_elements_share_a_root(self):
        uf = UnionFind()
        uf.union("a", "b")
        self.assertEqual(uf.find("a"), uf.find("b"))

    def test_union_is_transitive_across_chain(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("b", "c")
        uf.union("c", "d")
        self.assertEqual(uf.find("a"), uf.find("d"))

    def test_unioning_already_joined_elements_is_a_noop(self):
        uf = UnionFind()
        uf.union("a", "b")
        root_before = uf.find("a")
        uf.union("a", "b")
        self.assertEqual(uf.find("a"), root_before)

    def test_two_separate_groups_stay_separate(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("x", "y")
        self.assertNotEqual(uf.find("a"), uf.find("x"))


class TestIsRoundNumber(unittest.TestCase):
    def test_zero_is_not_round(self):
        self.assertFalse(_is_round_number(0))

    def test_negative_is_not_round(self):
        self.assertFalse(_is_round_number(-5))

    def test_one_is_round(self):
        self.assertTrue(_is_round_number(1.0))

    def test_ten_is_round(self):
        self.assertTrue(_is_round_number(10.0))

    def test_hundred_is_round(self):
        self.assertTrue(_is_round_number(100.0))

    def test_point_one_is_round(self):
        self.assertTrue(_is_round_number(0.1))

    def test_odd_decimal_is_not_round(self):
        self.assertFalse(_is_round_number(3.14159))

    def test_odd_small_decimal_is_not_round(self):
        self.assertFalse(_is_round_number(0.037291))


class TestBuildClusters(unittest.TestCase):
    def test_empty_transactions_returns_empty_clusters(self):
        clusters, events = build_clusters([])
        self.assertEqual(clusters, {})
        self.assertEqual(events, [])

    def test_single_input_single_output_produces_no_co_spend_edge(self):
        txs = [_tx("h1", "2026-01-01T00:00:00Z", ["A"], [("B", 3.14159)])]
        clusters, events = build_clusters(txs)
        co_spend_events = [e for e in events if e["type"] == "co_spend"]
        self.assertEqual(co_spend_events, [])

    def test_co_spend_unions_two_inputs(self):
        txs = [_tx("h1", "2026-01-01T00:00:00Z", ["A", "B"], [("C", 1.0)])]
        clusters, events = build_clusters(txs)
        all_addrs = set()
        for c in clusters.values():
            all_addrs |= c["addresses"]
        self.assertIn("A", all_addrs)
        self.assertIn("B", all_addrs)
        self.assertTrue(any(e["type"] == "co_spend" for e in events))

    def test_co_spend_with_three_inputs_chains_them_together(self):
        txs = [_tx("h1", "2026-01-01T00:00:00Z", ["A", "B", "C"], [("D", 1.0)])]
        clusters, _ = build_clusters(txs)
        roots = {addr: None for addr in ["A", "B", "C"]}
        # all three should end up in the same single cluster
        self.assertEqual(len(clusters), 1)
        only_cluster = next(iter(clusters.values()))
        for a in ["A", "B", "C"]:
            self.assertIn(a, only_cluster["addresses"])

    def test_change_address_heuristic_unions_input_with_novel_nonround_output(self):
        txs = [_tx("h1", "2026-01-01T00:00:00Z", ["A"], [("Z", 3.14159)])]
        clusters, _ = build_clusters(txs)
        self.assertEqual(len(clusters), 1)
        only_cluster = next(iter(clusters.values()))
        self.assertIn("A", only_cluster["addresses"])
        self.assertIn("Z", only_cluster["addresses"])

    def test_change_address_heuristic_skips_round_number_output(self):
        txs = [_tx("h1", "2026-01-01T00:00:00Z", ["A"], [("Z", 5.0)])]
        clusters, _ = build_clusters(txs)
        self.assertEqual(clusters, {})

    def test_change_address_heuristic_skips_already_seen_address(self):
        txs = [
            _tx("h1", "2026-01-01T00:00:00Z", ["X"], [("Z", 3.14159)]),
            _tx("h2", "2026-01-02T00:00:00Z", ["A"], [("Z", 2.71828)]),
        ]
        clusters, _ = build_clusters(txs)
        # Z was already "seen" from h1's output, so h2 should NOT union A with Z
        for c in clusters.values():
            if "A" in c["addresses"]:
                self.assertNotIn("Z", c["addresses"])

    def test_transactions_are_processed_in_timestamp_order_not_list_order(self):
        # h2 (later timestamp) listed first; h1 (earlier) listed second.
        # "seen_before" bookkeeping must follow chronological order.
        txs = [
            _tx("h2", "2026-01-02T00:00:00Z", ["A"], [("Z", 2.71828)]),
            _tx("h1", "2026-01-01T00:00:00Z", ["X"], [("Z", 3.14159)]),
        ]
        clusters, _ = build_clusters(txs)
        for c in clusters.values():
            if "A" in c["addresses"]:
                self.assertNotIn("Z", c["addresses"])

    def test_multi_output_transaction_never_triggers_change_address_heuristic(self):
        txs = [_tx("h1", "2026-01-01T00:00:00Z", ["A"], [("Y", 1.111), ("Z", 2.222)])]
        clusters, _ = build_clusters(txs)
        self.assertEqual(clusters, {})

    def test_cluster_size_cap_flags_oversized_cluster(self):
        txs = []
        addrs = [f"addr{i}" for i in range(CLUSTER_SIZE_CAP + 5)]
        for i in range(len(addrs) - 1):
            txs.append(_tx(f"h{i}", f"2026-01-01T00:{i%60:02d}:00Z", [addrs[i], addrs[i + 1]], [("OUT", 1.0)]))
        clusters, events = build_clusters(txs)
        self.assertTrue(any(e["type"] == "cluster_capped" for e in events))

    def test_edges_carry_the_originating_tx_hash(self):
        txs = [_tx("txhash123", "2026-01-01T00:00:00Z", ["A", "B"], [("C", 1.0)])]
        clusters, _ = build_clusters(txs)
        only_cluster = next(iter(clusters.values()))
        self.assertTrue(any(e["tx_hash"] == "txhash123" for e in only_cluster["edges"]))

    def test_co_spend_edge_weight_matches_constant(self):
        txs = [_tx("h1", "2026-01-01T00:00:00Z", ["A", "B"], [("C", 1.0)])]
        clusters, _ = build_clusters(txs)
        only_cluster = next(iter(clusters.values()))
        co_spend_edges = [e for e in only_cluster["edges"] if e["reason"] == "co_spend"]
        self.assertTrue(all(e["weight"] == CO_SPEND_WEIGHT for e in co_spend_edges))

    def test_change_address_edge_weight_matches_constant(self):
        txs = [_tx("h1", "2026-01-01T00:00:00Z", ["A"], [("Z", 3.14159)])]
        clusters, _ = build_clusters(txs)
        only_cluster = next(iter(clusters.values()))
        change_edges = [e for e in only_cluster["edges"] if e["reason"] == "change_address"]
        self.assertEqual(len(change_edges), 1)
        self.assertEqual(change_edges[0]["weight"], CHANGE_ADDRESS_WEIGHT)


class TestDepositFingerprintScore(unittest.TestCase):
    def test_none_input_returns_zeroed_unmatched_result(self):
        result = deposit_fingerprint_score(None)
        self.assertEqual(result["deposit_fingerprint"], 0.0)
        self.assertEqual(result["sweep_regularity"], 0.0)
        self.assertFalse(result["matched"])
        self.assertIsNone(result["event"])

    def test_high_senders_and_regular_intervals_matches(self):
        stats = {"unique_senders_30d": DEPOSIT_MIN_UNIQUE_SENDERS + 50,
                  "sweep_intervals_hours": [24, 24, 24, 25, 23]}
        result = deposit_fingerprint_score(stats)
        self.assertTrue(result["matched"])
        self.assertIsNotNone(result["event"])

    def test_low_senders_does_not_match_even_with_regular_intervals(self):
        stats = {"unique_senders_30d": 10, "sweep_intervals_hours": [24, 24, 24]}
        result = deposit_fingerprint_score(stats)
        self.assertFalse(result["matched"])

    def test_high_senders_but_irregular_intervals_does_not_match(self):
        stats = {"unique_senders_30d": DEPOSIT_MIN_UNIQUE_SENDERS + 100,
                  "sweep_intervals_hours": [1, 400, 2, 900, 5]}
        result = deposit_fingerprint_score(stats)
        self.assertFalse(result["matched"])

    def test_fewer_than_two_intervals_gives_zero_regularity(self):
        stats = {"unique_senders_30d": 600, "sweep_intervals_hours": [24]}
        result = deposit_fingerprint_score(stats)
        self.assertEqual(result["sweep_regularity"], 0.0)

    def test_empty_intervals_list_gives_zero_regularity(self):
        stats = {"unique_senders_30d": 600, "sweep_intervals_hours": []}
        result = deposit_fingerprint_score(stats)
        self.assertEqual(result["sweep_regularity"], 0.0)

    def test_deposit_fingerprint_saturates_at_one(self):
        stats = {"unique_senders_30d": DEPOSIT_MIN_UNIQUE_SENDERS * 10,
                  "sweep_intervals_hours": [24, 24]}
        result = deposit_fingerprint_score(stats)
        self.assertEqual(result["deposit_fingerprint"], 1.0)

    def test_unique_senders_passed_through_unchanged(self):
        stats = {"unique_senders_30d": 777, "sweep_intervals_hours": [10, 10]}
        result = deposit_fingerprint_score(stats)
        self.assertEqual(result["unique_senders"], 777)


class TestSenderDiversityZscore(unittest.TestCase):
    def test_mean_value_gives_zero_zscore(self):
        self.assertEqual(sender_diversity_zscore(40, population_mean=40, population_stdev=55), 0.0)

    def test_above_mean_gives_positive_zscore(self):
        z = sender_diversity_zscore(95, population_mean=40, population_stdev=55)
        self.assertAlmostEqual(z, 1.0, places=4)

    def test_below_mean_gives_negative_zscore(self):
        z = sender_diversity_zscore(-15, population_mean=40, population_stdev=55)
        self.assertAlmostEqual(z, -1.0, places=4)

    def test_extreme_high_value_clips_at_positive_three(self):
        z = sender_diversity_zscore(100000, population_mean=40, population_stdev=55)
        self.assertEqual(z, 3.0)

    def test_extreme_low_value_clips_at_negative_three(self):
        z = sender_diversity_zscore(-100000, population_mean=40, population_stdev=55)
        self.assertEqual(z, -3.0)

    def test_zero_population_stdev_returns_zero_not_a_crash(self):
        self.assertEqual(sender_diversity_zscore(100, population_mean=40, population_stdev=0), 0.0)


class TestClusterQualityScore(unittest.TestCase):
    def test_empty_clusters_returns_neutral_half(self):
        self.assertEqual(cluster_quality_score({}), 0.5)

    def test_all_singleton_clusters_returns_neutral_half(self):
        clusters = {"root1": {"addresses": {"a"}, "edges": []}}
        self.assertEqual(cluster_quality_score(clusters), 0.5)

    def test_fully_corroborated_chain_scores_near_one(self):
        clusters = {"root1": {"addresses": {"a", "b", "c"},
                               "edges": [{"a": "a", "b": "b"}, {"a": "b", "b": "c"}]}}
        self.assertEqual(cluster_quality_score(clusters), 1.0)

    def test_weakly_evidenced_large_cluster_scores_low(self):
        clusters = {"root1": {"addresses": {"a", "b", "c", "d", "e"}, "edges": [{"a": "a", "b": "b"}]}}
        score = cluster_quality_score(clusters)
        self.assertLess(score, 0.5)

    def test_oversized_cluster_gets_size_penalty(self):
        big_addrs = {f"a{i}" for i in range(CLUSTER_SIZE_CAP + 10)}
        big_edges = [{"a": f"a{i}", "b": f"a{i+1}"} for i in range(CLUSTER_SIZE_CAP + 9)]
        clusters = {"root1": {"addresses": big_addrs, "edges": big_edges}}
        score = cluster_quality_score(clusters)
        # even with a fully-corroborated chain (edge_density==1.0), the
        # 0.4 size penalty must bring this below what an equivalent
        # small fully-corroborated chain would score
        self.assertLess(score, 1.0)

    def test_score_never_goes_negative(self):
        clusters = {"root1": {"addresses": {f"a{i}" for i in range(CLUSTER_SIZE_CAP + 10)}, "edges": []}}
        score = cluster_quality_score(clusters)
        self.assertGreaterEqual(score, 0.0)


if __name__ == "__main__":
    unittest.main()
