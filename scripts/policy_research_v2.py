"""Research artifact helpers; never modify the canonical news inputs."""

from __future__ import annotations

import csv
import calendar
import hashlib
import json
import re
from copy import deepcopy
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "policy_research_v2.schema.json"
PIPELINE_VERSION = "2.0.1"


def read_json(path: Path):
    def reject_constant(value):
        raise ValueError(f"Nonfinite JSON number: {value}")

    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=reject_constant)


def read_markdown_metadata(path: Path) -> dict:
    import yaml

    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("Markdown frontmatter is required")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("Unclosed Markdown frontmatter") from exc
    result = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(result, dict):
        raise ValueError("Markdown frontmatter must be a mapping")
    for key in ("updated", "coverage_end"):
        date.fromisoformat(str(result[key]))
    return result


def input_fingerprints(paths: dict[str, Path]) -> dict[str, str]:
    return {name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in paths.items()}


def dataset_version(hashes: dict) -> str:
    canonical = {k: hashes[k] for k in ("news_index", "membership", "profiles", "manifest") if k in hashes}
    return "sha256:" + hashlib.sha256(json.dumps(canonical, sort_keys=True).encode("utf-8")).hexdigest()


def validate_input_fingerprints(artifact: dict, paths: dict[str, Path]) -> list[ValidationIssue]:
    expected = artifact.get("meta", {}).get("input_sha256", {})
    actual = input_fingerprints(paths)
    issues = [ValidationIssue("INPUT_FINGERPRINT_MISMATCH", f"meta.input_sha256.{key}", "Input missing or changed since compilation") for key, value in actual.items() if expected.get(key) != value]
    if artifact.get("meta", {}).get("dataset_version") != dataset_version(actual):
        issues.append(ValidationIssue("DATASET_FINGERPRINT_MISMATCH", "meta.dataset_version", "Canonical fingerprint version differs"))
    return issues


def snapshot_warnings(root: Path, news_index: dict) -> list[ValidationIssue]:
    issues = []
    for name in ("moenv_news_index.csv", "moenv_news_keywords.jsonl"):
        path = Path(root) / "資料" / name
        if not path.exists():
            issues.append(ValidationIssue("LEGACY_SNAPSHOT_MISSING", str(path), "Optional legacy snapshot not found", "warning"))
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle)) if path.suffix == ".csv" else [json.loads(line) for line in handle if line.strip()]
        ids = [r["news_id"] for r in rows]
        missing, extra = set(news_index) - set(ids), set(ids) - set(news_index)
        if missing or extra or len(ids) != len(set(ids)):
            message = f"Non-authoritative snapshot: rows={len(ids)}, missing={sorted(missing)}, extra={sorted(extra)}, duplicates={len(ids) - len(set(ids))}"
            issues.append(ValidationIssue("LEGACY_SNAPSHOT_MISMATCH", str(path), message, "warning"))
    return issues


def compile_artifact(authored, news_index, profiles, membership, manifest, markdown_metadata, generated_at, input_sha256):
    slug = authored["topic_slug"]
    profile = profiles[slug]
    end = manifest["generated_at"][:10]
    start = authored["date_from"]
    date.fromisoformat(start)
    rows = [news_index[key] for key in membership.get(slug, set())]
    if not rows or any(not start <= row["date"] <= end for row in rows):
        raise ValueError("Compilation requires a nonempty full topic snapshot")
    points = build_year_series(profile["year_counts"], end)
    peak = max((p for p in points if p["value"] is not None), key=lambda p: (p["value"], -int(p["period"])))
    sources = []
    for key in authored["source_news_ids"]:
        row = news_index[key]
        sources.append({"source_id": "moenv-news:" + key, "source_type": "moenv_news", "external_id": key, "title": row["title"], "url": row["source_url"], "published_at": row["date"], "publisher": row["unit"], "accessed_at": authored["accessed_at"]})
    result = {
        "schema_version": "2.0", "research_id": authored["research_id"],
        "topic": {"slug": slug, "name_zh": profile["title"], "description": profile["description"]},
        "scope": {"date_from": start, "date_to": end, "source": "MOENV news canonical local snapshot", "article_count": profile["total"], "query_version": "canonical-profile-v2", "filters": ["profile:" + slug], "missing_years": [str(y) for y in range(int(start[:4]), int(end[:4]) + 1) if str(y) not in profile["year_counts"]]},
        "statistics": {"total_articles": len(rows), "first_article_date": min(r["date"] for r in rows), "latest_article_date": max(r["date"] for r in rows), "peak_year": {"year": int(peak["period"]), "count": peak["value"], "period_status": peak["period_status"]}},
        "trend_series": [{"series_id": "article_count_yearly", "label": "年度新聞數", "unit": "則", "frequency": "year", "metric_type": "count", "points": points}],
        "trend_signals": build_trend_signals(points), "sources": sources,
        "quality": {"status": "needs_review", "warnings": list(dict.fromkeys(authored.get("warnings", [])))},
        "meta": {"generated_at": generated_at, "dataset_generated_at": manifest["generated_at"], "research_updated_at": str(markdown_metadata["updated"]), "narrative_coverage_end": str(markdown_metadata["coverage_end"]), "source_markdown": authored["source_markdown"], "pipeline_version": PIPELINE_VERSION, "dataset_version": dataset_version(input_sha256), "input_sha256": dict(input_sha256), "notes": authored.get("notes", "Authored claims and deterministic statistics are compiled separately; human acceptance pending.")},
    }
    for key in ("key_metrics", "key_events", "trend_insights"):
        result[key] = deepcopy(authored[key])
    if "research_summary" in authored:
        result["research_summary"] = deepcopy(authored["research_summary"])
    return result


