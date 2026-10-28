import unittest
from ml.engine.voiceprint_falak import scan

class TestVoiceprintPillars(unittest.TestCase):
    def test_single_isolated_keyword_never_triggers_high_risk(self):
        # 1 isolated authority word: "police station"
        res = scan("I am walking past the local police station.")
        self.assertLessEqual(res['score'], 25, "Isolated authority word should not exceed 25% risk")
        self.assertEqual(res['level'], "LOW")
        self.assertEqual(res['pillar_count'], 1)

        # 1 isolated financial phrase: "send money"
        res2 = scan("Can you send money for tonight's grocery shopping?")
        self.assertLessEqual(res2['score'], 25, "Isolated financial phrase should not exceed 25% risk")
        self.assertEqual(res2['level'], "LOW")
        self.assertEqual(res2['pillar_count'], 1)

        # Completely clean benign sentence
        res3 = scan("Hello, hope you are having a wonderful day.")
        self.assertEqual(res3['score'], 0)
        self.assertEqual(res3['level'], "LOW")
        self.assertEqual(res3['pillar_count'], 0)

    def test_two_intersecting_pillars_escalates(self):
        # Authority + Coercion
        res = scan("CBI officer here. Non-bailable arrest warrant has been issued against you.")
        self.assertGreaterEqual(res['score'], 60, "Two intersecting pillars should escalate threat")
        self.assertIn(res['level'], ["MEDIUM", "HIGH"])
        self.assertEqual(res['pillar_count'], 2)

    def test_three_intersecting_pillars_triggers_critical_threat(self):
        # Authority + Coercion + Financial Urgency
        res = scan("This is CBI Cyber Cell. You are under Digital Arrest. Transfer 50,000 to RBI escrow account immediately.")
        self.assertGreaterEqual(res['score'], 80, "Three intersecting pillars must trigger critical threat")
        self.assertEqual(res['level'], "HIGH")
        self.assertEqual(res['coercion_intent'], "SEVERE")
        self.assertEqual(res['pillar_count'], 3)

if __name__ == '__main__':
    unittest.main()
