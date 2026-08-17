"""画面表示に使う、Streamlitに依存しない判定処理。"""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse


TRAILING_MEDIA_PATTERN = re.compile(
    r"\s*(?:[-–—|｜]\s*)?"
    r"(?:Infoseekニュース|Yahoo!?ニュース|[^|｜\-–—]{0,25}"
    r"(?:新聞|ニュース|オンライン|デジタル))\s*$",
    re.IGNORECASE,
)


UNIVERSITY_NAME_PATTERN = re.compile(
    r"(?:^|[【】「」『』（()\[\]〔〕、,・/／\s-])"
    r"([一-龥ぁ-んァ-ンA-Za-z0-9]{2,20}大学)"
)

def _as_utc_datetime(value: object) -> datetime | None:
    """記事の日付値を比較可能なUTC日時へ変換する。"""
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _article_datetime(article: dict) -> datetime | None:
    for field in ("display_date", "published_at", "first_seen_at"):
        parsed = _as_utc_datetime(article.get(field))
        if parsed is not None:
            return parsed
    return None


def _university_names(article: dict) -> set[str]:
    title = unicodedata.normalize("NFKC", article.get("title", ""))
    return set(UNIVERSITY_NAME_PATTERN.findall(title))

def syndicated_title_key(title: str, source_name: str = "") -> str:
    """媒体名などの転載時装飾を除き、同じ発表を比較するキーを作る。"""
    text = unicodedata.normalize("NFKC", html.unescape(title or "")).strip()
    text = re.sub(r"^\s*【[^】]{2,40}】\s*", "", text)

    source = unicodedata.normalize("NFKC", source_name or "").strip()
    if source:
        text = re.sub(
            rf"\s*(?:[-–—|｜]\s*)?{re.escape(source)}\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        )
    for _ in range(2):
        shortened = TRAILING_MEDIA_PATTERN.sub("", text)
        if shortened == text:
            break
        text = shortened

    return re.sub(r"[\W_]+", "", text.casefold())


def same_syndicated_announcement(
    left: dict,
    right: dict,
    *,
    max_hours: int = 72,
) -> bool:
    """2記事が同じ発表の転載と十分確実に推定できるか判定する。"""
    left_subject = left.get("subject_category")
    right_subject = right.get("subject_category")
    if left_subject and right_subject and left_subject != right_subject:
        return False

    left_universities = _university_names(left)
    right_universities = _university_names(right)
    if (
        left_universities
        and right_universities
        and left_universities.isdisjoint(right_universities)
    ):
        return False

    left_date = _article_datetime(left)
    right_date = _article_datetime(right)
    if left_date is None or right_date is None:
        return False
    if abs(left_date - right_date) > timedelta(hours=max_hours):
        return False

    left_key = syndicated_title_key(left.get("title", ""), left.get("source_name", ""))
    right_key = syndicated_title_key(
        right.get("title", ""), right.get("source_name", "")
    )
    if min(len(left_key), len(right_key)) < 18:
        return False
    if left_key == right_key:
        return True

    matcher = SequenceMatcher(None, left_key, right_key, autojunk=False)
    longest = matcher.find_longest_match(0, len(left_key), 0, len(right_key)).size
    return matcher.ratio() >= 0.90 and longest >= 20


def _is_official_article(article: dict) -> bool:
    host = (urlparse(article.get("url", "")).hostname or "").lower()
    return host.endswith(".ac.jp") or host.endswith(".go.jp")


def _representative_article(group: list[dict]) -> dict:
    """公式情報を優先し、なければ新しい記事を代表にする。"""

    def score(article: dict) -> tuple[int, float, int]:
        published = _article_datetime(article)
        timestamp = published.timestamp() if published else 0.0
        return (_is_official_article(article), timestamp, -len(article.get("title", "")))

    return max(group, key=score)


def group_syndicated_articles(articles: list[dict]) -> list[dict]:
    """全記事を保持したまま、画面表示用に同じ発表を1件へ束ねる。"""
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    ordered = sorted(
        (dict(article) for article in articles),
        key=lambda article: _article_datetime(article) or oldest,
        reverse=True,
    )
    groups: list[list[dict]] = []
    for article in ordered:
        matching_group = next(
            (
                group
                for group in groups
                if any(same_syndicated_announcement(article, member) for member in group)
            ),
            None,
        )
        if matching_group is None:
            groups.append([article])
        else:
            matching_group.append(article)

    grouped_articles = []
    for group in groups:
        members = sorted(
            group,
            key=lambda article: _article_datetime(article) or oldest,
            reverse=True,
        )
        representative = dict(_representative_article(members))
        representative["display_date"] = _article_datetime(members[0])
        representative["syndicated_articles"] = members
        representative["syndicated_count"] = len(members)
        representative["syndicated_source_names"] = sorted(
            {
                article.get("source_name", "")
                for article in members
                if article.get("source_name")
            }
        )
        grouped_articles.append(representative)
    return grouped_articles


def is_new_article(
    published_at: datetime | None,
    *,
    now: datetime | None = None,
    days: int = 3,
) -> bool:
    """公開日時（不明時は初回取得日時）が現在から指定日数以内か判定する。"""
    if published_at is None:
        return False
    if hasattr(published_at, "to_pydatetime"):
        published_at = published_at.to_pydatetime()
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age = now.astimezone(timezone.utc) - published_at.astimezone(timezone.utc)
    return timedelta(0) <= age <= timedelta(days=days)