def load_news_index(path: Path) -> dict[str, dict]:
    records = {}
    with Path(path).open(encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = row.get("news_id")
            if not isinstance(key, str) or not key.strip():
                raise ValueError("news_id must be a nonempty string")
            if key in records:
                raise ValueError(f"Duplicate news_id: {key}")
            records[key] = row
    return records


class TopicMembership(dict):
    """Topic sets plus all CSV IDs, including rows with no matched topic."""

    def __init__(self):
        super().__init__()
        self.news_ids: set[str] = set()


def load_topic_membership(path: Path) -> TopicMembership:
    result = TopicMembership()
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"news_id", "keyword_slugs"}.issubset(reader.fieldnames or []):
            raise ValueError("Membership CSV requires news_id and keyword_slugs")
        for row in reader:
            key = row["news_id"]
            if not key or key in result.news_ids or row["keyword_slugs"] is None:
                raise ValueError(f"Invalid or duplicate membership ID: {key}")
            result.news_ids.add(key)
            for slug in filter(None, (s.strip() for s in row["keyword_slugs"].split(";"))):
                result.setdefault(slug, set()).add(key)
    return result


def load_profiles(path: Path) -> dict[str, dict]:
    result = {}
    for profile in read_json(path)["profiles"]:
        slug = profile["slug"]
        if not isinstance(slug, str) or not slug or slug in result:
            raise ValueError(f"Invalid or duplicate profile slug: {slug}")
        result[slug] = profile
    return result


def build_year_series(year_counts: dict, coverage_end: str) -> list[dict]:
    cutoff = date.fromisoformat(coverage_end)
    points = []
    for year, count in sorted(year_counts.items()):
        if not isinstance(year, str) or len(year) != 4 or not year.isdigit():
            raise ValueError(f"Invalid year: {year}")
        if int(year) < 1 or int(year) > cutoff.year or type(count) is not int or count < 0:
            raise ValueError(f"Invalid year/count: {year}/{count}")
        status = "partial" if int(year) == cutoff.year and coverage_end[5:] != "12-31" else "observed"
        points.append({"period": year, "value": count, "period_status": status})
    if str(cutoff.year) not in year_counts and coverage_end[5:] != "12-31":
        points.append({"period": str(cutoff.year), "value": None, "period_status": "unknown"})
    return points


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str
    severity: str = "error"


def period_bounds(period: str, frequency: str) -> tuple[str, str]:
    patterns = {"year": r"[0-9]{4}", "month": r"[0-9]{4}-[0-9]{2}", "quarter": r"[0-9]{4}-Q[1-4]"}
    if frequency not in patterns or not re.fullmatch(patterns[frequency], period):
        raise ValueError(f"Period {period!r} does not match {frequency}")
    year = int(period[:4])
    first_month, last_month = 1, 12
    if frequency == "month":
        first_month = last_month = int(period[5:])
    elif frequency == "quarter":
        first_month = (int(period[-1]) - 1) * 3 + 1
        last_month = first_month + 2
    first = date(year, first_month, 1)
    last = date(year, last_month, calendar.monthrange(year, last_month)[1])
    return first.isoformat(), last.isoformat()


