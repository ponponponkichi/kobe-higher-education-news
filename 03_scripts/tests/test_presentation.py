import unittest
from datetime import datetime, timedelta, timezone

from news_app.presentation import is_new_article


class NewBadgeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)

    def test_article_within_three_days_is_new(self):
        self.assertTrue(is_new_article(self.now - timedelta(days=2), now=self.now))

    def test_exactly_three_days_is_new(self):
        self.assertTrue(is_new_article(self.now - timedelta(days=3), now=self.now))

    def test_older_than_three_days_is_not_new(self):
        self.assertFalse(
            is_new_article(self.now - timedelta(days=3, seconds=1), now=self.now)
        )

    def test_future_or_missing_date_is_not_new(self):
        self.assertFalse(is_new_article(self.now + timedelta(hours=1), now=self.now))
        self.assertFalse(is_new_article(None, now=self.now))


if __name__ == "__main__":
    unittest.main()