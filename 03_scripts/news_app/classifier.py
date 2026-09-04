"""記事の分類、関連度、有料記事の推定。"""

from __future__ import annotations

import re
import unicodedata

from .config import FREE_PUBLISHERS, LIKELY_PAID_PUBLISHERS


CLASSIFIER_VERSION = "5"

CATEGORY_KOBE = "神戸大学関係"
CATEGORY_MEXT = "文部科学省関係"
CATEGORY_NATIONAL = "国立大学関係"
CATEGORY_EVALUATION = "認証評価・法人評価関係"
CATEGORY_GENERAL = "高等教育全般"

KOBE_EXACT_KEYWORDS = ("神戸大学", "Kobe University")
KOBE_ABBREVIATION_PATTERN = re.compile(
    r"神戸大(?=$|[0-9\s、。，．・:：;；!?！？「」『』（）()【】\[\]…]"
    r"|が|を|の|に|へ|で|と|は|も|や|から|より|など"
    r"|教授|准教授|名誉教授|助教|講師|学長|副学長|学生|院生"
    r"|研究|病院|チーム|発|卒|出身|入試|合格)"
)

CATEGORY_TABS = [
    CATEGORY_KOBE,
    CATEGORY_MEXT,
    CATEGORY_NATIONAL,
    CATEGORY_EVALUATION,
    CATEGORY_GENERAL,
]

EVALUATION_KEYWORDS = (
    "認証評価", "内部質保証", "自己点検", "大学評価基準", "質保証",
    "法人評価", "国立大学法人評価", "業務実績評価", "中期目標", "中期計画",
)

MEXT_KEYWORDS = (
    "文部科学省", "文科省", "中央教育審議会", "中教審", "大学分科会",
    "科学技術・学術審議会", "高等教育政策", "高等教育予算", "大学政策",
    "概算要求", "運営費交付金", "補助金", "競争的資金", "科研費",
    "科学研究費", "研究費公募", "公募事業", "採択課題", "助成事業",
    "学術振興", "研究力強化", "国際卓越研究大学", "基金", "JST", "JSPS",
)

ADMISSION_RANKING_KEYWORDS = (
    "大学入試", "入学者選抜", "共通テスト", "志願者", "入試", "就職",
    "大学ランキング", "世界大学ランキング", "THE", "QS",
)

# 国立大学協会の2026年4月1日現在の会員名簿を基礎にした大学名。
NATIONAL_UNIVERSITY_NAMES = (
    "北海道大学", "北海道教育大学", "室蘭工業大学", "小樽商科大学",
    "帯広畜産大学", "北見工業大学", "旭川医科大学", "弘前大学",
    "岩手大学", "東北大学", "宮城教育大学", "秋田大学", "山形大学",
    "福島大学", "東京大学", "東京外国語大学", "東京科学大学",
    "東京学芸大学", "東京農工大学", "東京藝術大学", "東京芸術大学",
    "東京海洋大学", "お茶の水女子大学", "電気通信大学", "一橋大学",
    "政策研究大学院大学", "茨城大学", "筑波大学", "筑波技術大学",
    "宇都宮大学", "群馬大学", "埼玉大学", "千葉大学", "横浜国立大学",
    "総合研究大学院大学", "新潟大学", "長岡技術科学大学", "上越教育大学",
    "山梨大学", "信州大学", "富山大学", "金沢大学",
    "北陸先端科学技術大学院大学", "福井大学", "岐阜大学", "静岡大学",
    "浜松医科大学", "名古屋大学", "愛知教育大学", "名古屋工業大学",
    "豊橋技術科学大学", "三重大学", "滋賀大学", "滋賀医科大学",
    "京都大学", "京都教育大学", "京都工芸繊維大学", "大阪大学",
    "大阪教育大学", "兵庫教育大学", "神戸大学", "奈良教育大学",
    "奈良女子大学", "奈良先端科学技術大学院大学", "和歌山大学",
    "鳥取大学", "島根大学", "岡山大学", "広島大学", "山口大学",
    "徳島大学", "鳴門教育大学", "香川大学", "愛媛大学", "高知大学",
    "福岡教育大学", "九州大学", "九州工業大学", "佐賀大学", "長崎大学",
    "熊本大学", "大分大学", "宮崎大学", "鹿児島大学", "鹿屋体育大学",
    "琉球大学",
)