def validate_artifact(artifact, news_index, profiles, membership, manifest, *, publication=False) -> list[ValidationIssue]:
    from jsonschema import Draft202012Validator, FormatChecker

    schema = read_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    issues = []

    def add(code, path, message, severity="error"):
        issues.append(ValidationIssue(code, path, str(message), severity))

    for error in sorted(validator.iter_errors(artifact), key=lambda e: str(list(e.path))):
        path = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.path).lstrip(".")
        add("SCHEMA", path or "$", error.message)
    if issues:
        return issues

    if publication and "research_summary" not in artifact:
        add("SUMMARY_REQUIRED", "research_summary", "Publication contract requires a structured research summary")

    scope, meta = artifact["scope"], artifact["meta"]
    start, end = scope["date_from"], scope["date_to"]
    if start > end:
        add("COVERAGE_ORDER", "scope", "date_from is after date_to")
    cutoff = manifest.get("generated_at", "")[:10]
    try:
        date.fromisoformat(cutoff)
        for key, row in news_index.items():
            date.fromisoformat(row["date"])
            if row.get("news_id") != key:
                raise ValueError(f"News ID/key mismatch: {key}")
    except (ValueError, TypeError, KeyError) as exc:
        add("CANONICAL_INVALID", "canonical", exc)
        return issues
    if end > cutoff:
        add("COVERAGE_EXCEEDS_DATASET", "scope.date_to", f"{end} exceeds {cutoff}")
    if meta["dataset_generated_at"] != manifest["generated_at"]:
        add("DATASET_VERSION_MISMATCH", "meta.dataset_generated_at", "Does not match manifest")
    if manifest.get("indexed_count") != len(news_index):
        add("MANIFEST_COUNT_MISMATCH", "manifest.indexed_count", len(news_index))
    if hasattr(membership, "news_ids") and membership.news_ids != set(news_index):
        add("MEMBERSHIP_COVERAGE", "membership", "CSV IDs do not exactly cover the main table")
    for slug, ids in membership.items():
        if ids - news_index.keys():
            add("MEMBERSHIP_ID_NOT_FOUND", f"membership.{slug}", sorted(ids - news_index.keys()))
        if slug not in profiles:
            add("PROFILE_NOT_FOUND", f"membership.{slug}", slug)
    for slug, profile in profiles.items():
        ids = membership.get(slug, set())
        if profile.get("total") != len(ids):
            add("PROFILE_TOTAL_MISMATCH", f"profiles.{slug}.total", f"Expected {len(ids)}")
        counts = dict(Counter(news_index[k]["date"][:4] for k in ids if k in news_index))
        if profile.get("year_counts") != counts:
            add("PROFILE_YEARS_MISMATCH", f"profiles.{slug}.year_counts", "Counts differ from canonical membership")

    slug = artifact["topic"]["slug"]
    if slug not in profiles:
        add("PROFILE_NOT_FOUND", "topic.slug", slug)
    else:
        profile = profiles[slug]
        for field, original in (("name_zh", "title"), ("description", "description")):
            if artifact["topic"][field] != profile.get(original):
                add("TOPIC_MISMATCH", f"topic.{field}", "Does not match canonical profile")
        ids = membership.get(slug, set()) & news_index.keys()
        rows = [news_index[k] for k in ids]
        selected = [r for r in rows if start <= r["date"] <= end]
        if len(selected) != len(rows):
            add("PROFILE_SCOPE_INCOMPLETE", "scope", "Pilot profile contract requires the full topic snapshot")
        if scope["article_count"] != profile["total"]:
            add("ARTICLE_COUNT_MISMATCH", "scope.article_count", f"Expected {profile['total']}")
        if rows:
            counts = dict(Counter(r["date"][:4] for r in selected))
            expected = build_year_series(counts, end)
            numeric = [p for p in expected if p["value"] is not None]
            if numeric:
                # Peak includes partial years but explicitly carries its status; ties choose earliest.
                peak = max(numeric, key=lambda p: (p["value"], -int(p["period"])))
                expected_stats = {
                    "total_articles": len(selected),
                    "first_article_date": min(r["date"] for r in selected),
                    "latest_article_date": max(r["date"] for r in selected),
                    "peak_year": {"year": int(peak["period"]), "count": peak["value"], "period_status": peak["period_status"]},
                }
                if artifact["statistics"] != expected_stats:
                    add("STATISTICS_MISMATCH", "statistics", "Statistics differ from canonical rows")
            for i, series in enumerate(artifact["trend_series"]):
                if series["series_id"] == "article_count_yearly" and series["points"] != expected:
                    add("SERIES_MISMATCH", f"trend_series[{i}].points", "Expected canonical yearly counts and period status")
            missing = [str(y) for y in range(int(start[:4]), int(end[:4]) + 1) if str(y) not in counts]
            if scope.get("missing_years", []) != missing:
                add("MISSING_YEAR_METADATA", "scope.missing_years", missing)

    groups = {"sources": "source_id", "key_metrics": "metric_id", "key_events": "event_id", "trend_insights": "insight_id", "trend_series": "series_id", "trend_signals": "signal_id"}
    all_ids = set()
    for group, key in groups.items():
        for i, record in enumerate(artifact.get(group, [])):
            if record[key] in all_ids:
                add("DUPLICATE_ID", f"{group}[{i}].{key}", record[key])
            all_ids.add(record[key])

    source_ids = {s["source_id"] for s in artifact["sources"]}
    evidence_ids = {r[key] for group, key in groups.items() if group in {"key_metrics", "key_events", "trend_signals"} for r in artifact.get(group, [])}
    records = [(f"{group}[{i}]", r) for group in ("key_metrics", "key_events", "trend_insights") for i, r in enumerate(artifact[group])]
    records.extend((f"trend_series[{i}]", series) for i, series in enumerate(artifact["trend_series"]) if "source_ids" in series)
    if "research_summary" in artifact:
        records.append(("research_summary", artifact["research_summary"]))
        records.extend((f"research_summary.phases[{i}]", p) for i, p in enumerate(artifact["research_summary"].get("phases", [])))
    for path, record in records:
        for j, ref in enumerate(record["source_ids"]):
            if ref not in source_ids:
                add("SOURCE_NOT_FOUND", f"{path}.source_ids[{j}]", ref)
        for j, ref in enumerate(record.get("evidence_refs", [])):
            if ref not in evidence_ids:
                add("EVIDENCE_NOT_FOUND", f"{path}.evidence_refs[{j}]", ref)

    for i, source in enumerate(artifact["sources"]):
        path = f"sources[{i}]"
        if source["source_type"] != "moenv_news":
            continue
        if not source.get("external_id") or not source.get("published_at"):
            add("MOENV_SOURCE_REQUIRED", path, "external_id and published_at are required")
            continue
        key = source["external_id"]
        if key not in news_index:
            add("NEWS_NOT_FOUND", path + ".external_id", key)
            continue
        row = news_index[key]
        pairs = {"source_id": "moenv-news:" + key, "title": row["title"], "published_at": row["date"], "url": row["source_url"]}
        if "publisher" in source:
            pairs["publisher"] = row["unit"]
        for field, expected in pairs.items():
            if source[field] != expected:
                add("SOURCE_MISMATCH", path + "." + field, "Does not match canonical news")
        if row["date"] > end:
            add("SOURCE_AFTER_COVERAGE", path, row["date"])

    for i, series in enumerate(artifact["trend_series"]):
        news_series = series["series_id"] == "article_count_yearly"
        if news_series and (series["frequency"], series["metric_type"], series["unit"]) != ("year", "count", "則"):
            add("NEWS_SERIES_CONTRACT", f"trend_series[{i}]", "article_count_yearly requires year/count/則")
        if not news_series and not series.get("source_ids"):
            add("SERIES_SOURCE_REQUIRED", f"trend_series[{i}].source_ids", "Non-news series requires explicit source provenance")
        periods = [p["period"] for p in series["points"]]
        if periods != sorted(set(periods)):
            add("SERIES_PERIOD_ORDER", f"trend_series[{i}].points", "Periods must be unique and sorted")
        for j, point in enumerate(series["points"]):
            path = f"trend_series[{i}].points[{j}]"
            try:
                period_bounds(point["period"], series["frequency"])
            except ValueError as exc:
                add("SERIES_PERIOD_INVALID", path + ".period", exc)
            if news_series and point["period"] == end[:4] and end[5:] != "12-31" and point["value"] is not None and point["period_status"] != "partial":
                add("PARTIAL_YEAR_REQUIRED", path, "Incomplete cutoff year must be partial")
            if news_series and point["period_status"] == "zero":
                add("ZERO_UNVERIFIED", path, "No coverage_complete evidence exists in this pilot contract")
    for i, event in enumerate(artifact["key_events"]):
        try:
            if event["date_precision"] == "day":
                lower = upper = date.fromisoformat(event["date"]).isoformat()
            else:
                # Bounds are only for scope checks, never substituted into the event's date.
                lower, upper = period_bounds(event["date"], event["date_precision"])
        except ValueError as exc:
            add("EVENT_DATE_INVALID", f"key_events[{i}].date", exc)
            continue
        if upper < start or lower > end:
            add("EVENT_OUTSIDE_SCOPE", f"key_events[{i}].date", event["date"])
        elif lower < start or upper > end:
            add("EVENT_SCOPE_UNCERTAIN", f"key_events[{i}].date", "Imprecise event period overlaps a scope boundary; exact inclusion is unknown", "warning")
    for i, insight in enumerate(artifact["trend_insights"]):
        period = insight["period"]
        if not start[:4] <= period["from"] <= period["to"] <= end[:4]:
            add("INSIGHT_PERIOD", f"trend_insights[{i}].period", period)
        if insight["confidence"] == "low" and artifact["quality"]["status"] in {"passed", "passed_with_warnings"}:
            add("LOW_CONFIDENCE_REVIEW_REQUIRED", f"trend_insights[{i}]", "Low-confidence insight cannot claim publication-ready quality")
    if artifact["quality"]["status"] == "failed":
        add("QUALITY_FAILED", "quality.status", "Artifact declares failed quality")
    if "trend_signals" in artifact:
        try:
            news_series = next((s for s in artifact["trend_series"] if s["series_id"] == "article_count_yearly"), None)
            expected_signals = build_trend_signals(news_series["points"]) if news_series else []
            if artifact["trend_signals"] != expected_signals:
                add("SIGNALS_MISMATCH", "trend_signals", "Signals differ from deterministic rules")
        except ValueError as exc:
            add("SIGNALS_MISMATCH", "trend_signals", exc)
    for warning in artifact["quality"]["warnings"]:
        add("AUTHOR_WARNING", "quality.warnings", warning, "warning")
    if artifact["quality"]["status"] == "needs_review":
        add("HUMAN_REVIEW_REQUIRED", "quality.status", "Technical validation does not constitute human acceptance", "warning")
    if manifest.get("site_total") is None:
        add("OFFICIAL_TOTAL_UNKNOWN", "manifest.site_total", "Cannot establish full-site completeness", "warning")
    if meta.get("narrative_coverage_end", end) < end:
        add("NARRATIVE_SNAPSHOT_DIFFERS", "meta.narrative_coverage_end", "Narrative and statistics have different cutoffs", "warning")
    return issues


