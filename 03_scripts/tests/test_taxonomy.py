import tempfile
import unittest
from pathlib import Path

from news_app.storage import connect, ensure_current_subject_themes, upsert_articles
from news_app.taxonomy import (
    SUBJECT_KOBE,
    SUBJECT_MEXT,
    SUBJECT_NATIONAL,
    SUBJECT_OTHER,
    THEME_EDUCATION,
    THEME_EVALUATION,
    THEME_RESEARCH,
    THEME_STUDENT_CAREER,
    classify_subject_and_themes,
)


class SubjectThemeTests(unittest.TestCase):
    def test_niad_evaluation_is_other_subject(self):
        result = classify_subject_and_themes(
            "大学機関別認証評価の評価結果を公表",
            source_name="大学改革支援・学位授与機構",
        )
        self.assertEqual(result["subject_category"], SUBJECT_OTHER)
        self.assertIn(THEME_EVALUATION, result["themes"])

    def test_national_university_evaluation_keeps_national_subject(self):
        result = classify_subject_and_themes(
            "大阪大学が自己点検・評価結果を公表"
        )
        self.assertEqual(result["subject_category"], SUBJECT_NATIONAL)
        self.assertIn(THEME_EVALUATION, result["themes"])

    def test_private_university_career_is_not_national(self):
        result = classify_subject_and_themes(
            "私立大学が学生の就職支援プログラムを開始"
        )
        self.assertEqual(result["subject_category"], SUBJECT_OTHER)
        self.assertIn(THEME_STUDENT_CAREER, result["themes"])

    def test_kobe_article_can_have_multiple_themes(self):
        result = classify_subject_and_themes(
            "神戸大学がキャリア教育プログラムを開設"
        )
        self.assertEqual(result["subject_category"], SUBJECT_KOBE)
        self.assertIn(THEME_STUDENT_CAREER, result["themes"])
        self.assertIn(THEME_EDUCATION, result["themes"])

    def test_mext_source_is_mext_subject(self):
        result = classify_subject_and_themes(
            "令和9年度予算案を公表",
            source_name="文部科学省",
        )
        self.assertEqual(result["subject_category"], SUBJECT_MEXT)


class SubjectThemeStorageTests(unittest.TestCase):
    def test_old_category_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "test.db"
            connection = connect(database)
            upsert_articles(
                connection,
                [
                    {
                        "fingerprint": "niad-evaluation",
                        "title": "大学機関別認証評価の評価結果を公表",
                        "summary": "",
                        "url": "https://example.com/evaluation",
                        "source_name": "大学改革支援・学位授与機構",
                        "source_kind": "rss",
                        "published_at": None,
                        "fetched_at": "2026-08-15T00:00:00+09:00",
                        "category": "認証評価・法人評価関係",
                        "relevance_score": 80,
                        "kobe_related": 0,
                        "is_relevant": 1,
                        "paywall_status": "free",
                        "search_query": "",
                    }
                ],
            )

            self.assertEqual(ensure_current_subject_themes(connection), 1)
            article = connection.execute(
                "SELECT category, subject_category FROM articles"
            ).fetchone()
            themes = {
                row["theme"]
                for row in connection.execute("SELECT theme FROM article_themes")
            }

            self.assertEqual(article["category"], "認証評価・法人評価関係")
            self.assertEqual(article["subject_category"], SUBJECT_OTHER)
            self.assertIn(THEME_EVALUATION, themes)
            self.assertEqual(ensure_current_subject_themes(connection), 0)
            connection.close()


    def test_longer_summary_is_reclassified(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "test.db"
            connection = connect(database)
            article = {
                "fingerprint": "summary-update",
                "title": "大学からのお知らせ",
                "summary": "",
                "url": "https://example.com/news",
                "source_name": "大学専門媒体",
                "source_kind": "rss",
                "published_at": None,
                "fetched_at": "2026-08-15T00:00:00+09:00",
                "category": "高等教育全般",
                "relevance_score": 30,
                "kobe_related": 0,
                "is_relevant": 1,
                "paywall_status": "free",
                "search_query": "",
            }
            upsert_articles(connection, [article])
            ensure_current_subject_themes(connection)

            article["summary"] = "大学が企業との共同研究成果を公表しました。"
            article["fetched_at"] = "2026-08-15T01:00:00+09:00"
            upsert_articles(connection, [article])

            version = connection.execute(
                "SELECT subject_theme_version FROM articles"
            ).fetchone()["subject_theme_version"]
            self.assertEqual(version, "")
            self.assertEqual(ensure_current_subject_themes(connection), 1)
            themes = {
                row["theme"]
                for row in connection.execute("SELECT theme FROM article_themes")
            }
            self.assertIn(THEME_RESEARCH, themes)
            connection.close()


if __name__ == "__main__":
    unittest.main()
