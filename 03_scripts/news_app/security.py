"""外部ニュース由来の文字列とURLを安全に表示するための共通処理。"""

from __future__ import annotations

import html
import re
from urllib.parse import urlsplit


_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]<>()#+\-.!|>])")


def safe_external_url(value: object) -> str:
    """有効なHTTP/HTTPSの絶対URLだけを返す。無効な値は空文字にする。"""
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    if not candidate or "\\" in candidate or any(char.isspace() for char in candidate):
        return ""
    if any(ord(char) < 32 or ord(char) == 127 for char in candidate):
        return ""

    try:
        parsed = urlsplit(candidate)
        # parsed.portへのアクセスで、不正なポート番号も検出できる。
        parsed.port
    except ValueError:
        return ""

    if parsed.scheme.casefold() not in {"http", "https"}:
        return ""
    if not parsed.netloc or not parsed.hostname:
        return ""
    if parsed.username is not None or parsed.password is not None:
        return ""
    return candidate


def escape_markdown_text(value: object) -> str:
    """外部文字列を、Markdownのリンク・画像・見出し等として解釈させない。"""
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ")
    return _MARKDOWN_SPECIAL.sub(r"\\\1", text)


def safe_anchor_html(label: object, url: object) -> str:
    """安全な外部リンクのHTMLを返す。無効なURLならリンクを作らない。"""
    safe_url = safe_external_url(url)
    if not safe_url:
        return ""
    safe_label = html.escape("" if label is None else str(label))
    safe_href = html.escape(safe_url, quote=True)
    return (
        f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer">'
        f"{safe_label}</a>"
    )
