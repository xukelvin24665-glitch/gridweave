import unittest

from gridweave.benchmark import interval, run_benchmark


class EvidenceTests(unittest.TestCase):
    def test_small_sample_confidence_interval(self):
        result = interval([10, 20, 30])
        self.assertEqual(result["n"], 3)
        self.assertEqual(result["mean"], 20)
        self.assertAlmostEqual(result["ci95_low"], -4.841377, places=5)
        self.assertAlmostEqual(result["ci95_high"], 44.841377, places=5)

    def test_missing_or_single_sample_never_claims_zero_uncertainty(self):
        self.assertIsNone(interval([])["mean"])
        self.assertIsNone(interval([12])["ci95_low"])
        self.assertIsNone(interval([12])["ci95_high"])

    def test_holdout_uses_requested_seed(self):
        report = run_benchmark(seeds=1, kinds=["balanced"], seed_start=100)
        self.assertEqual(report["seed_range"], [100, 100])
        self.assertEqual(report["runs"][0]["seed"], 100)
        self.assertEqual(report["summaries"]["balanced"]["attempted_seeds"], 1)
        self.assertEqual(report["summaries"]["balanced"]["failures"], [])


if __name__ == "__main__":
    unittest.main()
