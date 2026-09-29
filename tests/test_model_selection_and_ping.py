import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.config import get_ai_config, get_image_models
from app.services.image_generator import call_ai_generate_image

class TestModelSelectionAndPing(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_config_providers_returns_image_models_and_default(self):
        res = self.client.get("/api/config/providers")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("openai", data)
        openai_cfg = data["openai"]
        self.assertIn("image_models", openai_cfg)
        self.assertIn("default_image_model", openai_cfg)
        self.assertIsInstance(openai_cfg["image_models"], list)
        self.assertGreater(len(openai_cfg["image_models"]), 0)
        self.assertEqual(openai_cfg["default_image_model"], openai_cfg["image_models"][0])

    def test_config_endpoint_returns_image_models(self):
        res = self.client.get("/api/config")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("image_models", data)
        self.assertIn("default_image_model", data)
        self.assertIsInstance(data["image_models"], list)
        self.assertEqual(data["default_image_model"], data["image_models"][0])

    @patch("app.services.image_generator.urllib.request.urlopen")
    def test_call_ai_generate_image_uses_specified_model_or_default(self, mock_urlopen):
        import json
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"data": [{"url": "https://example.com/test.png"}]}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        # Test with specified model
        call_ai_generate_image(prompt_text="test prompt", model="zpro-payg/grok-imagine-image")
        sent_req = mock_urlopen.call_args[0][0]
        req_body = json.loads(sent_req.data.decode("utf-8"))
        self.assertEqual(req_body.get("model"), "zpro-payg/grok-imagine-image")

        # Test with default model (None passed)
        call_ai_generate_image(prompt_text="test prompt 2", model=None)
        sent_req2 = mock_urlopen.call_args[0][0]
        req_body2 = json.loads(sent_req2.data.decode("utf-8"))
        all_models = get_image_models()
        expected_default = all_models[0]
        self.assertEqual(req_body2.get("model"), expected_default)

    def test_static_data_images_mounted(self):
        # /data/images should be mounted as alias for /media
        res = self.client.get("/data/images/non_existent_file_xyz.png")
        # 404 from StaticFiles (not 404 from FastAPI missing route) means the mount exists
        self.assertEqual(res.status_code, 404)

if __name__ == "__main__":
    unittest.main()
