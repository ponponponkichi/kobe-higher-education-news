"""コマンドラインからニュースを更新する。"""

import argparse

from news_app.collector import run_collection
from news_app.public_feed import build_public_feed


def main() -> int:
    parser = argparse.ArgumentParser(description="高等教育ニュースを更新します。")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="一部情報源が失敗しても、取得済みデータを公開して正常終了します。",
    )
    args = parser.parse_args()
    results = run_collection()
    print("\nニュース取得結果")
    print("-" * 72)
    for result in results:
        mark = "OK" if result["status"] == "success" else "NG"
        print(
            f"[{mark}] {result['source_name']}: "
            f"取得 {result['item_count']}件 / 新規 {result['new_count']}件"
        )
        if result["message"]:
            print(f"     {result['message']}")
    failures = sum(result["status"] != "success" for result in results)
    public_feed = build_public_feed()
    print("-" * 72)
    print(f"情報源 {len(results)}件、失敗 {failures}件")
    print(
        f"公表用データ {len(public_feed['articles'])}件 / "
        f"生成日時 {public_feed['generated_at']}"
    )
    return 0 if args.allow_partial or not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
