import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import ml_model


def _tx(inputs, outputs, fee=0.001, hop=1):
    return {"inputs": inputs, "fee": fee, "hop": hop,
            "outputs": [{"address": a, "value": v} for a, v in outputs]}


class TestWalletFeaturesFromTx(unittest.TestCase):
    def test_no_transactions_gives_all_zero_ish_vector(self):
        feats = ml_model.wallet_features_from_tx("A", [])
        self.assertEqual(len(feats), 8)
        self.assertEqual(feats[0], 0)  # in_degree
        self.assertEqual(feats[1], 0)  # out_degree

    def test_in_degree_counts_outputs_addressed_to_wallet(self):
        txs = [_tx(["X"], [("A", 1.0)]), _tx(["Y"], [("A", 2.0)])]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[0], 2)

    def test_out_degree_counts_txs_where_wallet_is_a_sender(self):
        txs = [_tx(["A"], [("X", 1.0)]), _tx(["A"], [("Y", 1.0)]), _tx(["Z"], [("A", 1.0)])]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[1], 2)

    def test_in_degree_is_capped_at_20(self):
        txs = [_tx(["X"], [("A", 1.0)]) for _ in range(30)]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[0], 20)

    def test_out_degree_is_capped_at_20(self):
        txs = [_tx(["A"], [("X", 1.0)]) for _ in range(30)]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[1], 20)

    def test_avg_fee_ratio_only_counts_txs_where_wallet_is_sender(self):
        txs = [_tx(["A"], [("X", 1.0)], fee=0.1), _tx(["B"], [("A", 1.0)], fee=99.0)]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertAlmostEqual(feats[2], 0.1, places=6)

    def test_avg_fee_ratio_zero_when_wallet_never_sends(self):
        txs = [_tx(["B"], [("A", 1.0)], fee=5.0)]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[2], 0.0)

    def test_avg_fee_ratio_capped_at_5(self):
        txs = [_tx(["A"], [("X", 1.0)], fee=999.0)]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[2], 5.0)

    def test_timing_regularity_high_for_few_hops(self):
        txs = [_tx(["A"], [("X", 1.0)], hop=1)]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[3], 0.7)

    def test_timing_regularity_low_for_many_distinct_hops(self):
        txs = [_tx(["A"], [(f"X{i}", 1.0)], hop=i) for i in range(1, 6)]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[3], 0.4)

    def test_peel_chain_score_rises_with_small_single_output_sends(self):
        txs = [_tx(["A"], [("X", 0.1)]) for _ in range(8)]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[4], 1.0)

    def test_peel_chain_score_zero_when_no_small_single_outputs(self):
        txs = [_tx(["A"], [("X", 5.0), ("Y", 3.0)])]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[4], 0.0)

    def test_mixer_proximity_high_when_output_address_contains_mixer(self):
        txs = [_tx(["A"], [("MixerContract1", 1.0)])]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[5], 1.0)

    def test_mixer_proximity_low_when_no_mixer_in_outputs(self):
        txs = [_tx(["A"], [("NormalWallet", 1.0)])]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[5], 0.05)

    def test_value_zscore_zero_when_no_outputs_at_all(self):
        feats = ml_model.wallet_features_from_tx("A", [])
        self.assertEqual(feats[6], 0.0)

    def test_value_zscore_clipped_to_plus_minus_three(self):
        txs = [_tx(["A"], [("X", 1.0)]), _tx(["A"], [("Y", 1000000.0)])]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertLessEqual(feats[6], 3.0)
        self.assertGreaterEqual(feats[6], -3.0)

    def test_unique_counterparties_counts_distinct_addresses(self):
        txs = [_tx(["A"], [("X", 1.0), ("Y", 1.0)])]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[7], 2)

    def test_unique_counterparties_capped_at_50(self):
        txs = [_tx(["A"], [(f"X{i}", 1.0) for i in range(80)])]
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertEqual(feats[7], 50)

    def test_unique_counterparties_includes_senders_when_wallet_receives(self):
        txs = [_tx(["S1", "S2"], [("A", 1.0)])]
        # note: co-spend inputs both appear as "inputs" list on the tx;
        # when A is a recipient, both senders should count as counterparties
        feats = ml_model.wallet_features_from_tx("A", txs)
        self.assertGreaterEqual(feats[7], 1)


