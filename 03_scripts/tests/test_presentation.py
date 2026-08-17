import unittest
from datetime import datetime, timedelta, timezone

from news_app.presentation import (
    group_syndicated_articles,
    is_new_article,
    same_syndicated_announcement,
    syndicated_title_key,
)


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


class SyndicatedArticleTests(unittest.TestCase):
    def article(self, title, source, hour=0, url="https://example.com/article"):
        return {
            "title": title,
            "source_name": source,
            "url": url,
            "display_date": datetime(2026, 8, 14, hour, tzinfo=timezone.utc),
            "subject_category": "国立大学関係",
        }

    def test_media_prefix_and_suffix_are_removed_from_key(self):
        left = syndicated_title_key(
            "【岡山大学】岡山大学-信州大学『連携ロボラボ』を共同設置｜Infoseekニュース - Infoseek",
            "Infoseek",
        )
        right = syndicated_title_key(
            "【岡山大学】岡山大学-信州大学『連携ロボラボ』を共同設置 - AGARA紀伊民報",
            "AGARA紀伊民報",
        )
        self.assertEqual(left, right)

    def test_same_announcement_is_grouped_and_all_urls_are_preserved(self):
        articles = [
            self.article(
                "【岡山大学】岡山大学-信州大学『連携ロボラボ』を共同設置｜Infoseekニュース - Infoseek",
                "Infoseek",
                10,
                "https://example.com/infoseek",
            ),
            self.article(
                "【岡山大学】岡山大学-信州大学『連携ロボラボ』を共同設置 - AGARA紀伊民報",
                "AGARA紀伊民報",
                9,
                "https://example.com/agara",
            ),
        ]

        grouped = group_syndicated_articles(articles)

        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["syndicated_count"], 2)
        self.assertEqual(
            {item["url"] for item in grouped[0]["syndicated_articles"]},
            {"https://example.com/infoseek", "https://example.com/agara"},
        )

    def test_different_announcements_are_not_grouped(self):
        left = self.article("岡山大学が研究拠点を共同設置", "媒体A", 10)
        right = self.article("岡山大学が高校生向け講座を開催", "媒体B", 11)
        self.assertFalse(same_syndicated_announcement(left, right))

    def test_different_universities_with_similar_titles_are_not_grouped(self):
        left = self.article(
            "岡山大学が新しい高等教育研究支援センターを設置しました",
            "媒体A",
            10,
        )
        right = self.article(
            "神戸大学が新しい高等教育研究支援センターを設置しました",
            "媒体B",
            11,
        )
        self.assertFalse(same_syndicated_announcement(left, right))
    def test_same_title_more_than_three_days_apart_is_not_grouped(self):
        left = self.article("岡山大学が地域連携シンポジウムを開催", "媒体A")
        right = dict(left)
        right["source_name"] = "媒体B"
        right["display_date"] = left["display_date"] + timedelta(days=4)
        self.assertFalse(same_syndicated_announcement(left, right))

    def test_official_article_is_representative(self):
        press = self.article(
            "神戸大学が新しい高等教育研究の成果を発表しました - 一般ニュース",
            "一般ニュース",
            11,
            "https://example.com/news",
        )
        official = self.article(
            "神戸大学が新しい高等教育研究の成果を発表しました",
            "神戸大学",
            10,
            "https://www.kobe-u.ac.jp/ja/news/article/1",
        )
        grouped = group_syndicated_articles([press, official])
        self.assertEqual(grouped[0]["source_name"], "神戸大学")


if __name__ == "__main__":
    unittest.main()