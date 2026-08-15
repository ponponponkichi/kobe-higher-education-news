import unittest

from news_app.public_feed import public_summary


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


if __name__ == "__main__":
    unittest.main()
