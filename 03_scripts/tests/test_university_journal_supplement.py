import unittest

from news_app.classifier import title_fingerprint
from supplement_university_journal import merge_feed


def rss_article(title: str, *, fetched_at: str = "2026-08-16T09:00:00+09:00") -> dict:
    return {
        "fingerprint": title_fingerprint(title),
        "title": title,
        "summary": "RSSが配信した概要ですが、公表用には使用しません。",
        "url": "https://univ-journal.jp/123456/",
        "source_name": "大学ジャーナルオンライン",
        "source_kind": "rss",
        "published_at": "2026-08-16T08:00:00+09:00",
        "fetched_at": fetched_at,
        "category": "国立大学関係",
        "relevance_score": 60,
        "kobe_related": 0,
        "is_relevant": 1,
        "paywall_status": "free",
        "search_query": "",
    }


class UniversityJournalSupplementTests(unittest.TestCase):
    def test_new_article_is_added_without_summary(self):
        remote = {"version": 1, "articles": []}
        payload, added = merge_feed(remote, [rss_article("国立大学の新しい取組")])

        self.assertEqual(len(payload["articles"]), 1)
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["summary"], "")
        self.assertEqual(added[0]["summary_policy"], "none")
        self.assertEqual(added[0]["source_name"], "大学ジャーナルオンライン")

    def test_existing_summary_and_first_seen_are_preserved(self):
        item = rss_article("既存の大学ニュース")
        remote_article = {
            "fingerprint": item["fingerprint"],
            "title": item["title"],
            "summary": "以前から公表されている概要",
            "url": "https://news.google.com/old",
            "source_name": "大学ジャーナルオンライン",
            "source_kind": "rss",
            "published_at": item["published_at"],
            "first_seen_at": "2026-08-15T08:00:00+09:00",
            "last_seen_at": "2026-08-15T09:00:00+09:00",
            "category": "国立大学関係",
            "relevance_score": 60,
            "kobe_related": 0,
            "is_relevant": 1,
            "paywall_status": "free",
            "search_query": "",
            "subject_category": "国立大学関係",
            "themes": "",
            "summary_policy": "rss",
        }
        payload, added = merge_feed(
            {"version": 1, "articles": [remote_article]},
            [item],
        )

        self.assertEqual(added, [])
        merged = payload["articles"][0]
        self.assertEqual(merged["summary"], "以前から公表されている概要")
        self.assertEqual(merged["first_seen_at"], "2026-08-15T08:00:00+09:00")
        self.assertEqual(merged["url"], "https://univ-journal.jp/123456/")

    def test_paid_article_is_added_but_irrelevant_article_is_not(self):
        paid = rss_article("大学の会員限定ニュース")
        paid["paywall_status"] = "likely_paid"
        irrelevant = rss_article("大学と関係のないニュース")
        irrelevant["is_relevant"] = 0

        payload, added = merge_feed(
            {"version": 1, "articles": []},
            [paid, irrelevant],
        )

        self.assertEqual(len(payload["articles"]), 1)
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["paywall_status"], "likely_paid")


if __name__ == "__main__":
    unittest.main()