def build_trend_signals(points: list[dict]) -> list[dict]:
    """Conservative annual descriptive signals, excluding partial/unknown years."""
    years = [int(p["period"]) for p in points]
    if years != sorted(set(years)):
        raise ValueError("Periods must be unique and sorted")
    signals = []

    def complete(window):
        return bool(window) and all(p["period_status"] == "observed" and type(p["value"]) is int and p["value"] >= 0 for p in window) and all(int(b["period"]) - int(a["period"]) == 1 for a, b in zip(window, window[1:]))

    def emit(kind, point, baseline, method, description):
        signals.append({
            "signal_id": f"signal-{kind}-{point['period']}",
            "type": kind, "period": point["period"], "series_id": "article_count_yearly",
            "value": point["value"], "baseline": baseline, "strength": "medium",
            "method": method, "description": description,
        })

    for i, point in enumerate(points):
        if i >= 1 and complete(points[i - 1:i + 1]):
            previous = points[i - 1]["value"]
            delta = point["value"] - previous
            if previous >= 5 and abs(delta) >= 5 and abs(delta) / previous >= 0.5:
                kind = "rapid_growth" if delta > 0 else "rapid_decline"
                emit(kind, point, previous, "yoy_base_ge5_abs_delta_ge5_ratio_ge0.5", "完整相鄰年度新聞量變動達門檻；不代表政策成效或因果。")
        if i >= 2 and complete(points[i - 2:i + 1]):
            a, b, c = [p["value"] for p in points[i - 2:i + 1]]
            if b - a >= 5 and c - b >= 5:
                emit("sustained_growth", point, a, "three_consecutive_years_each_delta_ge5", "三個連續完整年度，每次增加至少五則；屬新聞關注度訊號。")
            elif a - b >= 5 and b - c >= 5:
                emit("sustained_decline", point, a, "three_consecutive_years_each_delta_le_minus5", "三個連續完整年度，每次減少至少五則；屬新聞關注度訊號。")
        if i >= 3 and i + 1 < len(points) and complete(points[i - 3:i + 2]):
            baseline = sum(p["value"] for p in points[i - 3:i]) / 3
            value = point["value"]
            if baseline >= 5 and value >= baseline * 1.5 and value - baseline >= 10 and value > points[i - 1]["value"] and value > points[i + 1]["value"]:
                emit("peak", point, baseline, "local_peak_prior3_mean_ratio_ge1.5_delta_ge10", "局部高點高於前三個完整年度平均至少50%及十則；非政策效果估計。")
    return signals
