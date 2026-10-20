import json
import tempfile
import unittest
from pathlib import Path

from news_app.public_feed import build_public_feed, public_summary
from news_app.storage import connect, upsert_articles


class PublicSummaryTests(unittest.TestCase):
    def test_official_source_summary_is_kept(self):
        summary, policy = public_summary({"summary": "審議会の開催内容を公開しました。", "source_name": "文部科学省", "source_kind": "rss", "search_query": ""})
        self.assertEqual(summary, "審議会の開催内容を公開しました。")
        self.assertEqual(policy, "official")

    def test_formal_rss_summary_is_kept(self):
        summary, policy = public_summary({"summary": "大学教育に関する公開概要です。", "source_name": "大学ジャーナルオンライン", "source_kind": "rss", "search_query": ""})
        self.assertEqual(summary, "大学教育に関する公開概要です。")
        self.assertEqual(policy, "rss")

    def test_google_news_summary_is_hidden(self):
        summary, policy = public_summary({"summary": "新聞記事の概要文です。", "source_name": "神戸新聞NEXT", "source_kind": "rss", "search_query": '"神戸大学"'})
        self.assertEqual(summary, "")
        self.assertEqual(policy, "hidden_news_search")

    def test_direct_press_summary_is_hidden(self):
        summary, policy = public_summary({"summary": "雑誌記事の概要文です。", "source_name": "週刊大学情報", "source_kind": "rss", "search_query": ""})
        self.assertEqual(summary, "")
        self.assertEqual(policy, "hidden_press")

    def test_likely_paid_article_is_included_in_public_feed(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "news.db"
            output_path = Path(temporary) / "public.json"
            connection = connect(database_path)
            upsert_articles(
                connection,
                [
                    {
                        "fingerprint": "paid-but-relevant",
                        "title": "国立大学の教育改革を解説",
                        "summary": "会員向け記事の概要",
                        "url": "https://example.com/paid",
                        "source_name": "日本経済新聞",
                        "source_kind": "rss",
                        "published_at": "2026-08-16T08:00:00+09:00",
                        "fetched_at": "2026-08-16T09:00:00+09:00",
                        "category": "国立大学関係",
                        "relevance_score": 60,
                        "kobe_related": 0,
                        "is_relevant": 1,
                        "paywall_status": "likely_paid",
                        "search_query": "国立大学",
                    }
                ],
            )
            connection.close()

            payload = build_public_feed(database_path, output_path)

            self.assertEqual(len(payload["articles"]), 1)
            self.assertEqual(payload["articles"][0]["paywall_status"], "likely_paid")
            self.assertEqual(payload["articles"][0]["summary"], "")

    def test_existing_netorabo_source_and_title_are_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "news.db"
            output_path = Path(temporary) / "public.json"
            connection = connect(database_path)
            connection.close()
            output_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "articles": [
                            {
                                "fingerprint": "netorabo-source",
                                "source_name": "ねとらぼ",
                                "title": "大学に関する話題",
                            },
                            {
                                "fingerprint": "netorabo-title",
                                "source_name": "Yahoo!ニュース",
                                "title": "大学に関する話題 - ねとらぼ",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_public_feed(database_path, output_path)

            self.assertEqual(payload["articles"], [])

    def test_existing_nhk_news_article_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "news.db"
            output_path = Path(temporary) / "public.json"
            connection = connect(database_path)
            connection.close()
            output_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "articles": [
                            {
                                "fingerprint": "nhk-news",
                                "source_name": "NHKニュース",
                                "title": "大学に関するニュース",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_public_feed(database_path, output_path)

            self.assertEqual(payload["articles"], [])

    def test_existing_ryukyu_shimpo_article_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "news.db"
            output_path = Path(temporary) / "public.json"
            connection = connect(database_path)
            connection.close()
            output_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "articles": [
                            {
                                "fingerprint": "ryukyu-shimpo",
                                "source_name": "琉球新報デジタル",
                                "title": "大学に関するニュース",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_public_feed(database_path, output_path)

            self.assertEqual(payload["articles"], [])

    def test_existing_infoseek_article_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "news.db"
            output_path = Path(temporary) / "public.json"
            connection = connect(database_path)
            connection.close()
            output_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "articles": [
                            {
                                "fingerprint": "infoseek",
                                "source_name": "Infoseek",
                                "title": "大学に関するニュース｜Infoseekニュース",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_public_feed(database_path, output_path)

            self.assertEqual(payload["articles"], [])

    def test_same_url_preserves_first_seen_and_replaces_old_title_variant(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "news.db"
            output_path = Path(temporary) / "public.json"
            connection = connect(database_path)
            upsert_articles(
                connection,
                [
                    {
                        "fingerprint": "new-title-fingerprint",
                        "title": "同じ記事｜大学ニュースサイト - 大学名",
                        "summary": "公開概要",
                        "url": "https://news.google.com/rss/articles/same-article?oc=5",
                        "source_name": "ニュース検索",
                        "source_kind": "rss",
                        "published_at": "2026-08-25T07:00:00+00:00",
                        "fetched_at": "2026-10-20T01:00:00+00:00",
                        "category": "神戸大学関係",
                        "relevance_score": 100,
                        "kobe_related": 1,
                        "is_relevant": 1,
                        "paywall_status": "unknown",
                        "search_query": "神戸大学",
                    }
                ],
            )
            connection.close()
            output_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "articles": [
                            {
                                "fingerprint": "old-title-fingerprint",
                                "title": "同じ記事 - 大学名",
                                "url": "https://news.google.com/rss/articles/same-article?oc=5",
                                "source_name": "ニュース検索",
                                "source_kind": "rss",
                                "published_at": "2026-08-25T07:00:00+00:00",
                                "first_seen_at": "2026-10-07T01:00:00+00:00",
                                "summary": "",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_public_feed(database_path, output_path)

            self.assertEqual(len(payload["articles"]), 1)
            self.assertEqual(
                payload["articles"][0]["fingerprint"], "new-title-fingerprint"
            )
            self.assertEqual(
                payload["articles"][0]["first_seen_at"],
                "2026-10-07T01:00:00+00:00",
            )

    def test_reused_non_google_news_url_does_not_merge_different_articles(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "news.db"
            output_path = Path(temporary) / "public.json"
            connection = connect(database_path)
            upsert_articles(
                connection,
                [
                    {
                        "fingerprint": "second-notice",
                        "title": "大学教育の同じ案内ページに掲載された2件目",
                        "summary": "2件目の公開概要",
                        "url": "https://example.com/shared-information-page",
                        "source_name": "文部科学省",
                        "source_kind": "rss",
                        "published_at": "2026-10-20T00:00:00+00:00",
                        "fetched_at": "2026-10-20T01:00:00+00:00",
                        "category": "文部科学省関係",
                        "relevance_score": 100,
                        "kobe_related": 0,
                        "is_relevant": 1,
                        "paywall_status": "free",
                        "search_query": "",
                    }
                ],
            )
            connection.close()
            output_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "articles": [
                            {
                                "fingerprint": "first-notice",
                                "title": "大学教育の同じ案内ページに掲載された1件目",
                                "url": "https://example.com/shared-information-page",
                                "source_name": "文部科学省",
                                "source_kind": "rss",
                                "published_at": "2026-10-19T00:00:00+00:00",
                                "first_seen_at": "2026-10-19T01:00:00+00:00",
                                "summary": "1件目の公開概要",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_public_feed(database_path, output_path)

            self.assertEqual(
                {article["fingerprint"] for article in payload["articles"]},
                {"first-notice", "second-notice"},
            )


    def test_existing_niconico_and_table_tennis_articles_are_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "news.db"
            output_path = Path(temporary) / "public.json"
            connection = connect(database_path)
            connection.close()
            output_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "articles": [
                            {
                                "fingerprint": "niconico",
                                "source_name": "ニコニコニュース",
                                "title": "大学に関するニュース",
                            },
                            {
                                "fingerprint": "table-tennis",
                                "source_name": "卓球メディア｜Rallys",
                                "title": "国公立大学卓球大会が開幕",
                            },
                            {
                                "fingerprint": "table-tennis-yahoo",
                                "source_name": "Yahoo!ニュース",
                                "title": "国公立大学卓球大会（Rallys） - Yahoo!ニュース",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_public_feed(database_path, output_path)

            self.assertEqual(payload["articles"], [])

if __name__ == "__main__":
    unittest.main()
