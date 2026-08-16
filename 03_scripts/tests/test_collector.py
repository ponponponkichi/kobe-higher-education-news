import unittest
from unittest.mock import patch

import requests

from news_app.collector import make_article, mext_page_summary


class CollectorTests(unittest.TestCase):
    def test_pr_times_article_is_excluded(self):
        article = make_article(
            title="神戸大学に関するプレスリリース - PR TIMES",
            summary="広告的な配信記事",
            url="https://example.com/press-release",
            source_name="一般ニュース検索",
            publisher_name="PR TIMES",
            source_kind="rss",
            published_at=None,
            targeted_source=False,
        )
        self.assertIsNone(article)

    def test_netorabo_source_is_excluded(self):
        article = make_article(
            title="大学に関する話題",
            summary="記事概要",
            url="https://example.com/netorabo-source",
            source_name="一般ニュース検索",
            publisher_name="ねとらぼ",
            source_kind="rss",
            published_at=None,
            targeted_source=False,
        )
        self.assertIsNone(article)

    def test_netorabo_in_title_is_excluded(self):
        article = make_article(
            title="大学に関する話題 - ねとらぼ",
            summary="記事概要",
            url="https://example.com/netorabo-title",
            source_name="一般ニュース検索",
            publisher_name="Yahoo!ニュース",
            source_kind="rss",
            published_at=None,
            targeted_source=False,
        )
        self.assertIsNone(article)
    @patch(
        "news_app.collector.request_content",
        return_value="""
            <main>
              <p>担当課へのお問い合わせ 電話番号：03-0000-0000</p>
              <p>山田委員、田中委員、鈴木委員、佐藤委員</p>
              <p>こちらのページでは、大学政策に関する会議の開催内容と配付資料を掲載しています。</p>
            </main>
        """,
    )
    def test_mext_summary_skips_contact_and_member_list(self, _request):
        summary = mext_page_summary(
            "https://www.mext.go.jp/example.html",
            "大学政策に関する会議",
        )
        self.assertIn("開催内容と配付資料", summary)
        self.assertNotIn("電話番号", summary)
        self.assertNotIn("山田委員", summary)

    @patch(
        "news_app.collector.request_content",
        side_effect=requests.RequestException("temporary error"),
    )
    def test_mext_summary_has_safe_fallback(self, _request):
        summary = mext_page_summary(
            "https://www.mext.go.jp/example.html",
            "大学分科会を開催しました",
        )
        self.assertIn("文部科学省", summary)
        self.assertIn("大学分科会を開催しました", summary)


if __name__ == "__main__":
    unittest.main()