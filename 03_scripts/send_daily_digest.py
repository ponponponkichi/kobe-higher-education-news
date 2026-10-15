"""GitHub Actionsまたは手元から日次ニュースメールを送信する。"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from news_app.config import OUTPUT_DIR, PUBLIC_DATA_PATH
from news_app.email_digest import (
    MailSettings,
    build_message,
    read_json,
    select_digest_articles,
    send_message,
    write_success_state,
)


DEFAULT_STATE_PATH = OUTPUT_DIR / "email_digest_state.json"


def _recipients(value: str) -> tuple[str, ...]:
    normalized = value.replace(";", ",").replace("\n", ",")
    return tuple(address.strip() for address in normalized.split(",") if address.strip())


def mail_settings_from_environment() -> MailSettings | None:
    sender = os.environ.get("DIGEST_GMAIL_ADDRESS", "").strip()
    password = "".join(os.environ.get("DIGEST_GMAIL_APP_PASSWORD", "").split())
    recipients = _recipients(os.environ.get("DIGEST_RECIPIENTS", ""))
    if not sender or not password or not recipients:
        return None
    return MailSettings(sender=sender, app_password=password, recipients=recipients)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description="新着ニュースの日次メールを送信します。")
    parser.add_argument("--feed", type=Path, default=PUBLIC_DATA_PATH)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument(
        "--skip-if-unconfigured",
        action="store_true",
        help="メール用環境変数が未設定なら、エラーにせず送信を見送ります。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="メールを送らず、件名と本文を画面へ表示します。",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    if not args.feed.exists():
        print(f"公表用データが見つかりません: {args.feed}")
        return 3
    feed = read_json(args.feed, {"version": 1, "articles": []})
    state = read_json(args.state, {"version": 1})
    window_start, articles = select_digest_articles(feed, state, now=now)

    settings = mail_settings_from_environment()
    if settings is None:
        if args.dry_run:
            settings = MailSettings(
                sender="preview@example.com",
                app_password="not-used",
                recipients=("recipient@example.com",),
            )
        elif args.skip_if_unconfigured:
            print("メール用Secretsが未設定のため、日次メールを見送りました。")
            return 0
        else:
            print(
                "DIGEST_GMAIL_ADDRESS、DIGEST_GMAIL_APP_PASSWORD、"
                "DIGEST_RECIPIENTSを設定してください。"
            )
            return 2

    message = build_message(
        settings,
        articles,
        window_start=window_start,
        now=now,
    )
    if args.dry_run:
        print(message["Subject"])
        print("-" * 72)
        print(message.get_body(preferencelist=("plain",)).get_content())
        print("送信と送信済み時刻の更新は行っていません。")
        return 0

    send_message(settings, message)
    write_success_state(args.state, now=now, article_count=len(articles))
    print(f"日次メールを送信しました。新着 {len(articles)}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
