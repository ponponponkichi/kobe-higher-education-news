"""公表用ニュースから、毎朝のメールダイジェストを作成・送信する。"""

from __future__ import annotations

import html
import json
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from .taxonomy import SUBJECT_KOBE, SUBJECT_MEXT, SUBJECT_NATIONAL


JST = ZoneInfo("Asia/Tokyo")
PORTAL_URL = "https://kobe-higher-education-news.streamlit.app"
DIGEST_SUBJECTS = (SUBJECT_KOBE, SUBJECT_MEXT, SUBJECT_NATIONAL)
STATE_VERSION = 1


@dataclass(frozen=True)
class MailSettings:
    sender: str
    app_password: str
    recipients: tuple[str, ...]
    sender_name: str = "高等教育ニュースポータル"


def parse_datetime(value: str | None) -> datetime | None:
    """ISO形式の日時をUTCへそろえる。"""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def digest_window_start(state: dict, now: datetime) -> datetime:
    """前回成功時刻を返す。初回だけ直近24時間を対象にする。"""
    previous = parse_datetime(state.get("last_successful_send_at"))
    return previous if previous is not None else now - timedelta(hours=24)


def select_digest_articles(
    feed: dict,
    state: dict,
    *,
    now: datetime,
) -> tuple[datetime, list[dict]]:
    """送信対象の3分類に属し、前回成功後に初めて取得した記事を選ぶ。"""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    window_start = digest_window_start(state, now)
    selected = []
    for article in feed.get("articles", []):
        if article.get("subject_category") not in DIGEST_SUBJECTS:
            continue
        first_seen = parse_datetime(article.get("first_seen_at"))
        if first_seen is None or not window_start < first_seen <= now:
            continue
        selected.append(article)
    selected.sort(
        key=lambda article: article.get("published_at")
        or article.get("first_seen_at")
        or "",
        reverse=True,
    )
    return window_start, selected


def _display_date(article: dict) -> str:
    value = parse_datetime(article.get("published_at") or article.get("first_seen_at"))
    return value.astimezone(JST).strftime("%Y/%m/%d") if value else "日付不明"


def _safe_url(value: str) -> str:
    value = (value or "").strip()
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _group_articles(articles: list[dict]) -> dict[str, list[dict]]:
    return {
        subject: [
            article
            for article in articles
            if article.get("subject_category") == subject
        ]
        for subject in DIGEST_SUBJECTS
    }


def render_plain_text(
    articles: list[dict],
    *,
    window_start: datetime,
    now: datetime,
) -> str:
    grouped = _group_articles(articles)
    lines = [
        "高等教育ニュースポータル 日次レポート",
        "",
        f"対象期間: {window_start.astimezone(JST):%Y/%m/%d %H:%M} ～ "
        f"{now.astimezone(JST):%Y/%m/%d %H:%M}",
        f"新着: {len(articles)}件",
        "",
    ]
    if not articles:
        lines.extend(["対象となる新着ニュースはありません。", ""])
    for subject in DIGEST_SUBJECTS:
        subject_articles = grouped[subject]
        lines.extend([f"■ {subject}（{len(subject_articles)}件）", ""])
        if not subject_articles:
            lines.extend(["該当なし", ""])
            continue
        for article in subject_articles:
            lines.append(f"● {article.get('title', '無題')}")
            lines.append(
                f"  {article.get('source_name', '媒体不明')} / {_display_date(article)}"
            )
            summary = (article.get("summary") or "").strip()
            if summary:
                lines.append(f"  {summary}")
            url = _safe_url(article.get("url", ""))
            if url:
                lines.append(f"  {url}")
            lines.append("")
    lines.extend(
        [
            f"ニュース一覧: {PORTAL_URL}",
            "",
            "このメールは公開情報を自動収集・分類した試験配信です。",
            "大学の公式通知ではありません。詳細・正確な内容はリンク先をご確認ください。",
        ]
    )
    return "\n".join(lines)


def render_html(
    articles: list[dict],
    *,
    window_start: datetime,
    now: datetime,
) -> str:
    grouped = _group_articles(articles)
    sections = []
    if not articles:
        sections.append("<p>対象となる新着ニュースはありません。</p>")
    for subject in DIGEST_SUBJECTS:
        subject_articles = grouped[subject]
        items = []
        for article in subject_articles:
            title = html.escape(article.get("title") or "無題")
            source = html.escape(article.get("source_name") or "媒体不明")
            url = _safe_url(article.get("url", ""))
            title_html = (
                f'<a href="{html.escape(url, quote=True)}">{title}</a>' if url else title
            )
            summary = html.escape((article.get("summary") or "").strip())
            summary_html = f'<p style="margin:6px 0 0">{summary}</p>' if summary else ""
            items.append(
                '<li style="margin-bottom:16px">'
                f'<strong>{title_html}</strong><br>'
                f'<span style="color:#555">{source} / {_display_date(article)}</span>'
                f"{summary_html}</li>"
            )
        content = "".join(items) if items else "<p>該当なし</p>"
        if items:
            content = f'<ul style="padding-left:24px">{content}</ul>'
        sections.append(
            f'<h2 style="font-size:18px;border-left:5px solid #2457a6;'
            f'padding-left:9px">{html.escape(subject)}（{len(subject_articles)}件）</h2>'
            f"{content}"
        )
    return f"""<!doctype html>
<html lang="ja"><body style="font-family:Arial,'Noto Sans JP',sans-serif;line-height:1.6;color:#222">
<h1 style="font-size:22px">高等教育ニュースポータル 日次レポート</h1>
<p>対象期間: {window_start.astimezone(JST):%Y/%m/%d %H:%M} ～ {now.astimezone(JST):%Y/%m/%d %H:%M}<br>
新着: <strong>{len(articles)}件</strong></p>
{''.join(sections)}
<p><a href="{PORTAL_URL}">ニュース一覧を開く</a></p>
<hr>
<p style="font-size:12px;color:#666">このメールは公開情報を自動収集・分類した試験配信です。<br>
大学の公式通知ではありません。詳細・正確な内容はリンク先をご確認ください。</p>
</body></html>"""


def build_message(
    settings: MailSettings,
    articles: list[dict],
    *,
    window_start: datetime,
    now: datetime,
) -> EmailMessage:
    local_now = now.astimezone(JST)
    message = EmailMessage()
    message["Subject"] = (
        f"[試験配信] 高等教育ニュース {local_now:%Y年%m月%d日}（新着{len(articles)}件）"
    )
    message["From"] = formataddr((settings.sender_name, settings.sender))
    message["To"] = ", ".join(settings.recipients)
    message.set_content(
        render_plain_text(articles, window_start=window_start, now=now)
    )
    message.add_alternative(
        render_html(articles, window_start=window_start, now=now), subtype="html"
    )
    return message


def send_message(settings: MailSettings, message: EmailMessage) -> None:
    """GmailのSTARTTLS接続でメールを送る。認証情報はログへ出力しない。"""
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(settings.sender, settings.app_password)
        smtp.send_message(message)


def write_success_state(path: Path, *, now: datetime, article_count: int) -> None:
    payload = {
        "version": STATE_VERSION,
        "last_successful_send_at": now.astimezone(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "last_article_count": article_count,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
