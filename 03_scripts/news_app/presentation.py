"""画面表示に使う、Streamlitに依存しない判定処理。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


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