class TestModelMetricsAndInference(unittest.TestCase):
    def test_get_metrics_has_expected_keys(self):
        metrics = ml_model.get_metrics()
        for key in ("auroc", "precision", "recall", "n_train", "n_test"):
            self.assertIn(key, metrics)

    def test_auroc_is_a_plausible_probability_like_value(self):
        metrics = ml_model.get_metrics()
        self.assertGreaterEqual(metrics["auroc"], 0.0)
        self.assertLessEqual(metrics["auroc"], 1.0)

    def test_predict_illicit_probability_returns_value_in_unit_interval(self):
        feats = [1, 6, 0.2, 0.3, 0.9, 0.8, 1.5, 3]  # illicit-shaped
        p = ml_model.predict_illicit_probability(feats)
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)

    def test_illicit_shaped_features_score_higher_than_licit_shaped(self):
        illicit_shaped = [1, 6, 0.2, 0.3, 0.9, 0.8, 1.5, 3]
        licit_shaped = [4, 3, 0.4, 0.8, 0.1, 0.05, 0.0, 8]
        p_illicit = ml_model.predict_illicit_probability(illicit_shaped)
        p_licit = ml_model.predict_illicit_probability(licit_shaped)
        self.assertGreater(p_illicit, p_licit)

    def test_get_elliptic_benchmark_returns_none_or_dict(self):
        result = ml_model.get_elliptic_benchmark()
        self.assertTrue(result is None or isinstance(result, dict))


class TestExplainPrediction(unittest.TestCase):
    def test_returns_top_n_entries(self):
        feats = [1, 6, 0.2, 0.3, 0.9, 0.8, 1.5, 3]
        result = ml_model.explain_prediction(feats, top_n=3)
        self.assertEqual(len(result), 3)

    def test_default_top_n_is_five(self):
        feats = [1, 6, 0.2, 0.3, 0.9, 0.8, 1.5, 3]
        result = ml_model.explain_prediction(feats)
        self.assertEqual(len(result), 5)

    def test_entries_sorted_by_descending_magnitude(self):
        feats = [1, 6, 0.2, 0.3, 0.9, 0.8, 1.5, 3]
        result = ml_model.explain_prediction(feats, top_n=8)
        magnitudes = [c["magnitude"] for c in result]
        self.assertEqual(magnitudes, sorted(magnitudes, reverse=True))

    def test_each_entry_has_expected_keys(self):
        feats = [1, 6, 0.2, 0.3, 0.9, 0.8, 1.5, 3]
        result = ml_model.explain_prediction(feats, top_n=1)
        for key in ("feature", "direction", "magnitude", "reason"):
            self.assertIn(key, result[0])

    def test_direction_is_plus_or_minus(self):
        feats = [1, 6, 0.2, 0.3, 0.9, 0.8, 1.5, 3]
        result = ml_model.explain_prediction(feats, top_n=8)
        for c in result:
            self.assertIn(c["direction"], ("+", "-"))

    def test_feature_names_are_from_the_known_schema(self):
        feats = [1, 6, 0.2, 0.3, 0.9, 0.8, 1.5, 3]
        result = ml_model.explain_prediction(feats, top_n=8)
        for c in result:
            self.assertIn(c["feature"], ml_model.FEATURE_NAMES)

    def test_asking_for_more_than_available_returns_all_features(self):
        feats = [1, 6, 0.2, 0.3, 0.9, 0.8, 1.5, 3]
        result = ml_model.explain_prediction(feats, top_n=999)
        self.assertEqual(len(result), len(ml_model.FEATURE_NAMES))


if __name__ == "__main__":
    unittest.main()
