#!/usr/bin/env python3
"""Incremental MOENV Open Data (MNEWS_P_01) sync + URL resolver + candidate radar + Gemini enricher."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ai_enricher  # noqa: E402
import moenv_news_indexer as indexer  # noqa: E402

TAIPEI_TZ = timezone(timedelta(hours=8))
OPENDATA_ENDPOINT = "https://data.moenv.gov.tw/api/v2/mnews_p_01"
NEW_ARTICLE_URL_TEMPLATE = "https://enews.moenv.gov.tw/moenv-news/zh-tw/News/{news_id}"
SINGLE_ARTICLE_URL_RE = re.compile(
    r"^https?://enews\.moenv\.gov\.tw/(?:moenv-news/zh-tw/News/\d+|Page/3B3C62C78849F32F/[^/?#]+)",
    re.I,
)
NUMERIC_ARTICLE_URL_RE = re.compile(r"/moenv-news/zh-tw/News/(\d+)", re.I)
LIST_OR_HOME_URL_RE = re.compile(r"(?:/News/List|/Page/B514A5023133ED27)", re.I)
HTML_H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
HTML_TITLE_RE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.I | re.S)
OG_TITLE_RE = re.compile(r'<meta\b[^>]*property=["\']og:title["\'][^>]*content=["\'](.*?)["\']', re.I | re.S)

DEFAULT_LIMIT = 1000
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_OVERLAP_DAYS = 14
DEFAULT_PROBE_RANGE = 40

HIGH_SIGNAL_TERMS: tuple[str, ...] = (
    "修正",
    "預告",
    "草案",
    "費率",
    "徵收",
    "施行",
    "辦法",
    "準則",
    "列管",
    "裁罰",
    "COP",
    "淨零",
)


def load_local_env_files(vault: Path) -> None:
    """Load local .env / key.env into os.environ only for variables not already set."""
    for filename in (".env", "key.env"):
        env_path = vault / filename
        if not env_path.is_file():
            continue
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ and value:
                    os.environ[key] = value
        except OSError:
            continue


def iso_to_roc_date(iso_date: str) -> str:
    """Convert YYYY-MM-DD to ROC date YYY-MM-DD."""
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", iso_date.strip())
    if not match:
        return ""
    year = int(match.group(1)) - 1911
    return f"{year}-{match.group(2)}-{match.group(3)}"


def parse_news_date(raw_value: Any) -> tuple[str, str]:
    """Parse MNEWS_P_01 newsdate into (YYYY-MM-DD, YYY-MM-DD)."""
    text = str(raw_value or "").strip()
    if not text:
        return "", ""
    match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if match:
        iso = f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        return iso, iso_to_roc_date(iso)
    compact = re.match(r"^(\d{4})(\d{2})(\d{2})", text)
    if compact:
        iso = f"{compact.group(1)}-{compact.group(2)}-{compact.group(3)}"
        return iso, iso_to_roc_date(iso)
    roc = re.match(r"^(\d{2,3})[-/](\d{1,2})[-/](\d{1,2})", text)
    if roc:
        roc_str = f"{int(roc.group(1))}-{int(roc.group(2)):02d}-{int(roc.group(3)):02d}"
        return indexer.roc_to_iso(roc_str), roc_str
    return "", ""


def clean_optional_url(raw_value: Any) -> str:
    text = str(raw_value or "").strip()
    if not text or text in {"-", "null", "None", "N/A"}:
        return ""
    return text


def is_official_single_article_url(url: str) -> bool:
    """Return True only when url points to a single official MOENV news article (never list/home)."""
    cleaned = (url or "").strip()
    if not cleaned or LIST_OR_HOME_URL_RE.search(cleaned):
        return False
    return bool(SINGLE_ARTICLE_URL_RE.match(cleaned))


def is_deleted_record(record: dict[str, Any]) -> bool:
    mark = str(record.get("deletemark") or "").strip()
    return mark not in {"", "0"}


def build_opendata_url(api_key: str, limit: int = DEFAULT_LIMIT, offset: int = 0) -> str:
    params = urlencode(
        {
            "api_key": api_key,
            "format": "JSON",
            "limit": str(limit),
            "offset": str(offset),
            "sort": "NewsDate desc",
        }
    )
    return f"{OPENDATA_ENDPOINT}?{params}"


def fetch_json_with_backoff(
    url: str,
    retries: int = DEFAULT_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        req = Request(
            url,
            headers={
                "User-Agent": indexer.USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                delay = 2**attempt
                print(
                    f"[WARN] Open Data request failed (attempt {attempt + 1}/{retries}): {exc}. Retrying in {delay}s...",
                    file=sys.stderr,
                )
                sleep_fn(delay)
    raise RuntimeError(f"Failed to fetch MOENV Open Data after {retries} attempts: {last_error}") from last_error


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        records = payload.get("records")
        if isinstance(records, list):
            return [r for r in records if isinstance(r, dict)]
    return []


def compact_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title or "").lower()
    return re.sub(r"[\s\W_]+", "", normalized)


def compact_title_key(date: str, title: str) -> tuple[str, str]:
    """Whitespace- and punctuation-insensitive (date, title) fingerprint for cross-source dedup."""
    return (date.strip(), compact_title(title))


def parse_opendata_record(record: dict[str, Any]) -> tuple[indexer.NewsItem, str] | None:
    """Convert one MNEWS_P_01 record into (NewsItem, raw_content) or None if skipped."""
    if is_deleted_record(record):
        return None
    news_id = str(record.get("newsno") or "").strip()
    title = indexer.clean_text(str(record.get("newstitle") or ""))
    if not news_id or not title:
        return None

    iso_date, roc_date = parse_news_date(record.get("newsdate"))
    if not iso_date:
        return None

    unit = indexer.clean_text(str(record.get("newssource") or "")) or "未標示"
    raw_source_url = clean_optional_url(record.get("relativeurl"))
    if is_official_single_article_url(raw_source_url):
        source_url = raw_source_url
        source_url_status = ""
    else:
        source_url = ""
        source_url_status = "pending_official_link"

    attach_url = clean_optional_url(record.get("attachurl"))
    raw_content = str(record.get("newscontent") or "")

    item = indexer.NewsItem(
        news_id=news_id,
        title=title,
        roc_date=roc_date,
        date=iso_date,
        category="環境部新聞",
        unit=unit,
        views=None,
        summary="",
        source_url=source_url,
        image_url="",
        site_topics=[],
        note_path="",
        body="",
        attach_url=attach_url,
        ai_tags=[],
        ai_policy_keywords=[],
        source_url_status=source_url_status,
    )
    return item, raw_content


def extract_html_page_title(html: str) -> str:
    """Extract the article headline from MOENV detail HTML (<meta og:title>, <h1>, or <title>)."""
    for pattern in (OG_TITLE_RE, HTML_H1_RE, HTML_TITLE_RE):
        for match in pattern.findall(html or ""):
            cleaned = indexer.clean_text(unescape(re.sub(r"<[^>]+>", " ", match)))
            # Strip trailing site suffix like " - 環境部新聞專區"
            cleaned = re.sub(r"\s*[-|｜–—]\s*(?:環境部新聞專區|環境部).*$", "", cleaned).strip()
            if cleaned and cleaned not in {"環境部新聞專區", "新聞專區", "Just a moment..."}:
                return cleaned
    return ""


def _max_known_numeric_article_id(items: list[indexer.NewsItem]) -> int:
    max_id = 0
    for item in items:
        m = NUMERIC_ARTICLE_URL_RE.search(item.source_url or "")
        if m:
            max_id = max(max_id, int(m.group(1)))
        elif item.news_id.isdigit() and len(item.news_id) <= 7:
            max_id = max(max_id, int(item.news_id))
    return max_id


def _fetch_html_quiet(url: str, timeout: int = 12) -> str:
    req = Request(url, headers=indexer.BROWSER_HEADERS)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _titles_match(target_compact: str, candidate_compact: str) -> bool:
    if not target_compact or not candidate_compact:
        return False
    if target_compact == candidate_compact:
        return True
    shorter, longer = (
        (target_compact, candidate_compact)
        if len(target_compact) <= len(candidate_compact)
        else (candidate_compact, target_compact)
    )
    return len(shorter) >= 12 and shorter in longer


def resolve_official_article_urls(
    items_to_resolve: list[indexer.NewsItem],
    all_items: list[indexer.NewsItem],
    timeout: int = 12,
    probe_range: int = DEFAULT_PROBE_RANGE,
    delay: float = 0.15,
    list_fetcher: Callable[[int], list[indexer.NewsItem]] | None = None,
    detail_fetcher: Callable[[str], str] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> set[str]:
    """
    Resolve official single-article URLs for items missing one.
    1) Check official list pages 1-2 (by date + compact title, or compact title alone).
    2) Probe sequential numeric IDs after max known official ID (up to +probe_range).
    3) Strict zero-homepage rule: unresolved items get source_url='' and
       source_url_status='pending_official_link'.
    Returns set of news_ids whose source_url or source_url_status changed.
    """
    changed_ids: set[str] = set()
    unresolved: list[indexer.NewsItem] = []

    for item in items_to_resolve:
        if is_official_single_article_url(item.source_url):
            if item.source_url_status:
                item.source_url_status = ""
                changed_ids.add(item.news_id)
            continue
        # Strip any legacy list/home URL immediately
        if item.source_url:
            item.source_url = ""
            changed_ids.add(item.news_id)
        if item.source_url_status != "pending_official_link":
            item.source_url_status = "pending_official_link"
            changed_ids.add(item.news_id)
        unresolved.append(item)

    if not unresolved:
        return changed_ids

    # Strategy 1: Official list pages 1-2
    list_candidates: list[indexer.NewsItem] = []
    for page in (1, 2):
        try:
            if list_fetcher is not None:
                page_items = list_fetcher(page)
            else:
                html = indexer.fetch_new_list_page(page, retries=2, timeout=timeout)
                page_items = indexer.parse_list_page(html)
            list_candidates.extend(page_items)
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] URL resolver list page {page} skipped: {exc}", file=sys.stderr)
            break

    still_unresolved: list[indexer.NewsItem] = []
    for item in unresolved:
        target_c = compact_title(item.title)
        matched_url = ""
        for cand in list_candidates:
            if not is_official_single_article_url(cand.source_url):
                continue
            cand_c = compact_title(cand.title)
            if _titles_match(target_c, cand_c):
                matched_url = cand.source_url
                break
        if matched_url:
            item.source_url = matched_url
            item.source_url_status = ""
            changed_ids.add(item.news_id)
        else:
            still_unresolved.append(item)

    # Strategy 2: Sequential numeric ID probe from max known official ID
    if still_unresolved and probe_range > 0:
        max_id = _max_known_numeric_article_id([*all_items, *list_candidates])
        if max_id > 0:
            fetcher = detail_fetcher or (lambda u: _fetch_html_quiet(u, timeout=timeout))
            remaining = list(still_unresolved)
            consecutive_misses = 0
            for offset in range(1, probe_range + 1):
                if not remaining:
                    break
                cand_id = max_id + offset
                cand_url = NEW_ARTICLE_URL_TEMPLATE.format(news_id=cand_id)
                try:
                    html = fetcher(cand_url)
                    page_title = extract_html_page_title(html)
                except Exception:  # noqa: BLE001
                    consecutive_misses += 1
                    if consecutive_misses >= 10:
                        break
                    if delay > 0:
                        sleep_fn(delay)
                    continue

                if not page_title:
                    consecutive_misses += 1
                    if consecutive_misses >= 10:
                        break
                else:
                    consecutive_misses = 0
                    cand_c = compact_title(page_title)
                    matched_item = None
                    for item in remaining:
                        if _titles_match(compact_title(item.title), cand_c):
                            matched_item = item
                            break
                    if matched_item is not None:
                        matched_item.source_url = cand_url
                        matched_item.source_url_status = ""
                        changed_ids.add(matched_item.news_id)
                        remaining.remove(matched_item)

                if delay > 0:
                    sleep_fn(delay)

    return changed_ids


def write_candidate_radar(vault: Path, items: list[indexer.NewsItem], generated_at: str) -> Path:
    """Generate 04_晧哥說/00_待把脈候選雷達.md from high-signal news in the last 14 days."""
    radar_path = vault / "04_晧哥說" / "00_待把脈候選雷達.md"
    radar_path.parent.mkdir(parents=True, exist_ok=True)

    dates = sorted(item.date for item in items if item.date)
    if not dates:
        anchor_dt = datetime.now(TAIPEI_TZ).replace(tzinfo=None)
    else:
        anchor_dt = datetime.strptime(dates[-1], "%Y-%m-%d")
    window_start = (anchor_dt - timedelta(days=13)).strftime("%Y-%m-%d")
    window_end = anchor_dt.strftime("%Y-%m-%d")

    matches_by_id = indexer.build_keyword_matches(items)
    scored: list[tuple[int, str, list[str], indexer.NewsItem, list[str]]] = []

    for item in items:
        if not item.date or item.date < window_start:
            continue
        hit_terms: list[str] = []
        score = 0
        title_text = item.title or ""
        summary_text = item.summary or ""
        for term in HIGH_SIGNAL_TERMS:
            in_title = term.lower() in title_text.lower()
            in_summary = term.lower() in summary_text.lower()
            if in_title or in_summary:
                hit_terms.append(term)
                score += (2 if in_title else 0) + (1 if in_summary else 0)
        if score > 0:
            topics = [m.profile.title for m in matches_by_id.get(item.news_id, [])]
            scored.append((score, item.date, hit_terms, item, topics))

    scored.sort(key=lambda row: (-row[0], row[1]), reverse=False)
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)

    lines = [
        "---",
        'title: "待把脈候選雷達（近 14 天高政策訊號新聞）"',
        f"date: {window_end}",
        "status: draft",
        'summary: "系統自動從近 14 天環境部新聞篩選具高政策訊號之候選題目，供《晧哥說》把脈挑題使用。"',
        "---",
        "",
        "# 待把脈候選雷達（近 14 天高政策訊號）",
        "",
        f"- 掃描區間：`{window_start}` ～ `{window_end}`",
        f"- 更新時間：`{generated_at}`",
        f"- 候選篇數：**{len(scored)}** 篇（訊號詞：{'、'.join(HIGH_SIGNAL_TERMS)}）",
        "",
    ]

    if not scored:
        lines.append("（近 14 天內暫無命中高政策訊號詞的新聞。）")
    else:
        lines.extend(
            [
                "| 訊號分 | 日期 | 新聞標題 | 發布單位 | 議題 | 命中訊號 | 原文連結 |",
                "| ---: | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for score, date_str, hit_terms, item, topics in scored[:40]:
            safe_title = item.title.replace("|", "｜")
            topic_str = "、".join(topics[:3]) if topics else "—"
            signal_str = "、".join(hit_terms[:5])
            link_str = f"[原文]({item.source_url})" if item.source_url else "同步中"
            lines.append(
                f"| {score} | {date_str} | {safe_title} | {item.unit or '未標示'} | {topic_str} | {signal_str} | {link_str} |"
            )

    lines.append("")
    radar_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return radar_path


def fetch_incremental_records(
    api_key: str,
    cutoff_date: str | None,
    limit: int = DEFAULT_LIMIT,
    max_pages: int = 20,
    retries: int = DEFAULT_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
    fetch_fn: Callable[[str, int, int], Any] | None = None,
) -> list[dict[str, Any]]:
    """Fetch paginated Open Data records sorted by NewsDate desc until cutoff_date is passed."""
    collected: list[dict[str, Any]] = []
    fetcher = fetch_fn or (lambda u, r, t: fetch_json_with_backoff(u, retries=r, timeout=t))

    for page in range(max_pages):
        offset = page * limit
        url = build_opendata_url(api_key=api_key, limit=limit, offset=offset)
        payload = fetcher(url, retries, timeout)
        records = extract_records(payload)
        if not records:
            break
        collected.extend(records)

        if len(records) < limit:
            break

        if cutoff_date:
            dates = [parse_news_date(r.get("newsdate"))[0] for r in records]
            valid_dates = [d for d in dates if d]
            if valid_dates and min(valid_dates) < cutoff_date:
                break

    return collected


def compute_cutoff_date(existing_items: list[indexer.NewsItem], overlap_days: int = DEFAULT_OVERLAP_DAYS) -> str | None:
    dates = sorted(item.date for item in existing_items if item.date)
    if not dates:
        return None
    latest = datetime.strptime(dates[-1], "%Y-%m-%d")
    return (latest - timedelta(days=overlap_days)).strftime("%Y-%m-%d")


def sync_opendata(
    vault: Path,
    moenv_api_key: str,
    gemini_api_key: str | None = None,
    limit: int = DEFAULT_LIMIT,
    max_pages: int = 20,
    retries: int = DEFAULT_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
    overlap_days: int = DEFAULT_OVERLAP_DAYS,
    summary_chars: int = 500,
    dry_run: bool = False,
    force_rebuild: bool = False,
    resolve_urls: bool = True,
    fetch_fn: Callable[[str, int, int], Any] | None = None,
    gemini_client: Any | None = None,
    list_fetcher: Callable[[int], list[indexer.NewsItem]] | None = None,
    detail_fetcher: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Run incremental Open Data sync + URL resolver + dual-track enricher + candidate radar."""
    existing_items = indexer.load_existing_items(vault)
    existing_ids = {item.news_id for item in existing_items}
    existing_identities = {indexer.item_identity_key(item) for item in existing_items}
    existing_compact = {compact_title_key(item.date, item.title) for item in existing_items}
    cutoff_date = compute_cutoff_date(existing_items, overlap_days=overlap_days)

    raw_records = fetch_incremental_records(
        api_key=moenv_api_key,
        cutoff_date=cutoff_date,
        limit=limit,
        max_pages=max_pages,
        retries=retries,
        timeout=timeout,
        fetch_fn=fetch_fn,
    )

    new_items: list[indexer.NewsItem] = []
    seen_new_ids: set[str] = set()
    seen_new_identities: set[tuple[str, str]] = set()
    seen_new_compact: set[tuple[str, str]] = set()
    gemini_used_count = 0
    gemini_fallback_count = 0

    for record in raw_records:
        parsed = parse_opendata_record(record)
        if parsed is None:
            continue
        item, raw_content = parsed
        if cutoff_date and item.date < cutoff_date:
            continue

        identity = indexer.item_identity_key(item)
        compact = compact_title_key(item.date, item.title)

        if (
            item.news_id in existing_ids
            or identity in existing_identities
            or compact in existing_compact
            or item.news_id in seen_new_ids
            or identity in seen_new_identities
            or compact in seen_new_compact
        ):
            continue

        seen_new_ids.add(item.news_id)
        seen_new_identities.add(identity)
        seen_new_compact.add(compact)

        enrichment = ai_enricher.enrich_news_item(
            title=item.title,
            content=raw_content,
            unit=item.unit,
            date=item.date,
            category=item.category,
            summary_chars=summary_chars,
            api_key=gemini_api_key,
            client=gemini_client,
        )
        item.summary = enrichment.summary
        item.ai_policy_keywords = enrichment.policy_keywords
        item.ai_tags = enrichment.ai_tags
        if enrichment.policy_keywords:
            item.category = enrichment.policy_keywords[0]
        if enrichment.used_gemini:
            gemini_used_count += 1
        elif enrichment.fallback_reason:
            gemini_fallback_count += 1

        new_items.append(item)

    merged_items = [*existing_items, *new_items]

    # Collect items needing official single-article URL resolution:
    # - all new items
    # - any existing item with list/home URL or pending_official_link within 14d (or any list URL globally)
    url_changed_ids: set[str] = set()
    if resolve_urls:
        pending_existing = [
            item
            for item in existing_items
            if (
                LIST_OR_HOME_URL_RE.search(item.source_url or "")
                or (
                    (not item.source_url or item.source_url_status == "pending_official_link")
                    and (not cutoff_date or item.date >= cutoff_date)
                )
            )
        ]
        url_changed_ids = resolve_official_article_urls(
            items_to_resolve=[*new_items, *pending_existing],
            all_items=merged_items,
            list_fetcher=list_fetcher,
            detail_fetcher=detail_fetcher,
        )

    generated_at = datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")
    total_after = len(merged_items)
    notes_to_write = {item.news_id for item in new_items} | url_changed_ids

    if not dry_run and (new_items or url_changed_ids or force_rebuild):
        indexer.write_outputs(
            vault=vault,
            items=merged_items,
            generated_at=generated_at,
            total_from_site=None,
            mode="opendata_incremental",
            new_count=len(new_items),
            note_ids_to_write=notes_to_write if not force_rebuild else None,
        )

    if not dry_run:
        write_candidate_radar(vault, merged_items, generated_at)

    resolved_now = sum(
        1
        for item in merged_items
        if item.news_id in url_changed_ids and is_official_single_article_url(item.source_url)
    )
    pending_count = sum(
        1 for item in merged_items if item.source_url_status == "pending_official_link" or not item.source_url
    )

    latest_date = max((item.date for item in merged_items if item.date), default="")
    return {
        "generated_at": generated_at,
        "existing_count": len(existing_items),
        "fetched_records": len(raw_records),
        "new_count": len(new_items),
        "total_count": total_after,
        "latest_date": latest_date,
        "new_ids": [item.news_id for item in new_items],
        "url_resolved_count": resolved_now,
        "url_pending_count": pending_count,
        "gemini_used_count": gemini_used_count,
        "gemini_fallback_count": gemini_fallback_count,
        "dry_run": dry_run,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incremental MOENV Open Data (MNEWS_P_01) sync + URL resolver + candidate radar."
    )
    parser.add_argument("--vault", type=Path, default=Path.cwd(), help="Path to Obsidian vault root.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Records per API page (default: 1000).")
    parser.add_argument("--max-pages", type=int, default=20, help="Maximum pages to fetch per run.")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="HTTP retry attempts.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds.")
    parser.add_argument("--overlap-days", type=int, default=DEFAULT_OVERLAP_DAYS, help="Overlap lookback window in days.")
    parser.add_argument("--summary-chars", type=int, default=500, help="Max summary characters.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and enrich without writing files.")
    parser.add_argument("--force-rebuild", action="store_true", help="Rebuild indexes even if 0 new items.")
    parser.add_argument("--no-resolve-urls", action="store_true", help="Skip official single-article URL resolution.")
    parser.add_argument("--no-dotenv", action="store_true", help="Do not load local .env/key.env files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    vault = args.vault.resolve()
    if not args.no_dotenv:
        load_local_env_files(vault)

    moenv_api_key = os.environ.get("MOENV_API_KEY", "").strip()
    if not moenv_api_key:
        print("[ERROR] MOENV_API_KEY is not set. Set it in environment or .env.", file=sys.stderr)
        return 1

    gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    result = sync_opendata(
        vault=vault,
        moenv_api_key=moenv_api_key,
        gemini_api_key=gemini_api_key,
        limit=args.limit,
        max_pages=args.max_pages,
        retries=args.retries,
        timeout=args.timeout,
        overlap_days=args.overlap_days,
        summary_chars=args.summary_chars,
        dry_run=args.dry_run,
        force_rebuild=args.force_rebuild,
        resolve_urls=not args.no_resolve_urls,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
