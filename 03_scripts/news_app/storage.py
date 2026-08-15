"""SQLiteへの保存と画面用データ取得。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .classifier import CLASSIFIER_VERSION, classify_article
from .config import DATABASE_PATH
from .taxonomy import (
    SUBJECT_THEME_CLASSIFIER_VERSION,
    classify_subject_and_themes,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    published_at TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    category TEXT NOT NULL,
    relevance_score INTEGER NOT NULL DEFAULT 0,
    kobe_related INTEGER NOT NULL DEFAULT 0,
    is_relevant INTEGER NOT NULL DEFAULT 0,
    paywall_status TEXT NOT NULL DEFAULT 'unknown',
    search_query TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_articles_published
    ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_category
    ON articles(category);

CREATE TABLE IF NOT EXISTS article_themes (
    article_id INTEGER NOT NULL,
    theme TEXT NOT NULL,
    PRIMARY KEY (article_id, theme),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_article_themes_theme
    ON article_themes(theme);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    source_name TEXT NOT NULL,
    status TEXT NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 0,
    new_count INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

TARGETED_SOURCE_NAMES = {
    "神戸大学ニュース",
    "神戸大学お知らせ",
    "神戸大学イベント",
    "大学改革支援・学位授与機構",
    "大学ジャーナルオンライン",
    "大学プレスセンター",
}

KOBE_SOURCE_NAMES = {
    "神戸大学ニュース",
    "神戸大学お知らせ",
    "神戸大学イベント",
}


def connect(path: Path = DATABASE_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(SCHEMA)
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(articles)")
    }
    if "subject_category" not in columns:
        connection.execute(
            "ALTER TABLE articles ADD COLUMN subject_category TEXT NOT NULL DEFAULT ''"
        )
    if "subject_theme_version" not in columns:
        connection.execute(
            "ALTER TABLE articles ADD COLUMN subject_theme_version TEXT NOT NULL DEFAULT ''"
        )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_subject ON articles(subject_category)"
    )
    connection.commit()
    return connection


def ensure_current_classification(connection: sqlite3.Connection) -> int:
    """分類ルールが変わったときだけ、既存記事をまとめて再分類する。"""
    current = connection.execute(
        "SELECT value FROM app_meta WHERE key = 'classifier_version'"
    ).fetchone()
    if current and current["value"] == CLASSIFIER_VERSION:
        return 0

    rows = connection.execute(
        """
        SELECT id, title, summary, source_name, search_query
        FROM articles
        """
    ).fetchall()
    for row in rows:
        result = classify_article(
            row["title"],
            row["summary"],
            always_kobe=row["source_name"] in KOBE_SOURCE_NAMES,
            targeted_source=row["source_name"] in TARGETED_SOURCE_NAMES,
            source_name=row["source_name"],
            search_query=row["search_query"],
        )
        connection.execute(
            """
            UPDATE articles
            SET category = ?, relevance_score = ?,
                kobe_related = ?, is_relevant = ?
            WHERE id = ?
            """,
            (
                result["category"],
                result["relevance_score"],
                int(result["kobe_related"]),
                int(result["is_relevant"]),
                row["id"],
            ),
        )

    connection.execute(
        """
        INSERT INTO app_meta(key, value) VALUES('classifier_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (CLASSIFIER_VERSION,),
    )
    connection.commit()
    return len(rows)


def ensure_current_subject_themes(connection: sqlite3.Connection) -> int:
    """旧分類を残したまま、主語と複数テーマを追加・更新する。"""
    current = connection.execute(
        "SELECT value FROM app_meta WHERE key = 'subject_theme_classifier_version'"
    ).fetchone()
    if current and current["value"] == SUBJECT_THEME_CLASSIFIER_VERSION:
        rows = connection.execute(
            """
            SELECT id, title, summary, source_name
            FROM articles
            WHERE subject_theme_version <> ?
            """,
            (SUBJECT_THEME_CLASSIFIER_VERSION,),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT id, title, summary, source_name FROM articles"
        ).fetchall()

    for row in rows:
        result = classify_subject_and_themes(
            row["title"],
            row["summary"],
            source_name=row["source_name"],
        )
        connection.execute(
            """
            UPDATE articles
            SET subject_category = ?, subject_theme_version = ?
            WHERE id = ?
            """,
            (
                result["subject_category"],
                SUBJECT_THEME_CLASSIFIER_VERSION,
                row["id"],
            ),
        )
        connection.execute(
            "DELETE FROM article_themes WHERE article_id = ?", (row["id"],)
        )
        connection.executemany(
            "INSERT INTO article_themes(article_id, theme) VALUES (?, ?)",
            [(row["id"], theme) for theme in result["themes"]],
        )

    connection.execute(
        """
        INSERT INTO app_meta(key, value)
        VALUES('subject_theme_classifier_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (SUBJECT_THEME_CLASSIFIER_VERSION,),
    )
    connection.commit()
    return len(rows)


def upsert_articles(connection: sqlite3.Connection, articles: list[dict]) -> int:
    new_count = 0
    sql = """
    INSERT INTO articles (
        fingerprint, title, summary, url, source_name, source_kind,
        published_at, first_seen_at, last_seen_at, category,
        relevance_score, kobe_related, is_relevant, paywall_status,
        search_query
    ) VALUES (
        :fingerprint, :title, :summary, :url, :source_name, :source_kind,
        :published_at, :fetched_at, :fetched_at, :category,
        :relevance_score, :kobe_related, :is_relevant, :paywall_status,
        :search_query
    )
    ON CONFLICT(fingerprint) DO UPDATE SET
        last_seen_at = excluded.last_seen_at,
        summary = CASE
            WHEN length(excluded.summary) > length(articles.summary)
            THEN excluded.summary ELSE articles.summary END,
        subject_theme_version = CASE
            WHEN length(excluded.summary) > length(articles.summary)
            THEN '' ELSE articles.subject_theme_version END,
        category = CASE
            WHEN excluded.relevance_score >= articles.relevance_score
            THEN excluded.category ELSE articles.category END,
        relevance_score = MAX(articles.relevance_score, excluded.relevance_score),
        kobe_related = MAX(articles.kobe_related, excluded.kobe_related),
        is_relevant = MAX(articles.is_relevant, excluded.is_relevant),
        paywall_status = CASE
            WHEN articles.paywall_status = 'free' THEN 'free'
            ELSE excluded.paywall_status END,
        search_query = CASE
            WHEN articles.search_query = '' THEN excluded.search_query
            ELSE articles.search_query END
    """
    for article in articles:
        exists = connection.execute(
            "SELECT 1 FROM articles WHERE fingerprint = ?",
            (article["fingerprint"],),
        ).fetchone()
        connection.execute(sql, article)
        if not exists:
            new_count += 1
    connection.commit()
    return new_count


def record_fetch_run(
    connection: sqlite3.Connection,
    *,
    started_at: str,
    finished_at: str,
    source_name: str,
    status: str,
    item_count: int,
    new_count: int,
    message: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO fetch_runs (
            started_at, finished_at, source_name, status,
            item_count, new_count, message
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            started_at,
            finished_at,
            source_name,
            status,
            item_count,
            new_count,
            message[:1000],
        ),
    )
    connection.commit()