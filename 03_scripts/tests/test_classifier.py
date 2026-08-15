import unittest

from news_app.classifier import (
    CATEGORY_EVALUATION,
    CATEGORY_GENERAL,
    CATEGORY_KOBE,
    CATEGORY_MEXT,
    CATEGORY_NATIONAL,
    classify_article,
    detect_paywall,
    title_fingerprint,
)


class ClassifierTests(unittest.TestCase):
    def test_kobe_is_highest_priority(self):
        result = classify_article("神戸大学が新しい教育プログラムを開始")
        self.assertEqual(result["category"], CATEGORY_KOBE)
        self.assertEqual(result["relevance_score"], 100)
        self.assertTrue(result["kobe_related"])

    def test_evaluation_categories_are_combined(self):
        for title in (
            "大学機関別認証評価の評価結果を公表",
            "国立大学法人評価の実施方針",
            "内部質保証を推進する新体制",
        ):
            with self.subTest(title=title):
                result = classify_article(title)
                self.assertEqual(result["category"], CATEGORY_EVALUATION)

    def test_mext_source_is_mext_category(self):
        result = classify_article(
            "大学関係資料を掲載しました",
            source_name="文部科学省",
        )
        self.assertEqual(result["category"], CATEGORY_MEXT)

    def test_council_and_competitive_funding_are_mext(self):
        for title in ("中央教育審議会大学分科会を開催", "競争的資金の公募を開始"):
            with self.subTest(title=title):
                self.assertEqual(classify_article(title)["category"], CATEGORY_MEXT)

    def test_generic_public_recommendation_is_not_mext_funding(self):
        result = classify_article("大学の公募推薦入試が始まる")
        self.assertEqual(result["category"], CATEGORY_NATIONAL)

    def test_national_university_name_is_national(self):
        result = classify_article("大阪大学が新しい教育研究拠点を設置")
        self.assertEqual(result["category"], CATEGORY_NATIONAL)

    def test_admissions_and_rankings_are_national_tab(self):
        result = classify_article("2027年度大学入試と大学ランキングの動向")
        self.assertEqual(result["category"], CATEGORY_NATIONAL)

    def test_other_university_research_is_general(self):
        result = classify_article("私立大学が地域連携研究を開始")
        self.assertEqual(result["category"], CATEGORY_GENERAL)

    def test_likely_paid_publisher(self):
        self.assertEqual(detect_paywall("日本経済新聞"), "likely_paid")

    def test_free_official_source(self):
        self.assertEqual(detect_paywall("文部科学省"), "free")

    def test_title_fingerprint_removes_publisher_suffix(self):
        left = title_fingerprint("国立大学の新制度を公表 - 日本経済新聞")
        right = title_fingerprint("国立大学の新制度を公表")
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()