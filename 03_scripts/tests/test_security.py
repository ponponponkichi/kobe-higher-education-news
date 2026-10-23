import json
import tempfile
import unittest
from pathlib import Path

from news_app.public_feed import read_public_feed
from news_app.security import (
    escape_markdown_text,
    safe_anchor_html,
    safe_external_url,
    safe_text_html,
)


class SecurityTests(unittest.TestCase):
    def test_accepts_absolute_http_and_https_urls(self):
        self.assertEqual(safe_external_url("https://example.com/news?id=1"), "https://example.com/news?id=1")
        self.assertEqual(safe_external_url("http://example.com/news"), "http://example.com/news")

    def test_rejects_non_web_and_relative_urls(self):
        for value in ("javascript:alert(1)", "data:text/html,test", "/relative", "example.com"):
            with self.subTest(value=value):
                self.assertEqual(safe_external_url(value), "")

    def test_rejects_malformed_or_ambiguous_urls(self):
        for value in (
            "https://example.com/a b",
            "https://example.com\\@attacker.example/",
            "https://example.com:bad/",
            "https:///missing-host",
        ):
            with self.subTest(value=value):
                self.assertEqual(safe_external_url(value), "")

    def test_rejects_urls_containing_credentials(self):
        self.assertEqual(safe_external_url("https://user:pass@example.com/news"), "")

    def test_markdown_syntax_is_escaped_and_newlines_are_flattened(self):
        value = "![画像](https://example.com/x)\n# 見出し <b>太字</b>"
        escaped = escape_markdown_text(value)
        self.assertNotIn("\n", escaped)
        self.assertIn(r"\!\[画像\]\(https://example\.com/x\)", escaped)
        self.assertIn(r"\# 見出し \<b\>太字\</b\>", escaped)

    def test_safe_anchor_escapes_external_text_and_attributes(self):
        anchor = safe_anchor_html(
            '<img src=x onerror="alert(1)">',
            'https://example.com/news?a=1&b="quoted"',
        )
        self.assertIn("&lt;img", anchor)
        self.assertIn("&quot;quoted&quot;", anchor)
        self.assertNotIn("<img", anchor)
        self.assertEqual(safe_anchor_html("危険", "javascript:alert(1)"), "")

    def test_safe_text_html_prevents_markup_and_flattens_newlines(self):
        value = '<img src=x onerror="alert(1)">\nwww.example.com'
        escaped = safe_text_html(value)
        self.assertEqual(
            escaped,
            '&lt;img src=x onerror=&quot;alert(1)&quot;&gt; www.example.com',
        )
        self.assertNotIn("<img", escaped)

    def test_read_public_feed_removes_unsafe_existing_url(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "feed.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "articles": [
                            {"fingerprint": "bad", "url": "javascript:alert(1)"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            payload = read_public_feed(path)

        self.assertEqual(payload["articles"][0]["url"], "")


if __name__ == "__main__":
    unittest.main()