NATIONAL_CONTEXT_KEYWORDS = (
    "国立大学", "国立大学法人", "国大協", "大学共同利用機関",
    "北海道国立大学機構", "東海国立大学機構", "奈良国立大学機構",
)

HIGHER_EDUCATION_KEYWORDS = (
    "高等教育", "大学", "学部", "大学院", "研究", "教育", "学生", "高専",
)

IRRELEVANT_HINTS = (
    "小学校", "中学校", "小中学校", "幼稚園", "保育園", "高校野球",
)

PAYWALL_MARKERS = (
    "有料会員限定", "会員限定", "購読者限定", "有料記事", "続きを読むには",
    "会員登録が必要",
)


def normalize_text(value: str) -> str:
    """比較用に全角半角・空白・記号の差を小さくする。"""
    value = unicodedata.normalize("NFKC", value or "").lower()
    return re.sub(r"[\s\W_]+", "", value, flags=re.UNICODE)


def contains_any(normalized: str, keywords: tuple[str, ...]) -> bool:
    return any(normalize_text(keyword) in normalized for keyword in keywords)


def contains_kobe_reference(value: str) -> bool:
    """正式名称または語の区切りが確認できる略称だけを神戸大学と判定する。"""
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    if any(keyword.casefold() in normalized for keyword in KOBE_EXACT_KEYWORDS):
        return True
    return bool(KOBE_ABBREVIATION_PATTERN.search(normalized))


def title_fingerprint(title: str) -> str:
    """配信元名などを除いた重複判定用文字列を返す。"""
    title = re.sub(r"\s*[-–—|｜]\s*[^-–—|｜]{2,30}$", "", title or "")
    return normalize_text(title)[:240]


def classify_article(
    title: str,
    summary: str = "",
    *,
    always_kobe: bool = False,
    targeted_source: bool = False,
    source_name: str = "",
    search_query: str = "",
) -> dict:
    """5分野の分類名、関連度、神戸大学関連フラグを返す。"""
    article_text = f"{title} {summary}"
    article_normalized = normalize_text(article_text)
    context_normalized = normalize_text(f"{article_text} {source_name} {search_query}")

    kobe_related = always_kobe or contains_kobe_reference(article_text)
    if kobe_related:
        category = CATEGORY_KOBE
        score = 100
    elif contains_any(context_normalized, EVALUATION_KEYWORDS):
        category = CATEGORY_EVALUATION
        score = 80
    elif source_name == "文部科学省" or contains_any(context_normalized, MEXT_KEYWORDS):
        category = CATEGORY_MEXT
        score = 70
    elif (
        contains_any(context_normalized, NATIONAL_CONTEXT_KEYWORDS)
        or contains_any(article_normalized, NATIONAL_UNIVERSITY_NAMES)
        or contains_any(context_normalized, ADMISSION_RANKING_KEYWORDS)
    ):
        category = CATEGORY_NATIONAL
        score = 60
    else:
        category = CATEGORY_GENERAL
        score = 30 if (
            targeted_source or contains_any(article_normalized, HIGHER_EDUCATION_KEYWORDS)
        ) else 0

    if contains_any(article_normalized, IRRELEVANT_HINTS):
        if not contains_any(article_normalized, ("大学", "高等教育", "高専")):
            score = min(score, 10)

    return {
        "category": category,
        "relevance_score": score,
        "kobe_related": kobe_related,
        "is_relevant": score >= 20,
    }


def detect_paywall(source_name: str, title: str = "", summary: str = "") -> str:
    """free / likely_paid / unknown のいずれかを返す。"""
    combined = f"{source_name} {title} {summary}"
    if any(marker in combined for marker in PAYWALL_MARKERS):
        return "likely_paid"
    if any(publisher.lower() in source_name.lower() for publisher in LIKELY_PAID_PUBLISHERS):
        return "likely_paid"
    if any(publisher.lower() in source_name.lower() for publisher in FREE_PUBLISHERS):
        return "free"
    return "unknown"