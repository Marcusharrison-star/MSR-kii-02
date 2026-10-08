import io
import math
import unittest
import pandas as pd
import sys
import os

# Ensure project modules are importable
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
api_dir = os.path.join(project_root, "api")
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

try:
    from api.analysis import analyze_genetic_bottleneck, AnalysisValidationError, is_blank_call, sanitize_allele
except ImportError:
    from analysis import analyze_genetic_bottleneck, AnalysisValidationError, is_blank_call, sanitize_allele


class TestEcoGenAnalysis(unittest.TestCase):
    """Unit tests for EcoGen Diagnostics population genetics calculations and validations."""

    def test_blank_call_detection(self):
        """Verify is_blank_call correctly identifies missing vs valid allele calls."""
        self.assertTrue(is_blank_call(None))
        self.assertTrue(is_blank_call(float('nan')))
        self.assertTrue(is_blank_call(""))
        self.assertTrue(is_blank_call("   "))
        self.assertTrue(is_blank_call("NA"))
        self.assertTrue(is_blank_call("na"))
        self.assertTrue(is_blank_call("NaN"))
        self.assertTrue(is_blank_call("null"))
        self.assertTrue(is_blank_call("."))
        self.assertTrue(is_blank_call("-9"))

        self.assertFalse(is_blank_call("142"))
        self.assertFalse(is_blank_call("0"))
        self.assertFalse(is_blank_call("A"))

    def test_sanitize_allele(self):
        """Verify allele labels are treated categorically and trailing float artifacts stripped."""
        self.assertEqual(sanitize_allele("142"), "142")
        self.assertEqual(sanitize_allele(" 150 "), "150")
        self.assertEqual(sanitize_allele("142.0"), "142")
        self.assertEqual(sanitize_allele("Allele_A"), "Allele_A")

    def test_reference_acceptance_dataset(self):
        """
        Verify the expected summary for a 30-sample, 5-locus population:
        - Ho: 0.3600
        - He: 0.5396
        - Fis: 0.3328
        - Samples: 30
        - Loci: 5
        - Status: WARNING
        """
        # Construct synthetic dataset with exact reference statistical properties:
        # 4 loci with allele partition [36, 14, 8, 1, 1] (sum sq = 1558, He = 1 - 1558/3600 = 0.567222...) and 11 hets each
        # 1 locus with allele partition [44, 10, 4, 2] (sum sq = 2056, He = 1 - 2056/3600 = 0.428888...) and 10 hets
        # Mean He = (4 * 0.5672222... + 0.4288888...) / 5 = 0.5395555... -> 0.5396
        # Total hets = 11*4 + 10 = 54. Mean Ho = 54 / 150 = 0.3600
        # Fis = (0.5395555... - 0.36) / 0.5395555... = 0.3327845... -> 0.3328

        # Locus 1-4 generator:
        # Alleles: 36 of '100', 14 of '102', 8 of '104', 1 of '106', 1 of '108'
        # 19 homozygotes: 14 (100, 100), 3 (102, 102), 2 (104, 104) -> 28 '100', 6 '102', 4 '104'
        # 11 heterozygotes using remaining: 8 '100', 8 '102', 4 '104', 1 '106', 1 '108'
        locus1_4_pairs = (
            [("100", "100")] * 14 +
            [("102", "102")] * 3 +
            [("104", "104")] * 2 +
            [
                ("100", "102"), ("100", "102"), ("100", "102"), ("100", "102"),
                ("100", "102"), ("100", "102"), ("100", "102"), ("100", "102"),
                ("104", "106"), ("104", "108"), ("104", "104") # wait: ("104","104") is hom, let's fix hets:
            ]
        )
        # Let's cleanly construct exact genotypes:
        def build_locus1_pairs():
            # 19 homozygotes:
            # 14 '100'x'100' (28 '100'), 3 '102'x'102' (6 '102'), 2 '104'x'104' (4 '104')
            homs = [("100", "100")] * 14 + [("102", "102")] * 3 + [("104", "104")] * 2
            # 11 hets:
            # Remaining: 8 '100', 8 '102', 4 '104', 1 '106', 1 '108' (total 22 alleles)
            hets = [
                ("100", "102"), ("100", "102"), ("100", "102"), ("100", "102"),
                ("100", "102"), ("100", "102"), ("100", "102"), ("100", "104"),
                ("104", "102"), ("104", "106"), ("104", "108")
            ]
            return homs + hets

        def build_locus5_pairs():
            # Partition: 44 of '200', 10 of '202', 4 of '204', 2 of '206'
            # 20 homozygotes: 19 '200'x'200' (38 '200'), 1 '202'x'202' (2 '202')
            homs = [("200", "200")] * 19 + [("202", "202")] * 1
            # 10 hets:
            # Remaining: 6 '200', 8 '202', 4 '204', 2 '206' (total 20 alleles)
            hets = [
                ("200", "202"), ("200", "202"), ("200", "202"), ("200", "202"),
                ("200", "202"), ("200", "202"),
                ("202", "204"), ("202", "204"),
                ("204", "206"), ("204", "206")
            ]
            return homs + hets

        data = {
            "Individual_ID": [f"Ind_{i+1:02d}" for i in range(30)],
            "Locus1_A1": [p[0] for p in build_locus1_pairs()],
            "Locus1_A2": [p[1] for p in build_locus1_pairs()],
            "Locus2_A1": [p[0] for p in build_locus1_pairs()],
            "Locus2_A2": [p[1] for p in build_locus1_pairs()],
            "Locus3_A1": [p[0] for p in build_locus1_pairs()],
            "Locus3_A2": [p[1] for p in build_locus1_pairs()],
            "Locus4_A1": [p[0] for p in build_locus1_pairs()],
            "Locus4_A2": [p[1] for p in build_locus1_pairs()],
            "Locus5_A1": [p[0] for p in build_locus5_pairs()],
            "Locus5_A2": [p[1] for p in build_locus5_pairs()],
        }
        df = pd.DataFrame(data)
        res = analyze_genetic_bottleneck(df)

        self.assertEqual(res["status"], "WARNING")
        self.assertEqual(res["color"], "yellow")
        self.assertEqual(res["summary"]["sample_count"], 30)
        self.assertEqual(res["summary"]["locus_count"], 5)
        self.assertAlmostEqual(res["summary"]["ho"], 0.3600, places=4)
        self.assertAlmostEqual(res["summary"]["he"], 0.5396, places=4)
        self.assertAlmostEqual(res["summary"]["fis"], 0.3328, places=4)

    def test_missing_call_pairwise_omission(self):
        """Verify incomplete genotype pairs are omitted per-locus without dropping valid calls from other loci."""
        csv_data = """Individual_ID,Locus1_A1,Locus1_A2,Locus2_A1,Locus2_A2
Ind_1,100,102,200,200
Ind_2,100,NA,200,202
Ind_3,100,100,200,202
Ind_4,102,102,NA,202
"""
        df = pd.read_csv(io.StringIO(csv_data), dtype=str)
        res = analyze_genetic_bottleneck(df)

        # Locus1 has 3 valid samples: Ind_1 (100,102 het), Ind_3 (100,100 hom), Ind_4 (102,102 hom)
        # Ho for Locus1 = 1 / 3 = 0.3333
        # Locus2 has 3 valid samples: Ind_1 (200,200 hom), Ind_2 (200,202 het), Ind_3 (200,202 het)
        # Ho for Locus2 = 2 / 3 = 0.6667
        self.assertEqual(res["summary"]["sample_count"], 4)
        self.assertEqual(res["summary"]["locus_count"], 2)
        locus1 = next(l for l in res["loci"] if l["locus"] == "Locus1")
        locus2 = next(l for l in res["loci"] if l["locus"] == "Locus2")
        self.assertEqual(locus1["samples_analyzed"], 3)
        self.assertEqual(locus1["missing_count"], 1)
        self.assertEqual(locus2["samples_analyzed"], 3)
        self.assertEqual(locus2["missing_count"], 1)

    def test_empty_locus_error(self):
        """Verify that a locus with 0 complete genotype calls raises a 400 error."""
        csv_data = """Individual_ID,Locus1_A1,Locus1_A2,Locus2_A1,Locus2_A2
Ind_1,100,102,NA,NA
Ind_2,100,100,NA,200
Ind_3,102,102,,
"""
        df = pd.read_csv(io.StringIO(csv_data), dtype=str)
        with self.assertRaises(AnalysisValidationError) as ctx:
            analyze_genetic_bottleneck(df)
        self.assertIn("no complete genotype calls", str(ctx.exception).lower())

    def test_missing_partner_column_error(self):
        """Verify that a missing partner column (e.g. Locus1_A1 without Locus1_A2) is rejected."""
        csv_data = """Individual_ID,Locus1_A1,Locus2_A1,Locus2_A2
Ind_1,100,200,200
Ind_2,102,200,202
"""
        df = pd.read_csv(io.StringIO(csv_data), dtype=str)
        with self.assertRaises(AnalysisValidationError) as ctx:
            analyze_genetic_bottleneck(df)
        self.assertIn("missing required partner column", str(ctx.exception).lower())

    def test_no_locus_columns_error(self):
        """Verify error when no locus pairs exist."""
        csv_data = """Individual_ID,Age,Population
Ind_1,25,North
Ind_2,30,South
"""
        df = pd.read_csv(io.StringIO(csv_data), dtype=str)
        with self.assertRaises(AnalysisValidationError) as ctx:
            analyze_genetic_bottleneck(df)
        self.assertIn("no valid locus columns found", str(ctx.exception).lower())

    def test_empty_dataframe_error(self):
        """Verify empty dataframe is rejected."""
        df = pd.DataFrame()
        with self.assertRaises(AnalysisValidationError):
            analyze_genetic_bottleneck(df)

    def test_bottleneck_critical_classification(self):
        """Verify Ho > He produces CRITICAL status (red)."""
        # Create a population with extreme heterozygote excess
        # 10 individuals, all heterozygous (100, 102)
        # Ho = 1.0. Allele frequencies: p_100 = 0.5, p_102 = 0.5. He = 1 - (0.25 + 0.25) = 0.5.
        # Ho (1.0) > He (0.5) => CRITICAL
        data = {
            "Individual_ID": [f"Ind_{i}" for i in range(10)],
            "Locus1_A1": ["100"] * 10,
            "Locus1_A2": ["102"] * 10,
        }
        df = pd.DataFrame(data)
        res = analyze_genetic_bottleneck(df)
        self.assertEqual(res["status"], "CRITICAL")
        self.assertEqual(res["color"], "red")
        self.assertIn("Ho > He", res["verdict"])
        self.assertAlmostEqual(res["summary"]["ho"], 1.0, places=4)
        self.assertAlmostEqual(res["summary"]["he"], 0.5, places=4)

    def test_stable_classification(self):
        """Verify HWE population produces STABLE status (green)."""
        # Hardy Weinberg proportions: p = 0.5, q = 0.5
        # Expected: 25% AA, 50% Aa, 25% aa
        # For 20 individuals: 5 (100, 100), 10 (100, 102), 5 (102, 102)
        # Ho = 10 / 20 = 0.5. Pooled alleles: 20 of '100', 20 of '102'. p = 0.5, q = 0.5.
        # He = 1 - (0.25 + 0.25) = 0.5.
        # Fis = (0.5 - 0.5) / 0.5 = 0.0 <= 0.15.
        # Ho <= He and Fis <= 0.15 => STABLE
        pairs = [("100", "100")] * 5 + [("100", "102")] * 10 + [("102", "102")] * 5
        data = {
            "Individual_ID": [f"Ind_{i}" for i in range(20)],
            "Locus1_A1": [p[0] for p in pairs],
            "Locus1_A2": [p[1] for p in pairs],
        }
        df = pd.DataFrame(data)
        res = analyze_genetic_bottleneck(df)
        self.assertEqual(res["status"], "STABLE")
        self.assertEqual(res["color"], "green")
        self.assertAlmostEqual(res["summary"]["fis"], 0.0, places=4)

    def test_monomorphic_locus_fis_null(self):
        """Verify that when He == 0, Fis is returned as None (JSON null) and displayed as N/A."""
        data = {
            "Individual_ID": [f"Ind_{i}" for i in range(10)],
            "Locus1_A1": ["100"] * 10,
            "Locus1_A2": ["100"] * 10,
        }
        df = pd.DataFrame(data)
        res = analyze_genetic_bottleneck(df)
        self.assertIsNone(res["summary"]["fis"])
        self.assertEqual(res["summary"]["fis_display"], "N/A")
        self.assertEqual(res["status"], "STABLE")


if __name__ == "__main__":
    unittest.main()
