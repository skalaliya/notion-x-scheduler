import json
import unittest
from unittest.mock import patch

from xquik_poster import build_xquik_payload, post_xquik_tweet


class XquikPosterTests(unittest.TestCase):
    def test_build_payload_maps_reply_id(self):
        payload = build_xquik_payload(
            "account-1",
            "Scheduled post",
            "1900000000000000000",
        )

        self.assertEqual(
            payload,
            {
                "account": "account-1",
                "text": "Scheduled post",
                "reply_to_tweet_id": "1900000000000000000",
            },
        )

    def test_post_xquik_tweet_returns_write_action_id(self):
        captured = {}

        class Response:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return json.dumps({"writeActionId": "wa_123"}).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return Response()

        with patch("urllib.request.urlopen", fake_urlopen):
            result = post_xquik_tweet(
                api_key="test-key",
                account="account-1",
                text="Scheduled post",
                reply_to_id="1900000000000000000",
            )

        self.assertEqual(result, "wa_123")
        self.assertEqual(captured["url"], "https://xquik.com/api/v1/x/tweets")
        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(captured["headers"]["X-api-key"], "test-key")
        self.assertEqual(
            captured["body"],
            {
                "account": "account-1",
                "text": "Scheduled post",
                "reply_to_tweet_id": "1900000000000000000",
            },
        )


if __name__ == "__main__":
    unittest.main()
