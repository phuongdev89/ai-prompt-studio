"""Exercise the real image endpoint without provider charges or database writes."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from fastapi.testclient import TestClient
from app.main import app


class ImageGenerationTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "api_key": "test-only", "base_url": "https://provider.invalid/v1",
            "image_model": "test-image", "timeout": 10,
            "image_reference_support": False,
        }
        self.requests = []
        self.responses = []
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        for target, kwargs in [
            ("app.services.image_generator.get_ai_config", {"return_value": self.config}),
            ("app.api.routes.PromptRepository.get_prompt_by_id",
             {"return_value": {"id": "test", "prompt_code": "stored prompt"}}),
            ("app.services.image_generator.urllib.request.urlopen", {"side_effect": self.respond}),
        ]:
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def respond(self, request, **kwargs):
        self.requests.append((request.full_url, json.loads(request.data)))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return io.BytesIO(json.dumps(response).encode())

    def generate(self, **kwargs):
        return self.client.post('/api/prompts/test/generate-image', json={
            "prompt": "draw a cat", "size": "1536x1024", "quality": "high", **kwargs,
        })

    def test_generate_and_regenerate(self):
        for _ in range(2):
            self.responses.append({"data": [{"url": "https://example.invalid/image.png"}]})
            response = self.generate(extra_description="blue background")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["format"], "url")
            url, payload = self.requests[-1]
            self.assertTrue(url.endswith('/images/generations'))
            self.assertEqual(payload["model"], "test-image")
            self.assertEqual(payload["size"], "1536x1024")
            self.assertIn("blue background", payload["prompt"])

    def test_base64_response_and_stored_prompt(self):
        self.responses.append({"data": [{"b64_json": "aW1hZ2U="}]})
        response = self.generate(prompt="")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["image_url"], "data:image/png;base64,aW1hZ2U=")
        self.assertIn("stored prompt", self.requests[0][1]["prompt"])

    def test_reference_via_chat(self):
        self.responses.append({"choices": [{"message": {"content": "![image](https://example.invalid/a.png)"}}]})
        ref = "data:image/png;base64,cmVm"
        response = self.generate(reference_image=ref)
        self.assertEqual(response.status_code, 200, response.text)
        url, payload = self.requests[0]
        self.assertTrue(url.endswith('/chat/completions'))
        self.assertEqual(payload["messages"][1]["content"][1]["image_url"]["url"], ref)

    def test_reference_via_image_endpoint(self):
        self.config["image_reference_support"] = True
        self.responses.append({"data": [{"b64_json": "aW1hZ2U="}]})
        response = self.generate(reference_image="data:image/png;base64,cmVm")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.requests[0][1]["image"], "cmVm")

    def test_text_to_image_fallback(self):
        self.responses.extend([URLError("unsupported"), {"choices": [{"message": {
            "content": "data:image/png;base64,aW1hZ2U="}}]}])
        response = self.generate()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(self.requests[1][0].endswith('/chat/completions'))

    def test_reference_fallback(self):
        self.responses.extend([URLError("unsupported"), {"data": [{"url": "https://example.invalid/a.png"}]}])
        response = self.generate(reference_image="data:image/png;base64,cmVm")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(self.requests[1][0].endswith('/images/generations'))

    def test_missing_key_is_controlled_error(self):
        self.config["api_key"] = ""
        response = self.generate()
        self.assertEqual(response.status_code, 500)
        self.assertIn("API Key", response.json()["detail"])
        self.assertEqual(self.requests, [])

    def test_provider_failure_is_controlled_error(self):
        self.responses.extend([URLError("offline"), URLError("offline")])
        response = self.generate()
        self.assertEqual(response.status_code, 500)
        self.assertIn("offline", response.json()["detail"])


if __name__ == '__main__':
    unittest.main()
