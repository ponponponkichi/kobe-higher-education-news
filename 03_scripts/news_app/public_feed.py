"""収集用SQLiteから、読み取り専用の公表データを生成する。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .config import DATABASE_PATH, EXCLUDED_PUBLISHERS, PUBLIC_DATA_PATH
from .security import safe_external_url
from .storage import connect, ensure_current_classification, ensure_current_subject_themes


PUBLIC_FEED_VERSION = 1
OFFICIAL_PUBLIC_SOURCES = {
    "神戸大学ニュース",
    "神戸大学お知らせ",
    "神戸大学イベント",
    "文部科学省",
    "大学改革支援・学位授与機構",
}
CAUTIOUS_PUBLISHER_MARKERS = (
    "新聞",
    "日本経済新聞",
    "日経",
    "読売",
    "朝日",
    "毎日",
    "産経",
    "神戸新聞",
    "週刊",
    "AERA",
    "東洋経済",
    "ダイヤモンド",
)


def is_excluded_public_article(article: dict) -> bool:
    """媒体名またはタイトルに除外対象が含まれる記事を公表対象外にする。"""
    exclusion_text = (
        f"{article.get('source_name', '')} {article.get('title', '')}".casefold()
    )
    return any(name.casefold() in exclusion_text for name in EXCLUDED_PUBLISHERS)


def public_summary(article: dict) -> tuple[str, str]:
    """公表画面へ出す概要と、その判断区分を返す。"""
    summary = (article.get("summary") or "").strip()
    if not summary:
        return "", "none"
    source_name = article.get("source_name") or ""
    if source_name in OFFICIAL_PUBLIC_SOURCES:
        return summary, "official"
    if article.get("search_query"):
        return "", "hidden_news_search"
    if any(marker.casefold() in source_name.casefold() for marker in CAUTIOUS_PUBLISHER_MARKERS):
        return "", "hidden_press"
    if article.get("source_kind") == "rss":
        return summary, "rss"
    return "", "hidden_non_rss"


def _safe_public_article(article: dict) -> dict:
    """記事のコピーを作り、公開可能なURLだけを残す。"""
    safe_article = dict(article)
    safe_article["url"] = safe_external_url(safe_article.get("url", ""))
    return safe_article


def _read_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        article["fingerprint"]: _safe_public_article(article)
        for article in payload.get("articles", [])
        if article.get("fingerprint") and not is_excluded_public_article(article)
    }


def _matching_existing_articles(
    merged: dict[str, dict], article: dict
) -> list[tuple[str, dict]]:
    """同じ指紋、または同じGoogleニュース記事URLを持つ既存記事を返す。"""
    fingerprint = article.get("fingerprint")
    url = (article.get("url") or "").strip()
    parsed_url = urlparse(url)
    stable_google_news_url = (
        parsed_url.netloc.casefold() == "news.google.com"
        and parsed_url.path.startswith("/rss/articles/")
    )
    return [
        (existing_fingerprint, existing)
        for existing_fingerprint, existing in merged.items()
        if existing_fingerprint == fingerprint
        or (
            stable_google_news_url
            and (existing.get("url") or "").strip() == url
        )
    ]


def _earliest_first_seen(matches: list[tuple[str, dict]]) -> str | None:
    """既存の初回取得日時のうち、最も古い値を返す。"""
    values = [
        article.get("first_seen_at")
        for _, article in matches
        if article.get("first_seen_at")
    ]
    if not values:
        return None

    def sort_key(value: str) -> tuple[int, datetime | str]:
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return (0, parsed.astimezone(timezone.utc))
        except (TypeError, ValueError):
            return (1, value)

    return min(values, key=sort_key)


def build_public_feed(
    database_path: Path = DATABASE_PATH,
    output_path: Path = PUBLIC_DATA_PATH,
) -> dict:
    """SQLiteの表示対象を既存公表データと統合し、JSONへ原子的に保存する。"""
    connection = connect(database_path)
    ensure_current_classification(connection)
    ensure_current_subject_themes(connection)
    rows = connection.execute(
        """
        SELECT a.*, COALESCE(GROUP_CONCAT(t.theme, '｜'), '') AS themes
        FROM articles AS a
        LEFT JOIN article_themes AS t ON t.article_id = a.id
        WHERE a.is_relevant = 1
        GROUP BY a.id
        """
    ).fetchall()
    connection.close()

    merged = _read_existing(output_path)
    for row in rows:
        article = dict(row)
        if is_excluded_public_article(article):
            continue
        matches = _matching_existing_articles(merged, article)
        first_seen_at = _earliest_first_seen(matches)
        if first_seen_at:
            article["first_seen_at"] = first_seen_at
        for existing_fingerprint, _ in matches:
            if existing_fingerprint != article["fingerprint"]:
                merged.pop(existing_fingerprint, None)
        article["summary"], article["summary_policy"] = public_summary(article)
        article = _safe_public_article(article)
        article.pop("id", None)
        article.pop("subject_theme_version", None)
        merged[article["fingerprint"]] = article

    articles = [
        article for article in merged.values() if not is_excluded_public_article(article)
    ]
    for article in articles:
        article["summary"], article["summary_policy"] = public_summary(article)
    articles.sort(
        key=lambda article: article.get("published_at") or article.get("first_seen_at") or "",
        reverse=True,
    )
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "version": PUBLIC_FEED_VERSION,
        "generated_at": generated_at,
        "articles": articles,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(output_path)
    return payload


def read_public_feed(path: Path = PUBLIC_DATA_PATH) -> dict:
    """公表用JSONを読み込む。未生成時は空データを返す。"""
    if not path.exists():
        return {"version": PUBLIC_FEED_VERSION, "generated_at": "", "articles": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["articles"] = [
        _safe_public_article(article) for article in payload.get("articles", [])
    ]
    return payload
