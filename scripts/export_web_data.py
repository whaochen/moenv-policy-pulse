#!/usr/bin/env python3
"""
Export full MOENV news archive, trends, topics, search index, policy research,
Route 3 policy graph, per-year relation shards, policy timelines, and academic downloads
to web/public/data/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
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

GROUP_HUBS: tuple[dict[str, str], ...] = (
    {"id": "group:climate", "title": "氣候與碳定價", "color": "#0F4C3A"},
    {"id": "group:circular", "title": "資源循環與廢棄物", "color": "#0D9488"},
    {"id": "group:pollution", "title": "污染防制", "color": "#2563EB"},
    {"id": "group:governance", "title": "治理與制度", "color": "#B45309"},
    {"id": "group:society", "title": "社會溝通與人才", "color": "#7C3AED"},
)

CLUSTER_REGULATIONS: tuple[dict[str, Any], ...] = (
    {"id": "cluster:carbon_fee_reg", "title": "碳費收費辦法", "topic_slug": "carbon_fee", "terms": ("碳費收費辦法", "碳費費率", "碳費")},
    {"id": "cluster:water_fee_reg", "title": "水污染防治費", "topic_slug": "water_quality", "terms": ("水污染防治費", "水污費")},
    {"id": "cluster:pfas_reg", "title": "PFAS 列管", "topic_slug": "chemical_management", "terms": ("PFAS", "全氟", "PFOA", "PFOS")},
    {"id": "cluster:circular_dual_law", "title": "資源循環雙法", "topic_slug": "resource_circulation", "terms": ("循環雙法", "資源循環促進法", "資源循環")},
    {"id": "cluster:cop_climate", "title": "COP 氣候大會", "topic_slug": "international_cooperation", "terms": ("COP28", "COP29", "COP30", "COP31", "巴黎協定")},
    {"id": "cluster:plastic_bag_cup", "title": "一次用減塑／袋袋箱傳", "topic_slug": "plastic_reduction", "terms": ("袋袋箱傳", "循環杯", "一次用")},
    {"id": "cluster:ev_air_std", "title": "移動源與空污標準", "topic_slug": "air_quality", "terms": ("老舊車輛", "空氣品質標準", "戴奧辛")},
    {"id": "cluster:green_talent", "title": "淨零綠領人才", "topic_slug": "environmental_education", "terms": ("綠領人才", "綠領", "淨零綠生活")},
)


def _write_json(path: Path, data: Any, compact: bool = False) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path.stat().st_size


def _write_csv_bom(path: Path, headers: list[str], rows: list[list[Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8-sig", newline="")
    return path.stat().st_size


def _pct_change(current: int, previous: int) -> float:
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


def _load_relations(vault: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    rel_path = vault / "資料" / "moenv_news_relations.jsonl"
    meta_path = vault / "資料" / "moenv_news_relations_meta.json"
    relations: dict[str, list[dict[str, Any]]] = {}
    meta: dict[str, Any] = {}
    if rel_path.is_file():
        for line in rel_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                relations[str(row["news_id"])] = row.get("relations", [])
            except (KeyError, json.JSONDecodeError):
                continue
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    return relations, meta


def _export_timelines(vault: Path, items: list[indexer.NewsItem]) -> list[dict[str, Any]]:
    timeline_dir = vault / "05_政策脈絡線"
    if not timeline_dir.is_dir():
        return []

    timelines: list[dict[str, Any]] = []
    for cfg_path in sorted(timeline_dir.glob("*.json")):
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        include_terms = [str(t).lower() for t in cfg.get("include_terms", []) if str(t).strip()]
        stage_rules = cfg.get("stage_rules", [])
        max_nodes = int(cfg.get("max_nodes", 18))

        matched: list[dict[str, Any]] = []
        for item in items:
            hay = f"{item.title} {item.summary}".lower()
            if not any(term in hay for term in include_terms):
                continue
            stage = "政策進展"
            title_lower = item.title.lower()
            for rule in stage_rules:
                terms = [str(t).lower() for t in rule.get("terms", [])]
                if any(t in title_lower for t in terms):
                    stage = str(rule.get("stage", "政策進展"))
                    break
            else:
                for rule in stage_rules:
                    terms = [str(t).lower() for t in rule.get("terms", [])]
                    if any(t in hay for t in terms):
                        stage = str(rule.get("stage", "政策進展"))
                        break

            matched.append(
                {
                    "news_id": item.news_id,
                    "date": item.date,
                    "title": item.title,
                    "unit": item.unit or "未標示",
                    "stage": stage,
                    "summary": item.summary[:180],
                    "source_url": item.source_url,
                    "source_url_status": item.source_url_status,
                }
            )

        # Keep chronological diversity: prioritize stage-tagged nodes + most recent milestones
        matched_sorted_desc = sorted(matched, key=lambda r: (r["date"], r["news_id"]), reverse=True)
        priority_nodes = [m for m in matched_sorted_desc if m["stage"] != "政策進展"]
        selected = priority_nodes[:max_nodes]
        if len(selected) < max_nodes:
            seen_ids = {m["news_id"] for m in selected}
            for m in matched_sorted_desc:
                if m["news_id"] not in seen_ids:
                    selected.append(m)
                    seen_ids.add(m["news_id"])
                if len(selected) >= max_nodes:
                    break

        selected.sort(key=lambda r: (r["date"], r["news_id"]))
        timelines.append(
            {
                "slug": cfg.get("slug", cfg_path.stem),
                "title": cfg.get("title", cfg_path.stem),
                "topic_slug": cfg.get("topic_slug", ""),
                "description": cfg.get("description", ""),
                "total_matched": len(matched),
                "nodes": selected,
            }
        )

    return timelines


def _build_policy_graph(
    items: list[indexer.NewsItem],
    matches_by_id: dict[str, list[indexer.KeywordMatch]],
    topic_total_counts: Counter[str],
    topic_30d_counts: Counter[str],
    topic_prev30d_counts: Counter[str],
    relations_by_id: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    group_id_by_name = {g["title"]: g["id"] for g in GROUP_HUBS}
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []

    # 1. Five Group Hub Nodes (category 0)
    group_totals: Counter[str] = Counter()
    for p in indexer.KEYWORD_PROFILES:
        group_totals[p.group] += topic_total_counts[p.slug]

    for g in GROUP_HUBS:
        nodes.append(
            {
                "id": g["id"],
                "name": g["title"],
                "kind": "group",
                "category": g["title"],
                "value": group_totals[g["title"]],
                "last30": sum(topic_30d_counts[p.slug] for p in indexer.KEYWORD_PROFILES if p.group == g["title"]),
                "delta30": sum(
                    topic_30d_counts[p.slug] - topic_prev30d_counts[p.slug]
                    for p in indexer.KEYWORD_PROFILES
                    if p.group == g["title"]
                ),
            }
        )

    # 2. Twenty Policy Topic Nodes (category 1..5 by group)
    for p in indexer.KEYWORD_PROFILES:
        cur = topic_30d_counts[p.slug]
        prev = topic_prev30d_counts[p.slug]
        nodes.append(
            {
                "id": f"topic:{p.slug}",
                "slug": p.slug,
                "name": p.title,
                "kind": "topic",
                "category": p.group,
                "description": p.description,
                "value": topic_total_counts[p.slug],
                "last30": cur,
                "delta30": cur - prev,
                "pct30": _pct_change(cur, prev),
                "url": f"/topics/{p.slug}",
            }
        )
        links.append(
            {
                "source": group_id_by_name[p.group],
                "target": f"topic:{p.slug}",
                "weight": max(1, topic_total_counts[p.slug] // 50),
                "kind": "hierarchy",
            }
        )

    # 3. Core Regulation / Event Cluster Nodes
    item_topics_by_id: dict[str, list[str]] = {
        nid: [m.profile.slug for m in ms] for nid, ms in matches_by_id.items()
    }
    for cluster in CLUSTER_REGULATIONS:
        c_count = 0
        c_30d = 0
        terms = [t.lower() for t in cluster["terms"]]
        dates = sorted(item.date for item in items if item.date)
        win30_start = ""
        if dates:
            win30_start = (datetime.strptime(dates[-1], "%Y-%m-%d") - timedelta(days=29)).strftime("%Y-%m-%d")
        for item in items:
            hay = f"{item.title} {item.summary}".lower()
            if any(t in hay for t in terms):
                c_count += 1
                if win30_start and item.date >= win30_start:
                    c_30d += 1
        parent_profile = next(p for p in indexer.KEYWORD_PROFILES if p.slug == cluster["topic_slug"])
        nodes.append(
            {
                "id": cluster["id"],
                "name": cluster["title"],
                "kind": "cluster",
                "category": parent_profile.group,
                "value": c_count,
                "last30": c_30d,
                "delta30": c_30d,
                "url": f"/news?q={cluster['terms'][0]}",
            }
        )
        links.append(
            {
                "source": f"topic:{cluster['topic_slug']}",
                "target": cluster["id"],
                "weight": max(2, min(15, c_count // 15)),
                "kind": "cluster",
            }
        )

    # 4. Topic-to-Topic links combining co-occurrence + Route 3 semantic relation scores
    pair_cooccur: Counter[tuple[str, str]] = Counter()
    for slugs in item_topics_by_id.values():
        uniq = sorted(set(slugs))
        for i, left in enumerate(uniq):
            for right in uniq[i + 1 :]:
                pair_cooccur[(left, right)] += 1

    pair_semantic: defaultdict[tuple[str, str], float] = defaultdict(float)
    for src_id, rels in relations_by_id.items():
        src_topics = item_topics_by_id.get(src_id, [])
        if not src_topics:
            continue
        for rel in rels:
            dst_topics = item_topics_by_id.get(str(rel["news_id"]), [])
            score = float(rel.get("score", 0.0))
            for st in src_topics:
                for dt in dst_topics:
                    if st != dt:
                        pair = (st, dt) if st < dt else (dt, st)
                        pair_semantic[pair] += score

    # Select strongest cross-topic semantic/co-occurrence edges
    combined_pairs: list[tuple[float, str, str, int]] = []
    all_pairs = set(pair_cooccur.keys()) | set(pair_semantic.keys())
    for left, right in all_pairs:
        co = pair_cooccur.get((left, right), 0)
        sem = pair_semantic.get((left, right), 0.0)
        strength = co + sem * 0.35
        if co >= 35 or sem >= 40.0:
            combined_pairs.append((strength, left, right, co))

    combined_pairs.sort(reverse=True)
    for strength, left, right, co in combined_pairs[:42]:
        links.append(
            {
                "source": f"topic:{left}",
                "target": f"topic:{right}",
                "weight": round(strength, 1),
                "cooccurrence": co,
                "kind": "semantic",
            }
        )

    return {
        "categories": [{"name": g["title"], "itemStyle": {"color": g["color"]}} for g in GROUP_HUBS],
        "nodes": nodes,
        "links": links,
    }


def export_web_data(vault: Path, output_dir: Path | None = None) -> dict[str, Any]:
    out = (output_dir or (vault / "web" / "public" / "data")).resolve()
    news_dir = out / "news"
    rel_dir = out / "relations"
    dl_dir = out / "downloads"
    news_dir.mkdir(parents=True, exist_ok=True)
    rel_dir.mkdir(parents=True, exist_ok=True)
    dl_dir.mkdir(parents=True, exist_ok=True)

    items = indexer.load_existing_items(vault)
    items = sorted(items, key=indexer.item_sort_key, reverse=True)
    matches_by_id = indexer.build_keyword_matches(items)
    relations_by_id, relations_meta = _load_relations(vault)

    # Read manifest generated_at if available
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
    unit_year_counts: dict[str, Counter[str]] = defaultdict(Counter)

    cur_30d_total = 0
    prev_30d_total = 0

    weekly_buckets: list[tuple[datetime, datetime]] = []
    for i in range(7, -1, -1):
        w_end = anchor_dt - timedelta(days=i * 7)
        w_start = w_end - timedelta(days=6)
        weekly_buckets.append((w_start, w_end))
    weekly_counter = [0] * len(weekly_buckets)

    by_year: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rel_by_year: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    search_index: list[dict[str, Any]] = []
    latest_news_cards: list[dict[str, Any]] = []
    total_relation_edges = 0

    for item in items:
        matches = matches_by_id.get(item.news_id, [])
        policy_keywords = [m.profile.title for m in matches]
        topic_slugs = [m.profile.slug for m in matches]
        year = item.date[:4] if item.date and len(item.date) >= 4 else "unknown"
        unit = item.unit or "未標示"

        yearly_counts[year] += 1
        unit_all_counts[unit] += 1
        unit_year_counts[unit][year] += 1

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
            "source_url_status": item.source_url_status,
            "attach_url": item.attach_url,
        }
        by_year[year].append(record)

        rels = relations_by_id.get(item.news_id, [])
        if rels:
            rel_by_year[year][item.news_id] = rels
            total_relation_edges += len(rels)

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

    # Clean stale year shards
    desired_year_files = {f"{year}.json" for year in by_year}
    for existing_file in news_dir.glob("*.json"):
        if existing_file.name not in desired_year_files:
            existing_file.unlink(missing_ok=True)
    for existing_file in rel_dir.glob("*.json"):
        if existing_file.name not in desired_year_files:
            existing_file.unlink(missing_ok=True)

    file_sizes: dict[str, int] = {}
    sorted_years = sorted((y for y in by_year if y.isdigit()), key=int)
    if "unknown" in by_year:
        sorted_years.append("unknown")
    numeric_years = [y for y in sorted_years if y.isdigit()]

    for year in sorted_years:
        file_sizes[f"news/{year}.json"] = _write_json(news_dir / f"{year}.json", by_year[year], compact=True)
        file_sizes[f"relations/{year}.json"] = _write_json(
            rel_dir / f"{year}.json", rel_by_year.get(year, {}), compact=True
        )

    # Dataset SHA-256 fingerprint
    jsonl_src = vault / "資料" / "moenv_news_index.jsonl"
    dataset_sha256 = (
        hashlib.sha256(jsonl_src.read_bytes()).hexdigest()
        if jsonl_src.is_file()
        else hashlib.sha256(str(len(items)).encode("utf-8")).hexdigest()
    )

    # 1. manifest.json
    manifest_data = {
        "total_news": len(items),
        "total_relation_edges": total_relation_edges,
        "relation_mode": relations_meta.get("mode", "tfidf_only"),
        "date_start": date_start,
        "date_end": date_end,
        "updated_at": updated_at,
        "dataset_version": dataset_sha256[:16],
        "dataset_sha256": dataset_sha256,
        "topic_count": len(indexer.KEYWORD_PROFILES),
        "years": numeric_years,
        "last_30_days_count": cur_30d_total,
        "prev_30_days_count": prev_30d_total,
        "last_30_days_delta": cur_30d_total - prev_30d_total,
        "last_30_days_pct": _pct_change(cur_30d_total, prev_30d_total),
        "latest_news": latest_news_cards,
    }
    file_sizes["manifest.json"] = _write_json(out / "manifest.json", manifest_data)

    # 2. trends.json
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
            "recent_1y": [{"unit": u, "count": c} for u, c in unit_1y_counts.most_common(25)],
            "all_time": [{"unit": u, "count": c} for u, c in unit_all_counts.most_common(25)],
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

    # 4. search_index.json
    file_sizes["search_index.json"] = _write_json(out / "search_index.json", search_index, compact=True)

    # 5. research.json
    research_data = _export_research(vault)
    file_sizes["research.json"] = _write_json(out / "research.json", research_data)

    # 6. policy_graph.json (Macro Neural Network Graph)
    policy_graph = _build_policy_graph(
        items=items,
        matches_by_id=matches_by_id,
        topic_total_counts=topic_total_counts,
        topic_30d_counts=topic_30d_counts,
        topic_prev30d_counts=topic_prev30d_counts,
        relations_by_id=relations_by_id,
    )
    file_sizes["policy_graph.json"] = _write_json(out / "policy_graph.json", policy_graph)

    # 7. timelines.json (Policy Evolution Timelines)
    timelines = _export_timelines(vault, items)
    file_sizes["timelines.json"] = _write_json(out / "timelines.json", timelines)

    # 8. Academic Downloads (CSV with BOM + Methodology JSON)
    matrix_headers = ["year", "total_news", *[p.title for p in indexer.KEYWORD_PROFILES]]
    matrix_rows = [
        [y, yearly_counts[y], *[topic_year_counts[p.slug].get(y, 0) for p in indexer.KEYWORD_PROFILES]]
        for y in numeric_years
    ]
    file_sizes["downloads/moenv_topic_yearly_matrix.csv"] = _write_csv_bom(
        dl_dir / "moenv_topic_yearly_matrix.csv", matrix_headers, matrix_rows
    )

    top_units = [u for u, _ in unit_all_counts.most_common(40)]
    unit_headers = ["unit", "all_time_total", *numeric_years]
    unit_rows = [
        [u, unit_all_counts[u], *[unit_year_counts[u].get(y, 0) for y in numeric_years]]
        for u in top_units
    ]
    file_sizes["downloads/moenv_unit_yearly_stats.csv"] = _write_csv_bom(
        dl_dir / "moenv_unit_yearly_stats.csv", unit_headers, unit_rows
    )

    methodology_meta = {
        "project": "環策晧脈（Taiwan Environment Observatory）",
        "license": "資料來源：中華民國環境部（環境部新聞專區及環境資料開放平臺 MNEWS_P_01），依政府資料開放授權條款（OGDL 1.0）引用；原創分類口徑、分析與視覺化歸屬環策晧脈。",
        "updated_at": updated_at,
        "coverage": {"date_start": date_start, "date_end": date_end, "total_news": len(items)},
        "dataset_version": dataset_sha256[:16],
        "dataset_sha256": dataset_sha256,
        "deduplication": "以 news_id 為主鍵，並搭配正規化日期＋去標點去空白標題指紋（NFKC compact identity key）雙重去重，避免跨來源（官網與開放資料）重複收錄。",
        "multi_label_rule": "採「一文多標籤」口徑：單篇新聞若同時命中多項議題之同義詞表，將於對應議題各自計數 1 次，因此各議題加總高於全站新聞總篇數屬正常現象。",
        "relation_engine": {
            "name": "路線 3：雙層混合語意網絡（TF-IDF ＋ 類神經網路語意向量）",
            "layer_1": "scikit-learn TfidfVectorizer ＋ jieba 中文斷詞（掛載 20 大議題同義詞與環境法規專有名詞詞典），計算餘弦相似度 S_tfidf。",
            "layer_2": "選配 Gemini Embedding API（gemini-embedding-001）增量快取語意向量計算 S_embed；若未設 API Key 或遭遇限流，自動降級為 100% TF-IDF 權重。",
            "blend_formula": "w_ij = alpha * S_tfidf(i, j) + (1 - alpha) * S_embed(i, j) + topic_bonus (0.05)",
            "active_meta": relations_meta,
        },
        "topic_profiles": [
            {
                "slug": p.slug,
                "title": p.title,
                "group": p.group,
                "description": p.description,
                "aliases": list(p.aliases),
                "total_count": topic_total_counts[p.slug],
            }
            for p in indexer.KEYWORD_PROFILES
        ],
    }
    file_sizes["downloads/moenv_methodology_metadata.json"] = _write_json(
        dl_dir / "moenv_methodology_metadata.json", methodology_meta
    )

    total_files = len(file_sizes)
    max_file = max(file_sizes.items(), key=lambda kv: kv[1]) if file_sizes else ("", 0)
    return {
        "output_dir": str(out),
        "total_news": len(items),
        "total_relation_edges": total_relation_edges,
        "shard_sum": sum(len(v) for v in by_year.values()),
        "total_files": total_files,
        "timelines": len(timelines),
        "graph_nodes": len(policy_graph["nodes"]),
        "graph_links": len(policy_graph["links"]),
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
