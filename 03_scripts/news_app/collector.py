"""公開情報源からニュース候補を取得する。"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from .classifier import classify_article, detect_paywall, title_fingerprint
from .config import (
    DATABASE_PATH,
    EXCLUDED_PUBLISHERS,
    NEWS_SEARCHES,
    REQUEST_TIMEOUT,
    SOURCES,
    USER_AGENT,
)
from .storage import (
    connect,
    ensure_current_subject_themes,
    record_fetch_run,
    upsert_articles,
)


UNIVERSITY_JOURNAL_SOURCE = "大学ジャーナルオンライン"
MAX_UNIVERSITY_JOURNAL_TITLE_BREAKS = 20
_TITLE_ELEMENT_PATTERN = re.compile(
    rb"(<title(?:\s[^>]*)?>)(.*?)(</title\s*>)",
    re.IGNORECASE | re.DOTALL,
)
_BARE_HTML_BREAK_PATTERN = re.compile(rb"<br\s*>", re.IGNORECASE)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(element: ET.Element, *names: str) -> str:
    wanted = {name.lower() for name in names}
    for child in element:
        if local_name(child.tag) in wanted:
            return "".join(child.itertext()).strip()
    return ""


def clean_html(value: str, limit: int = 500) -> str:
    value = html.unescape(value or "")
    if "<" in value and ">" in value:
        value = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", value).strip()
    return text[:limit]


def normalize_url(url: str) -> str:
    parts = urlsplit((url or "").strip())
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, parts.query, ""))


def parse_date(value: str) -> str | None:
    if not value:
        return None
    value = value.strip()
    try:
        return parsedate_to_datetime(value).astimezone().isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError):
        pass
    iso_value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_value).astimezone().isoformat(timespec="seconds")
    except ValueError:
        pass
    match = re.search(r"(20\d{2})[./年-](\d{1,2})[./月-](\d{1,2})", value)
    if match:
        year, month, day = map(int, match.groups())
        return datetime(year, month, day).astimezone().isoformat(timespec="seconds")
    return None


def request_content(url: str) -> bytes:
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return response.content


def _repair_university_journal_title_breaks(content: bytes) -> tuple[bytes, int]:
    """大学ジャーナルのtitle内にある未閉鎖のbrだけを空白へ置き換える。"""
    replacement_count = 0

    def replace_title(match: re.Match[bytes]) -> bytes:
        nonlocal replacement_count
        title_body = match.group(2)
        if b"<![CDATA[" in title_body:
            return match.group(0)
        repaired_body, count = _BARE_HTML_BREAK_PATTERN.subn(b" ", title_body)
        replacement_count += count
        return match.group(1) + repaired_body + match.group(3)

    repaired = _TITLE_ELEMENT_PATTERN.sub(replace_title, content)
    return repaired, replacement_count


def parse_rss_xml(content: bytes, source_name: str) -> ET.Element:
    """通常は厳密に解析し、既知の大学ジャーナルtitle不備だけを限定補正する。"""
    try:
        return ET.fromstring(content)
    except ET.ParseError:
        if source_name != UNIVERSITY_JOURNAL_SOURCE:
            raise
        repaired, replacement_count = _repair_university_journal_title_breaks(content)
        if not 1 <= replacement_count <= MAX_UNIVERSITY_JOURNAL_TITLE_BREAKS:
            raise
        return ET.fromstring(repaired)


def make_article(
    *,
    title: str,
    summary: str,
    url: str,
    source_name: str,
    source_kind: str,
    published_at: str | None,
    targeted_source: bool,
    always_kobe: bool = False,
    search_query: str = "",
    publisher_name: str = "",
) -> dict | None:
    title = clean_html(title, 300)
    if not title or len(title) < 4:
        return None
    if re.search(r"\d+\s*枚目の写真・画像", title):
        return None
    summary = clean_html(summary)
    url = normalize_url(url)
    display_source = publisher_name.strip() or source_name
    exclusion_text = f"{display_source} {title}".casefold()
    if any(name.casefold() in exclusion_text for name in EXCLUDED_PUBLISHERS):
        return None
    classification = classify_article(
        title,
        summary,
        always_kobe=always_kobe,
        targeted_source=targeted_source,
        source_name=display_source,
        search_query=search_query,
    )
    fetched_at = now_iso()
    return {
        "fingerprint": title_fingerprint(title),
        "title": title,
        "summary": summary,
        "url": url,
        "source_name": display_source,
        "source_kind": source_kind,
        "published_at": published_at,
        "fetched_at": fetched_at,
        "category": classification["category"],
        "relevance_score": classification["relevance_score"],
        "kobe_related": int(classification["kobe_related"]),
        "is_relevant": int(classification["is_relevant"]),
        "paywall_status": detect_paywall(display_source, title, summary),
        "search_query": search_query,
    }


def collect_rss(source: dict) -> list[dict]:
    root = parse_rss_xml(request_content(source["url"]), source["name"])
    entries = [node for node in root.iter() if local_name(node.tag) in {"item", "entry"}]
    articles = []
    for entry in entries:
        link = child_text(entry, "link")
        if not link:
            for child in entry:
                if local_name(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        publisher = child_text(entry, "source")
        article = make_article(
            title=child_text(entry, "title"),
            summary=child_text(entry, "description", "summary", "content"),
            url=link,
            source_name=source["name"],
            publisher_name=publisher if source.get("google_news") else "",
            source_kind=source["kind"],
            published_at=parse_date(
                child_text(entry, "pubdate", "published", "updated", "date")
            ),
            targeted_source=source.get("targeted", False),
            always_kobe=source.get("always_kobe", False),
            search_query=source.get("query", ""),
        )
        if article:
            articles.append(article)
    return articles


def mext_page_summary(url: str, title: str) -> str:
    """文科省RSSにない概要を公式ページから短く補う。"""
    fallback = (
        f"文部科学省が「{title}」に関する情報を公開しました。"
        "詳細は公式ページをご確認ください。"
    )
    try:
        soup = BeautifulSoup(request_content(url), "html.parser")
    except (requests.RequestException, ValueError):
        return fallback

    root = soup.select_one("main") or soup.select_one("#main") or soup.body
    if root is None:
        return fallback

    skipped_starts = (
        "当サイトではJavaScript",
        "（部会長）",
        "（事務局）",
        "電話番号",
        "メールアドレス",
    )
    for node in root.select("p"):
        text = clean_html(node.get_text(" ", strip=True), 400)
        noise_markers = (
            "電話番号",
            "メールアドレス",
            "Adobe Acrobat Reader",
            "PDF形式のファイル",
            "その他関係者",
            "これまでに開催した会議",
        )
        contains_noise = any(marker in text for marker in noise_markers)
        looks_like_member_list = text.count("委員") >= 3
        looks_like_bare_link = len(text) < 60 and text.startswith(
            ("議事次第はこちら", "資料はこちら")
        )
        if (
            len(text) < 30
            or text.startswith(skipped_starts)
            or text.startswith("【")
            or contains_noise
            or looks_like_member_list
            or looks_like_bare_link
        ):
            continue
        return text
    return fallback


def enrich_mext_summaries(connection, articles: list[dict]) -> None:
    """DBにもRSSにも概要がない文科省記事だけを補完する。"""
    for article in articles:
        if article["source_name"] != "文部科学省" or article["summary"]:
            continue
        existing = connection.execute(
            "SELECT summary FROM articles WHERE fingerprint = ?",
            (article["fingerprint"],),
        ).fetchone()
        if existing and existing["summary"].strip():
            continue
        article["summary"] = mext_page_summary(article["url"], article["title"])


def collect_u_press(source: dict) -> list[dict]:
    soup = BeautifulSoup(request_content(source["url"]), "html.parser")
    articles = []
    for element in soup.select("main article"):
        anchor = element.find("a", href=True)
        if not anchor:
            continue
        text = element.get_text(" ", strip=True)
        title = anchor.get_text(" ", strip=True) or text
        date_match = re.search(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", text)
        article = make_article(
            title=title,
            summary="",
            url=urljoin(source["url"], anchor["href"]),
            source_name=source["name"],
            source_kind=source["kind"],
            published_at=parse_date(date_match.group(0)) if date_match else None,
            targeted_source=True,
        )
        if article:
            articles.append(article)
    return articles


def collect_benesse(source: dict) -> list[dict]:
    soup = BeautifulSoup(request_content(source["url"]), "html.parser")
    articles = []
    seen_urls = set()
    for anchor in soup.find_all("a", href=True):
        url = urljoin(source["url"], anchor["href"])
        if "/news/page-" not in url or url in seen_urls:
            continue
        title = anchor.get_text(" ", strip=True)
        if len(title) < 12:
            continue
        seen_urls.add(url)
        date_match = re.search(r"20\d{2}/\d{1,2}/\d{1,2}", title)
        title = re.sub(r"^\d+\s+", "", title)
        title = re.sub(r"\s+20\d{2}/\d{1,2}/\d{1,2}.*$", "", title)
        article = make_article(
            title=title,
            summary="",
            url=url,
            source_name=source["name"],
            source_kind=source["kind"],
            published_at=parse_date(date_match.group(0)) if date_match else None,
            targeted_source=False,
        )
        if article:
            articles.append(article)
    return articles


def google_news_source(query: str) -> dict:
    return {
        "name": f"一般ニュース検索：{query}",
        "kind": "rss",
        "url": (
            "https://news.google.com/rss/search?"
            f"q={quote_plus(query)}&hl=ja&gl=JP&ceid=JP:ja"
        ),
        "targeted": False,
        "google_news": True,
        "query": query,
    }


COLLECTORS = {
    "rss": collect_rss,
    "u_press_html": collect_u_press,
    "benesse_html": collect_benesse,
}


def run_collection(database_path=DATABASE_PATH) -> list[dict]:
    """全情報源を取得し、情報源ごとの結果を返す。"""
    connection = connect(database_path)
    results = []
    all_sources = [*SOURCES, *(google_news_source(query) for query in NEWS_SEARCHES)]

    for source in all_sources:
        started_at = now_iso()
        try:
            items = COLLECTORS[source["kind"]](source)
            enrich_mext_summaries(connection, items)
            new_count = upsert_articles(connection, items)
            status = "success"
            message = ""
        except Exception as exc:  # 1媒体の障害で全体を止めないための境界
            items = []
            new_count = 0
            status = "error"
            message = f"{type(exc).__name__}: {exc}"
        finished_at = now_iso()
        result = {
            "source_name": source["name"],
            "status": status,
            "item_count": len(items),
            "new_count": new_count,
            "message": message,
        }
        results.append(result)
        record_fetch_run(
            connection,
            started_at=started_at,
            finished_at=finished_at,
            **result,
        )

    ensure_current_subject_themes(connection)
    connection.close()
    return results
