"""記事を「主語」と複数の「テーマ」に分ける追加分類。

従来の category は削除・上書きせず、画面用の別軸として使用する。
"""

from __future__ import annotations

from .classifier import (
    EVALUATION_KEYWORDS,
    NATIONAL_CONTEXT_KEYWORDS,
    NATIONAL_UNIVERSITY_NAMES,
    contains_any,
    normalize_text,
)


SUBJECT_THEME_CLASSIFIER_VERSION = "1"

SUBJECT_KOBE = "神戸大学関係"
SUBJECT_MEXT = "文部科学省関係"
SUBJECT_NATIONAL = "国立大学関係"
SUBJECT_OTHER = "その他の大学・高等教育機関"

SUBJECT_TABS = [
    SUBJECT_KOBE,
    SUBJECT_MEXT,
    SUBJECT_NATIONAL,
    SUBJECT_OTHER,
]

THEME_ALL = "すべて"
THEME_POLICY = "政策・制度・予算"
THEME_ADMISSIONS = "入試"
THEME_STUDENT_CAREER = "学生支援・就職支援・キャリア教育"
THEME_EDUCATION = "教育"
THEME_RESEARCH = "研究"
THEME_INTERNATIONAL = "国際・留学生"
THEME_EVALUATION = "評価・質保証"
THEME_SOCIAL = "社会連携・地域貢献"

THEME_TABS = [
    THEME_POLICY,
    THEME_ADMISSIONS,
    THEME_STUDENT_CAREER,
    THEME_EDUCATION,
    THEME_RESEARCH,
    THEME_INTERNATIONAL,
    THEME_EVALUATION,
    THEME_SOCIAL,
]

THEME_KEYWORDS = {
    THEME_POLICY: (
        "高等教育政策", "大学政策", "制度改正", "法改正", "予算",
        "概算要求", "運営費交付金", "補助金", "競争的資金", "科研費",
        "基金", "審議会", "中教審", "大学分科会", "答申", "公募事業",
    ),
    THEME_ADMISSIONS: (
        "大学入試", "入試", "入学者選抜", "共通テスト", "志願者",
        "募集要項", "総合型選抜", "学校推薦型選抜", "高大接続",
    ),
    THEME_STUDENT_CAREER: (
        "学生支援", "就職支援", "キャリア教育", "キャリア支援", "就職",
        "インターンシップ", "奨学金", "学生相談", "学生生活", "障害学生",
        "修学支援", "学生支援機構", "JASSO",
    ),
    THEME_EDUCATION: (
        "教育改革", "教育課程", "教育プログラム", "授業", "カリキュラム",
        "学修", "教学", "学位プログラム", "FD", "単位", "卒業認定",
        "教育DX", "教育の質",
    ),
    THEME_RESEARCH: (
        "研究", "科研費", "論文", "研究力", "博士", "科学技術", "学術",
        "共同研究", "研究成果", "研究者",
    ),
    THEME_INTERNATIONAL: (
        "留学生", "国際化", "国際交流", "国際連携", "国際共同",
        "海外留学", "交換留学", "外国人学生", "グローバル",
    ),
    THEME_EVALUATION: (*EVALUATION_KEYWORDS, "機関別認証評価", "評価結果"),
    THEME_SOCIAL: (
        "社会貢献", "地域貢献", "地域連携", "社会連携", "産学連携",
        "産学官", "自治体", "地域創生", "地方創生", "公開講座",
        "リカレント教育", "生涯学習",
    ),
}

KOBE_SOURCE_NAMES = {
    "神戸大学ニュース",
    "神戸大学お知らせ",
    "神戸大学イベント",
}


def classify_subject_and_themes(
    title: str,
    summary: str = "",
    *,
    source_name: str = "",
) -> dict:
    """主語を1つ、テーマを0個以上返す。"""
    normalized = normalize_text(f"{title} {summary}")

    if source_name in KOBE_SOURCE_NAMES or contains_any(
        normalized, ("神戸大学", "Kobe University")
    ):
        subject = SUBJECT_KOBE
    elif source_name == "文部科学省" or contains_any(
        normalized, ("文部科学省", "文科省", "中央教育審議会", "中教審")
    ):
        subject = SUBJECT_MEXT
    elif source_name == "大学改革支援・学位授与機構":
        subject = SUBJECT_OTHER
    elif contains_any(normalized, NATIONAL_CONTEXT_KEYWORDS) or contains_any(
        normalized, NATIONAL_UNIVERSITY_NAMES
    ):
        subject = SUBJECT_NATIONAL
    else:
        subject = SUBJECT_OTHER

    themes = [
        theme
        for theme in THEME_TABS
        if contains_any(normalized, THEME_KEYWORDS[theme])
    ]
    return {"subject_category": subject, "themes": themes}
