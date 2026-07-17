import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse


class AssistantReplyTests(TestCase):
    def test_assistant_reply_uses_fallback_without_ollama(self):
        response = self.client.post(
            reverse("assistant_reply"),
            data=json.dumps({"question": "How does the ATS report work?"}),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "fallback")
        self.assertIn("report", response.json()["answer"].lower())

    @override_settings(OLLAMA_BASE_URL="https://ollama.example", OLLAMA_MODEL="test-model", OLLAMA_API_KEY="secret")
    @patch("core.views.call_ollama", return_value="Maya answer from Ollama.")
    def test_assistant_reply_can_use_ollama(self, _mock_call):
        response = self.client.post(
            reverse("assistant_reply"),
            data=json.dumps({"question": "Tell me about plans"}),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "ollama")
        self.assertEqual(response.json()["answer"], "Maya answer from Ollama.")
