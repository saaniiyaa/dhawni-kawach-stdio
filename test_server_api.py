# test_server_api.py
import os
import json
import unittest
from demo_server import app

class TestDhwaniKavachAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_ping_and_cors(self):
        res = self.client.get('/api/ping')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "ONLINE")
        self.assertEqual(data.get("app"), "DHWANI-KAVACH")
        # Check CORS headers
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("Content-Type", res.headers.get("Access-Control-Allow-Headers", ""))

    def test_reset(self):
        res = self.client.post('/api/reset')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "*")

    def test_context(self):
        res = self.client.post('/api/context', json={
            "number": "+91-140-987654",
            "claims_bank": True
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("level"), "danger")
        self.assertEqual(data.get("trust_score"), 38)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "*")

    def test_actions(self):
        res_oob = self.client.post('/api/action/oob', json={"number": "+91-9876543210"})
        self.assertEqual(res_oob.status_code, 200)
        data_oob = res_oob.get_json()
        self.assertEqual(data_oob.get("status"), "INITIATED")

        res_report = self.client.post('/api/action/report', json={"tier": "CRITICAL"})
        self.assertEqual(res_report.status_code, 200)
        data_report = res_report.get_json()
        self.assertEqual(data_report.get("status"), "DISPATCHED")

    def test_demo_audio(self):
        for kind in ["real", "fake", "my_voice"]:
            res = self.client.get(f'/api/demo_audio/{kind}')
            self.assertEqual(res.status_code, 200, f"Failed for {kind}")
            self.assertTrue(len(res.data) > 1000)

    def test_score_audio_bonafide(self):
        # Reset engine first
        self.client.post('/api/reset')
        with open("results/demo/demo_real_studio.wav", "rb") as fh:
            res = self.client.post('/api/score', data=fh.read(), headers={'Content-Type': 'audio/wav'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertNotIn("error", data)
        self.assertLess(data.get("window_p", 1.0), 0.50)
        self.assertIn(data.get("tier"), ["SAFE", "INSUFFICIENT_AUDIO"])

    def test_score_audio_spoof(self):
        # Reset engine first
        self.client.post('/api/reset')
        with open("results/demo/demo_fake_studio.wav", "rb") as fh:
            res = self.client.post('/api/score', data=fh.read(), headers={'Content-Type': 'audio/wav'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertNotIn("error", data)
        self.assertGreater(data.get("window_p", 0.0), 0.70)

if __name__ == '__main__':
    unittest.main()
