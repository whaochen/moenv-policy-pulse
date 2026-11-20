#!/usr/bin/env python3
"""Export full MOENV news archive, trends, topics, search index, and policy research to web/public/data/."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import moenv_news_indexer as indexer  # noqa: E402

TAIPEI_TZ = timezone(timedelta(hours=8))


def _write_json(path: Path, data: Any, compact: bool = False) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path.stat().st_size


def _pct_change(current: int, previous: int) -> float | None:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100.0, 1)


def _extract_markdown_summary(body: str) -> str:
    match = re.search(r"^##\s+摘要\s*\n+(.*?)(?:\n##\s+|\Z)", body, flags=re.M | re.S)
    if match:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", match.group(1).strip()) if p.strip()]
        if paragraphs:
            return paragraphs[0]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith(">"):
            return stripped[:240]
    return ""


def _strip_frontmatter(text: str) -> str:
    return indexer.FRONTMATTER_RE.sub("", text, count=1).lstrip()


def _export_research(vault: Path) -> dict[str, Any]:
    reports_dir = vault / "03_政策研究" / "研究報告"
    data_dir = vault / "03_政策研究" / "研究資料"

    reports: list[dict[str, Any]] = []
    if reports_dir.is_dir():
        for path in sorted(reports_dir.glob("*.md"), reverse=True):
            raw = path.read_text(encoding="utf-8")
            fm = indexer.parse_frontmatter(raw)
            status = str(fm.get("status", "published")).strip()
            if status in {"archived", "retired", "draft"}:
                continue
            body = _strip_frontmatter(raw)
            topic = str(fm.get("topic", "")).strip() or path.stem
            keywords = indexer.frontmatter_list(fm, "keywords")
            slug_base = keywords[0] if keywords else re.sub(r"^\d{4}-\d{2}-\d{2}_", "", path.stem)
            reports.append(
                {
                    "slug": slug_base,
                    "filename": path.name,
                    "topic": topic,
                    "issue_type": str(fm.get("issue_type", "")).strip(),
                    "status": status,
                    "keywords": keywords,
                    "aliases": indexer.frontmatter_list(fm, "aliases"),
                    "created": str(fm.get("created", "")).strip(),
                    "updated": str(fm.get("updated", "")).strip(),
                    "coverage_start": str(fm.get("coverage_start", "")).strip(),
                    "coverage_end": str(fm.get("coverage_end", "")).strip(),
                    "summary": _extract_markdown_summary(body),
                    "body_markdown": body,
                }
            )

    datasets: list[dict[str, Any]] = []
    if data_dir.is_dir():
        for path in sorted(data_dir.glob("*.v2.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            datasets.append(
                {
                    "filename": path.name,
                    "research_id": payload.get("research_id", path.stem),
                    "schema_version": payload.get("schema_version", "2.0"),
                    "topic": payload.get("topic", {}),
                    "scope": payload.get("scope", {}),
                    "statistics": payload.get("statistics", {}),
                    "trend_series": payload.get("trend_series", []),
                    "milestones": payload.get("milestones", []),
                }
            )

    return {
        "generated_at": datetime.now(TAIPEI_TZ).isoformat(timespec="seconds"),
        "report_count": len(reports),
        "dataset_count": len(datasets),
        "reports": reports,
        "datasets": datasets,
    }


def export_web_data(vault: Path, output_dir: Path | None = None) -> dict[str, Any]:
    out = (output_dir or (vault / "web" / "public" / "data")).resolve()
    news_dir = out / "news"
    news_dir.mkdir(parents=True, exist_ok=True)

    items = indexer.load_existing_items(vault)
    items = sorted(items, key=indexer.item_sort_key, reverse=True)
    matches_by_id = indexer.build_keyword_matches(items)

    # Read manifest generated_at if available, else current Taipei time
    manifest_src = vault / "資料" / "moenv_news_manifest.json"
    updated_at = datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")
    if manifest_src.is_file():
        try:
            src_manifest = json.loads(manifest_src.read_text(encoding="utf-8"))
            if src_manifest.get("generated_at"):
                updated_at = str(src_manifest["generated_at"])
        except (OSError, json.JSONDecodeError):
            pass

    dates = sorted(item.date for item in items if item.date)
    date_start = dates[0] if dates else ""
    date_end = dates[-1] if dates else ""

    anchor_dt = datetime.strptime(date_end, "%Y-%m-%d") if date_end else datetime.now(TAIPEI_TZ).replace(tzinfo=None)
    win30_start = anchor_dt - timedelta(days=29)
    prev30_end = win30_start - timedelta(days=1)
    prev30_start = prev30_end - timedelta(days=29)
    recent_1y_start = anchor_dt - timedelta(days=364)

    yearly_counts: Counter[str] = Counter()
    topic_year_counts: dict[str, Counter[str]] = {p.slug: Counter() for p in indexer.KEYWORD_PROFILES}
    topic_total_counts: Counter[str] = Counter()
    topic_30d_counts: Counter[str] = Counter()
    topic_prev30d_counts: Counter[str] = Counter()
    topic_latest_news: dict[str, list[dict[str, Any]]] = {p.slug: [] for p in indexer.KEYWORD_PROFILES}

    unit_all_counts: Counter[str] = Counter()
    unit_1y_counts: Counter[str] = Counter()

    cur_30d_total = 0
    prev_30d_total = 0

    # Weekly counts for the last 8 weeks ending at anchor_dt
    weekly_buckets: list[tuple[datetime, datetime]] = []
    for i in range(7, -1, -1):
        w_end = anchor_dt - timedelta(days=i * 7)
        w_start = w_end - timedelta(days=6)
        weekly_buckets.append((w_start, w_end))
    weekly_counter = [0] * len(weekly_buckets)

    by_year: dict[str, list[dict[str, Any]]] = defaultdict(list)
    search_index: list[dict[str, Any]] = []
    latest_news_cards: list[dict[str, Any]] = []

    for item in items:
        matches = matches_by_id.get(item.news_id, [])
        policy_keywords = [m.profile.title for m in matches]
        topic_slugs = [m.profile.slug for m in matches]
        year = item.date[:4] if item.date and len(item.date) >= 4 else "unknown"
        unit = item.unit or "未標示"

        yearly_counts[year] += 1
        unit_all_counts[unit] += 1

        record = {
            "news_id": item.news_id,
            "date": item.date,
            "roc_date": item.roc_date,
            "title": item.title,
            "unit": unit,
            "summary": item.summary,
            "policy_keywords": policy_keywords,
            "ai_tags": list(item.ai_tags),
            "source_url": item.source_url,
            "attach_url": item.attach_url,
        }
        by_year[year].append(record)

        if len(latest_news_cards) < 10:
            latest_news_cards.append(record)

        search_index.append(
            {
                "id": item.news_id,
                "d": item.date,
                "t": item.title,
                "u": unit,
                "k": topic_slugs,
            }
        )

        item_dt: datetime | None = None
        if item.date:
            try:
                item_dt = datetime.strptime(item.date, "%Y-%m-%d")
            except ValueError:
                item_dt = None

        in_cur_30d = False
        in_prev_30d = False
        if item_dt is not None:
            if win30_start <= item_dt <= anchor_dt:
                cur_30d_total += 1
                in_cur_30d = True
            elif prev30_start <= item_dt <= prev30_end:
                prev_30d_total += 1
                in_prev_30d = True
            if recent_1y_start <= item_dt <= anchor_dt:
                unit_1y_counts[unit] += 1
            for idx, (w_start, w_end) in enumerate(weekly_buckets):
                if w_start <= item_dt <= w_end:
                    weekly_counter[idx] += 1
                    break

        for slug in topic_slugs:
            topic_total_counts[slug] += 1
            topic_year_counts[slug][year] += 1
            if in_cur_30d:
                topic_30d_counts[slug] += 1
            elif in_prev_30d:
                topic_prev30d_counts[slug] += 1
            if len(topic_latest_news[slug]) < 10:
                topic_latest_news[slug].append(record)

    # Remove stale news/*.json files if any
    desired_year_files = {f"{year}.json" for year in by_year}
    for existing_file in news_dir.glob("*.json"):
        if existing_file.name not in desired_year_files:
            existing_file.unlink(missing_ok=True)

    # Write news/YYYY.json shards
    file_sizes: dict[str, int] = {}
    sorted_years = sorted((y for y in by_year if y.isdigit()), key=int)
    if "unknown" in by_year:
        sorted_years.append("unknown")

    for year in sorted_years:
        shard_path = news_dir / f"{year}.json"
        file_sizes[f"news/{year}.json"] = _write_json(shard_path, by_year[year], compact=True)

    # 1. manifest.json
    manifest_data = {
        "total_news": len(items),
        "date_start": date_start,
        "date_end": date_end,
        "updated_at": updated_at,
        "topic_count": len(indexer.KEYWORD_PROFILES),
        "years": [y for y in sorted_years if y.isdigit()],
        "last_30_days_count": cur_30d_total,
        "prev_30_days_count": prev_30d_total,
        "last_30_days_delta": cur_30d_total - prev_30d_total,
        "last_30_days_pct": _pct_change(cur_30d_total, prev_30d_total),
        "latest_news": latest_news_cards,
    }
    file_sizes["manifest.json"] = _write_json(out / "manifest.json", manifest_data)

    # 2. trends.json
    numeric_years = [y for y in sorted_years if y.isdigit()]
    last_30d_topics = []
    for p in indexer.KEYWORD_PROFILES:
        cur = topic_30d_counts[p.slug]
        prev = topic_prev30d_counts[p.slug]
        last_30d_topics.append(
            {
                "slug": p.slug,
                "title": p.title,
                "group": p.group,
                "current": cur,
                "previous": prev,
                "delta": cur - prev,
                "pct_change": _pct_change(cur, prev),
            }
        )
    last_30d_topics.sort(key=lambda row: (-row["current"], -row["delta"], row["title"]))

    trends_data = {
        "updated_at": updated_at,
        "yearly_totals": [{"year": y, "count": yearly_counts[y]} for y in numeric_years],
        "topic_yearly_matrix": {
            "years": numeric_years,
            "topics": [
                {
                    "slug": p.slug,
                    "title": p.title,
                    "group": p.group,
                    "counts": [topic_year_counts[p.slug].get(y, 0) for y in numeric_years],
                }
                for p in indexer.KEYWORD_PROFILES
            ],
        },
        "last_30_days": {
            "window_start": win30_start.strftime("%Y-%m-%d"),
            "window_end": anchor_dt.strftime("%Y-%m-%d"),
            "prev_start": prev30_start.strftime("%Y-%m-%d"),
            "prev_end": prev30_end.strftime("%Y-%m-%d"),
            "current_total": cur_30d_total,
            "previous_total": prev_30d_total,
            "delta": cur_30d_total - prev_30d_total,
            "pct_change": _pct_change(cur_30d_total, prev_30d_total),
            "topics": last_30d_topics,
            "weekly_counts": [
                {
                    "week_start": w_start.strftime("%Y-%m-%d"),
                    "week_end": w_end.strftime("%Y-%m-%d"),
                    "count": weekly_counter[idx],
                }
                for idx, (w_start, w_end) in enumerate(weekly_buckets)
            ],
        },
        "unit_ranking": {
            "recent_1y": [
                {"unit": u, "count": c}
                for u, c in unit_1y_counts.most_common(25)
            ],
            "all_time": [
                {"unit": u, "count": c}
                for u, c in unit_all_counts.most_common(25)
            ],
        },
    }
    file_sizes["trends.json"] = _write_json(out / "trends.json", trends_data)

    # 3. topics.json
    topics_data = [
        {
            "slug": p.slug,
            "title": p.title,
            "group": p.group,
            "description": p.description,
            "aliases": list(p.aliases),
            "total_count": topic_total_counts[p.slug],
            "last_30_days_count": topic_30d_counts[p.slug],
            "prev_30_days_count": topic_prev30d_counts[p.slug],
            "yearly_counts": {y: topic_year_counts[p.slug].get(y, 0) for y in numeric_years},
            "latest_news": topic_latest_news[p.slug],
        }
        for p in indexer.KEYWORD_PROFILES
    ]
    file_sizes["topics.json"] = _write_json(out / "topics.json", topics_data)

    # 5. search_index.json
    file_sizes["search_index.json"] = _write_json(out / "search_index.json", search_index, compact=True)

    # 6. research.json
    research_data = _export_research(vault)
    file_sizes["research.json"] = _write_json(out / "research.json", research_data)

    total_files = len(file_sizes)
    max_file = max(file_sizes.items(), key=lambda kv: kv[1]) if file_sizes else ("", 0)
    return {
        "output_dir": str(out),
        "total_news": len(items),
        "shard_sum": sum(len(v) for v in by_year.values()),
        "total_files": total_files,
        "search_index_bytes": file_sizes["search_index.json"],
        "max_file": {"name": max_file[0], "bytes": max_file[1]},
        "research_reports": research_data["report_count"],
        "research_datasets": research_data["dataset_count"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export MOENV vault data to web/public/data/ JSON shards.")
    parser.add_argument("--vault", type=Path, default=Path.cwd(), help="Path to Obsidian vault root.")
    parser.add_argument("--out", type=Path, default=None, help="Output directory (default: <vault>/web/public/data).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = export_web_data(vault=args.vault.resolve(), output_dir=args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
