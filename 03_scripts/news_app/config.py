"""情報源と保存先の設定。

情報源を増やすときは、まず SOURCES に1件追加します。取得方法ごとの処理は
collector.py にまとめ、画面やデータベース処理と分離しています。
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "02_output"
DATABASE_PATH = OUTPUT_DIR / "higher_education_news.db"
PUBLIC_DATA_PATH = OUTPUT_DIR / "public_news.json"

USER_AGENT = (
    "HigherEducationNewsPrototype/0.1 "
    "(local research tool; contact: local administrator)"
)
REQUEST_TIMEOUT = 25

EXCLUDED_PUBLISHERS = (
    "PR TIMES",
    "ねとらぼ",
    "NHKニュース",
)

SOURCES = [
    {
        "name": "神戸大学ニュース",
        "kind": "rss",
        "url": "https://www.kobe-u.ac.jp/ja/news/article/rss.xml",
        "targeted": True,
        "always_kobe": True,
    },
    {
        "name": "神戸大学お知らせ",
        "kind": "rss",
        "url": "https://www.kobe-u.ac.jp/ja/announcement/rss.xml",
        "targeted": True,
        "always_kobe": True,
    },
    {
        "name": "神戸大学イベント",
        "kind": "rss",
        "url": "https://www.kobe-u.ac.jp/ja/news/events/rss.xml",
        "targeted": True,
        "always_kobe": True,
    },
    {
        "name": "文部科学省",
        "kind": "rss",
        "url": "https://www.mext.go.jp/b_menu/news/index.rdf",
        "targeted": False,
    },
    {
        "name": "大学改革支援・学位授与機構",
        "kind": "rss",
        "url": "https://www.niad.ac.jp/rss2.xml",
        "targeted": True,
    },
    {
        "name": "大学ジャーナルオンライン",
        "kind": "rss",
        "url": "https://univ-journal.jp/feed/",
        "targeted": True,
    },
    {
        "name": "大学プレスセンター",
        "kind": "u_press_html",
        "url": "https://www.u-presscenter.jp/",
        "targeted": True,
    },
    {
        "name": "ベネッセ VIEW next",
        "kind": "benesse_html",
        "url": "https://view-next.benesse.jp/news/",
        "targeted": False,
    },
]

NEWS_SEARCHES = [
    "\"神戸大学\" OR \"Kobe University\"",
    "国立大学 予算 OR 政策 OR 改革 OR 評価",
    "高等教育 政策 OR 予算 OR 大学",
    "大学 認証評価 OR 法人評価 OR 内部質保証",
    "大学 入試 OR 就職 OR ランキング",
    "\"文部科学省\" 大学 when:30d",
    "\"国立大学\" when:30d",
    "site:newswitch.jp/p/ 文科省 when:30d",
]

LIKELY_PAID_PUBLISHERS = (
    "日本経済新聞", "日経", "nikkei.com", "朝日新聞デジタル", "朝日新聞",
    "読売新聞オンライン", "読売新聞", "毎日新聞", "産経新聞",
    "神戸新聞NEXT", "神戸新聞", "教育新聞", "日本教育新聞",
    "週刊東洋経済", "東洋経済オンライン", "週刊ダイヤモンド",
    "ダイヤモンド・オンライン", "AERA", "サンデー毎日",
)

FREE_PUBLISHERS = (
    "神戸大学", "文部科学省", "大学改革支援・学位授与機構",
    "大学ジャーナルオンライン", "大学プレスセンター", "ベネッセ VIEW next",
    "NHK", "kobe-u.ac.jp", "mext.go.jp", "niad.ac.jp", "janu.jp",
    "大学通信オンライン", "ReseEd", "リセマム", "ベネッセ",
)
