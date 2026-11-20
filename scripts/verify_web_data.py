#!/usr/bin/env python3
"""Quick integrity check for exported web/public/data/ artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_FILES = (
    "manifest.json",
    "trends.json",
    "topics.json",
    "search_index.json",
    "research.json",
)
MAX_FILE_BYTES = 25 * 1024 * 1024  # Cloudflare Pages 25 MiB limit
MAX_SEARCH_INDEX_BYTES = 3 * 1024 * 1024  # 3 MiB target
MAX_TOTAL_FILES = 50


def verify_web_data(data_dir: Path) -> dict[str, object]:
    if not data_dir.is_dir():
        raise AssertionError(f"Data directory not found: {data_dir}")

    all_files = sorted(p for p in data_dir.rglob("*") if p.is_file())
    if len(all_files) >= MAX_TOTAL_FILES:
        raise AssertionError(f"Too many files under {data_dir}: {len(all_files)} >= {MAX_TOTAL_FILES}")

    for f in all_files:
        size = f.stat().st_size
        if size == 0:
            raise AssertionError(f"Empty file: {f}")
        if size >= MAX_FILE_BYTES:
            raise AssertionError(f"File exceeds 25 MiB: {f} ({size} bytes)")

    for rel in REQUIRED_FILES:
        path = data_dir / rel
        if not path.is_file():
            raise AssertionError(f"Missing required file: {path}")

    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    total_news = int(manifest.get("total_news", 0))
    if total_news <= 0:
        raise AssertionError(f"Invalid total_news in manifest.json: {total_news}")
    if int(manifest.get("topic_count", 0)) != 20:
        raise AssertionError(f"Expected 20 topics, got {manifest.get('topic_count')}")

    news_dir = data_dir / "news"
    shard_files = sorted(news_dir.glob("*.json"))
    if not shard_files:
        raise AssertionError("No news/YYYY.json shards found")

    shard_sum = 0
    for shard in shard_files:
        records = json.loads(shard.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise AssertionError(f"Shard is not a list: {shard}")
        shard_sum += len(records)

    if shard_sum != total_news:
        raise AssertionError(f"Shard sum ({shard_sum}) != manifest total_news ({total_news})")

    search_path = data_dir / "search_index.json"
    search_size = search_path.stat().st_size
    if search_size >= MAX_SEARCH_INDEX_BYTES:
        raise AssertionError(f"search_index.json exceeds 3 MiB: {search_size} bytes")

    search_index = json.loads(search_path.read_text(encoding="utf-8"))
    if len(search_index) != total_news:
        raise AssertionError(f"search_index length ({len(search_index)}) != total_news ({total_news})")

    topics = json.loads((data_dir / "topics.json").read_text(encoding="utf-8"))
    if len(topics) != 20:
        raise AssertionError(f"topics.json count ({len(topics)}) != 20")

    return {
        "status": "ok",
        "total_files": len(all_files),
        "shard_count": len(shard_files),
        "total_news": total_news,
        "shard_sum": shard_sum,
        "search_index_mib": round(search_size / (1024 * 1024), 3),
        "max_file_mib": round(max(f.stat().st_size for f in all_files) / (1024 * 1024), 3),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify exported web/public/data/ integrity.")
    parser.add_argument("--data-dir", type=Path, default=Path.cwd() / "web" / "public" / "data")
    args = parser.parse_args(argv)
    try:
        report = verify_web_data(args.data_dir.resolve())
    except AssertionError as exc:
        print(f"[ERROR] Web data verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
