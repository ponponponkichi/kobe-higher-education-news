import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from news_app.email_digest import (
    MailSettings,
    build_message,
    read_json,
    select_digest_articles,
    send_message,
    write_success_state,
)
from news_app.taxonomy import (
    SUBJECT_KOBE,
    SUBJECT_MEXT,
    SUBJECT_NATIONAL,
    SUBJECT_OTHER,
)


NOW = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc)


def article(fingerprint, subject, first_seen_at, **overrides):
    value = {
        "fingerprint": fingerprint,
        "title": f"記事 {fingerprint}",
        "summary": "公開してよい概要です。",
        "url": f"https://example.com/{fingerprint}",
        "source_name": "テスト媒体",
        "published_at": first_seen_at,
        "first_seen_at": first_seen_at,
        "subject_category": subject,
    }
    value.update(overrides)
    return value


class EmailDigestTests(unittest.TestCase):
    def test_broken_json_stops_instead_of_advancing_delivery_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broken.json"
            path.write_text("{broken", encoding="utf-8")

            with self.assertRaises(json.JSONDecodeError):
                read_json(path, {})

    def test_first_send_uses_last_24_hours_and_three_subjects_only(self):
        feed = {
            "articles": [
                article("kobe", SUBJECT_KOBE, "2026-10-15T12:00:00+00:00"),
                article("mext", SUBJECT_MEXT, "2026-10-15T13:00:00+00:00"),
                article("national", SUBJECT_NATIONAL, "2026-10-15T14:00:00+00:00"),
                article("other", SUBJECT_OTHER, "2026-10-15T15:00:00+00:00"),
                article("old", SUBJECT_KOBE, "2026-10-14T23:59:59+00:00"),
            ]
        }

        window_start, selected = select_digest_articles(feed, {}, now=NOW)

        self.assertEqual(window_start.isoformat(), "2026-10-15T00:00:00+00:00")
        self.assertEqual(
            {item["fingerprint"] for item in selected},
            {"kobe", "mext", "national"},
        )

    def test_later_send_uses_last_successful_send_time(self):
        state = {"last_successful_send_at": "2026-10-15T18:00:00+00:00"}
        feed = {
            "articles": [
                article("before", SUBJECT_KOBE, "2026-10-15T17:59:59+00:00"),
                article("after", SUBJECT_KOBE, "2026-10-15T18:00:01+00:00"),
            ]
        }

        _, selected = select_digest_articles(feed, state, now=NOW)

        self.assertEqual([item["fingerprint"] for item in selected], ["after"])

    def test_message_has_plain_and_html_parts_and_escapes_html(self):
        settings = MailSettings(
            sender="sender@example.com",
            app_password="secret",
            recipients=("group@example.com",),
        )
        news = [
            article(
                "unsafe",
                SUBJECT_KOBE,
                "2026-10-15T20:00:00+00:00",
                title="大学ニュース <script>alert(1)</script>",
            )
        ]

        message = build_message(
            settings,
            news,
            window_start=NOW,
            now=NOW,
        )

        self.assertIn("新着1件", message["Subject"])
        self.assertIn(
            "大学ニュース <script>",
            message.get_body(("plain",)).get_content(),
        )
        html_body = message.get_body(("html",)).get_content()
        self.assertIn("&lt;script&gt;", html_body)
        self.assertNotIn("<script>", html_body)

    @patch("news_app.email_digest.smtplib.SMTP")
    def test_gmail_login_and_send(self, smtp_connection):
        smtp = MagicMock()
        smtp_connection.return_value.__enter__.return_value = smtp
        settings = MailSettings(
            sender="sender@example.com",
            app_password="app-password",
            recipients=("group@example.com",),
        )
        message = build_message(settings, [], window_start=NOW, now=NOW)

        send_message(settings, message)

        smtp_connection.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("sender@example.com", "app-password")
        smtp.send_message.assert_called_once_with(message)

    def test_success_state_contains_no_address_or_password(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"

            write_success_state(path, now=NOW, article_count=3)

            text = path.read_text(encoding="utf-8")
            payload = json.loads(text)
            self.assertEqual(payload["last_article_count"], 3)
            self.assertEqual(payload["last_successful_send_at"], NOW.isoformat())
            self.assertNotIn("address", text)
            self.assertNotIn("password", text)


if __name__ == "__main__":
    unittest.main()
