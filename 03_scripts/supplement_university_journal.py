"""PCから大学ジャーナルRSSを取得し、GitHub公表JSONの更新案を作る。

このスクリプト自身はGitHubを更新しない。最新の公表JSONとRSSを一時ファイル上で
統合し、GitHub Contents APIへ渡すリクエストファイルを準備するだけに限定する。
実際の公開は publish_university_journal.ps1 が、テストと再確認の後に行う。
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from news_app.collector import collect_rss
from news_app.config import SOURCES, USER_AGENT
from news_app.public_feed import PUBLIC_FEED_VERSION
from news_app.taxonomy import classify_subject_and_themes


REPOSITORY = "ponponponkichi/kobe-higher-education-news"
BRANCH = "main"
PUBLIC_DATA_REPOSITORY_PATH = "02_output/public_news.json"
CONTENTS_API_URL = (
    f"https://api.github.com/repos/{REPOSITORY}/contents/"
    f"{PUBLIC_DATA_REPOSITORY_PATH}"
)
SOURCE_NAME = "大学ジャーナルオンライン"
REQUEST_TIMEOUT = 30
COMMIT_MESSAGE = "Supplement University Journal feed from local PC"


class SupplementError(RuntimeError):
    """安全に公開できない状態を表す。"""


def _source() -> dict:
    for source in SOURCES:
        if source["name"] == SOURCE_NAME:
            return source
    raise SupplementError(f"情報源設定に「{SOURCE_NAME}」がありません。")


def fetch_remote_public_feed() -> tuple[str, dict]:
    """GitHubの最新JSONと、その版を示すblob SHAを返す。"""
    response = requests.get(
        CONTENTS_API_URL,
        params={"ref": BRANCH},
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    metadata = response.json()
    if metadata.get("type") != "file" or not metadata.get("sha"):
        raise SupplementError("GitHubの公表JSONをファイルとして確認できませんでした。")
    try:
        decoded = base64.b64decode(metadata["content"]).decode("utf-8")
        payload = json.loads(decoded)
    except (KeyError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupplementError("GitHubの公表JSONを正しく読み込めませんでした。") from exc
    if not isinstance(payload.get("articles"), list):
        raise SupplementError("GitHubの公表JSONにarticles一覧がありません。")
    return metadata["sha"], payload


def collect_university_journal() -> list[dict]:
    """PCの通信経路から大学ジャーナルRSSだけを取得する。"""
    articles = collect_rss(_source())
    if not articles:
        raise SupplementError("大学ジャーナルRSSを取得できましたが、記事が0件でした。")
    if len(articles) > 200:
        raise SupplementError(
            f"大学ジャーナルRSSが想定外の件数です（{len(articles)}件）。公開を中止します。"
        )
    return articles


def _public_article(item: dict, previous: dict | None) -> dict:
    """RSS記事を公表JSONの形式へ変換する。

    利用条件を慎重に扱うため、新たに補完する記事のRSS概要は公表しない。
    既存JSONに概要がある場合も、この補完処理では内容を変更しない。
    """
    previous = previous or {}
    fetched_at = item["fetched_at"]
    taxonomy = classify_subject_and_themes(
        item["title"],
        item.get("summary", ""),
        source_name=SOURCE_NAME,
    )
    return {
        "fingerprint": item["fingerprint"],
        "title": item["title"],
        "summary": previous.get("summary", ""),
        "url": item["url"],
        "source_name": SOURCE_NAME,
        "source_kind": item["source_kind"],
        "published_at": item.get("published_at"),
        "first_seen_at": previous.get("first_seen_at") or fetched_at,
        "last_seen_at": fetched_at,
        "category": item["category"],
        "relevance_score": item["relevance_score"],
        "kobe_related": item["kobe_related"],
        "is_relevant": item["is_relevant"],
        "paywall_status": item["paywall_status"],
        "search_query": "",
        "subject_category": taxonomy["subject_category"],
        "themes": "｜".join(taxonomy["themes"]),
        "summary_policy": previous.get("summary_policy", "none"),
    }


def merge_feed(remote: dict, rss_articles: list[dict]) -> tuple[dict, list[dict]]:
    """最新公表JSONへ、表示対象の大学ジャーナル記事だけを統合する。"""
    merged = {
        article["fingerprint"]: article
        for article in remote["articles"]
        if article.get("fingerprint")
    }
    existing_fingerprints = set(merged)
    new_articles: list[dict] = []

    for item in rss_articles:
        if not item.get("is_relevant"):
            continue
        article = _public_article(item, merged.get(item["fingerprint"]))
        merged[item["fingerprint"]] = article
        if item["fingerprint"] not in existing_fingerprints:
            new_articles.append(article)

    articles = list(merged.values())
    articles.sort(
        key=lambda article: article.get("published_at")
        or article.get("first_seen_at")
        or "",
        reverse=True,
    )
    payload = {
        "version": remote.get("version", PUBLIC_FEED_VERSION),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "articles": articles,
    }
    return payload, new_articles


def write_prepared_files(
    *,
    candidate_path: Path,
    request_path: Path,
    original_sha: str,
    payload: dict,
) -> None:
    """候補JSONと、SHA付きGitHub更新要求を一時ファイルへ原子的に保存する。"""
    candidate_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_temporary = candidate_path.with_suffix(candidate_path.suffix + ".writing")
    candidate_temporary.write_text(candidate_text, encoding="utf-8")
    candidate_temporary.replace(candidate_path)

    request_payload = {
        "message": COMMIT_MESSAGE,
        "content": base64.b64encode(candidate_text.encode("utf-8")).decode("ascii"),
        "sha": original_sha,
        "branch": BRANCH,
    }
    request_temporary = request_path.with_suffix(request_path.suffix + ".writing")
    request_temporary.write_text(
        json.dumps(request_payload, ensure_ascii=True),
        encoding="utf-8",
    )
    request_temporary.replace(request_path)


def verify_request(request_path: Path) -> None:
    """準備後にGitHubが更新されていないことをSHAで確認する。"""
    try:
        prepared = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SupplementError("公開準備ファイルを読み込めませんでした。") from exc
    current_sha, _ = fetch_remote_public_feed()
    if prepared.get("sha") != current_sha:
        raise SupplementError(
            "準備後にGitHubの公表JSONが更新されました。"
            "古いデータで上書きしないため、最初からやり直してください。"
        )


def prepare(candidate_path: Path, request_path: Path) -> int:
    original_sha, remote = fetch_remote_public_feed()
    rss_articles = collect_university_journal()
    payload, new_articles = merge_feed(remote, rss_articles)
    write_prepared_files(
        candidate_path=candidate_path,
        request_path=request_path,
        original_sha=original_sha,
        payload=payload,
    )

    print("\n大学ジャーナル補完のプレビュー")
    print("-" * 72)
    print(f"GitHubに現在ある記事: {len(remote['articles'])}件")
    print(f"PCで取得したRSS記事: {len(rss_articles)}件")
    print(f"今回新たに追加する記事: {len(new_articles)}件")
    if new_articles:
        for number, article in enumerate(new_articles, start=1):
            print(f"{number:>2}. {article['title']}")
    else:
        print("新規記事はありません。既存記事の最終確認日時だけを更新します。")
    print("-" * 72)
    print("この時点ではGitHubを変更していません。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="大学ジャーナルRSSを公表JSONへ安全に補完する準備をします。"
    )
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="準備時からGitHubのJSONが変わっていないかだけを確認します。",
    )
    args = parser.parse_args()
    try:
        if args.verify_only:
            verify_request(args.request)
            print("GitHub側に競合する更新はありません。")
            return 0
        return prepare(args.candidate, args.request)
    except (requests.RequestException, SupplementError) as exc:
        print(f"\n中止しました: {exc}", file=sys.stderr)
        print("GitHubのデータは変更していません。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
