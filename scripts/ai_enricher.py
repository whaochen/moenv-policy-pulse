#!/usr/bin/env python3
"""Dual-track zero-cost news enrichment: rule engine + optional Gemini Free Tier."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import moenv_news_indexer as indexer  # noqa: E402

GEMINI_MODEL = "gemini-2.5-flash-lite"
VALID_TOPIC_TITLES: tuple[str, ...] = tuple(p.title for p in indexer.KEYWORD_PROFILES)
VALID_TOPIC_SET: frozenset[str] = frozenset(VALID_TOPIC_TITLES)


@dataclass
class EnrichmentResult:
    summary: str
    policy_keywords: list[str] = field(default_factory=list)
    ai_tags: list[str] = field(default_factory=list)
    used_gemini: bool = False
    fallback_reason: str = ""


def extract_first_paragraph_summary(raw_html_or_text: str, max_chars: int = 500) -> str:
    """Clean HTML tags and return the first non-empty paragraph (<= max_chars)."""
    if not raw_html_or_text:
        return ""
    if "<" in raw_html_or_text and ">" in raw_html_or_text:
        for raw_paragraph in indexer.PARAGRAPH_RE.findall(raw_html_or_text):
            cleaned = indexer.clean_text(raw_paragraph)
            if cleaned:
                return indexer.truncate_text(cleaned, max_chars)
        parsed = indexer.parse_detail_summary(raw_html_or_text, max_chars=max_chars)
        if parsed:
            return parsed
    text = indexer.clean_html_to_markdown(raw_html_or_text)
    paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    first = paragraphs[0] if paragraphs else indexer.clean_text(raw_html_or_text)
    return indexer.truncate_text(first, max_chars)


def rule_engine_enrich(
    title: str,
    content: str,
    unit: str = "",
    category: str = "",
    summary_chars: int = 500,
) -> EnrichmentResult:
    """Layer 1 (mandatory): pure-Python rule engine using the 20 KEYWORD_PROFILES."""
    clean_body = indexer.clean_html_to_markdown(content) if content else ""
    summary = extract_first_paragraph_summary(content, max_chars=summary_chars)
    search_text = indexer.clean_text(" ".join(part for part in (title, category, unit, summary, clean_body) if part))

    matched_titles: list[str] = []
    for profile in indexer.KEYWORD_PROFILES:
        if any(indexer.count_alias(search_text, alias) > 0 for alias in profile.aliases):
            matched_titles.append(profile.title)

    return EnrichmentResult(
        summary=summary,
        policy_keywords=matched_titles,
        ai_tags=[],
        used_gemini=False,
    )


def _build_response_schema() -> dict[str, Any]:
    return {
        "type": "OBJECT",
        "properties": {
            "summary": {
                "type": "STRING",
                "description": "120 至 200 字的繁體中文精簡政策重點摘要，忠於原文事實不杜撰數據。",
            },
            "policy_keywords": {
                "type": "ARRAY",
                "items": {
                    "type": "STRING",
                    "enum": list(VALID_TOPIC_TITLES),
                },
                "description": "從既定 20 大環境政策議題標準名稱中選出最相關者。",
            },
            "ai_tags": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "最多 3 個關鍵法規、制度或國際事件標籤（如 碳費子法、PFAS、COP31）。",
            },
        },
        "required": ["summary", "policy_keywords", "ai_tags"],
    }


def _build_prompt(title: str, unit: str, date: str, plain_body: str) -> str:
    topics_list = "、".join(VALID_TOPIC_TITLES)
    excerpt = indexer.truncate_text(plain_body, 2500)
    return (
        "你是台灣環境政策分析師。請閱讀以下中華民國環境部新聞稿，輸出結構化 JSON：\n"
        "1. summary：以繁體中文撰寫 120～200 字政策重點摘要，聚焦法規、目標、對象與時程，嚴禁杜撰數字。\n"
        f"2. policy_keywords：僅可從以下 20 個標準議題名稱中選取（可複選，若無則空陣列）：{topics_list}。\n"
        "3. ai_tags：最多 3 個精簡關鍵法規或事件標籤（每個不超過 12 字）。\n\n"
        f"日期：{date}\n"
        f"發布單位：{unit or '未標示'}\n"
        f"標題：{title}\n"
        f"內文：{excerpt}\n"
    )


def _merge_keywords(rule_keywords: list[str], ai_keywords: list[str]) -> list[str]:
    combined = set(rule_keywords)
    for kw in ai_keywords:
        if isinstance(kw, str) and kw.strip() in VALID_TOPIC_SET:
            combined.add(kw.strip())
    return [title for title in VALID_TOPIC_TITLES if title in combined]


def _normalize_ai_tags(raw_tags: Any) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    seen: set[str] = set()
    cleaned: list[str] = []
    for tag in raw_tags:
        if not isinstance(tag, str):
            continue
        text = tag.strip().lstrip("#")
        if text and text not in seen:
            seen.add(text)
            cleaned.append(text[:24])
        if len(cleaned) >= 3:
            break
    return cleaned


def _call_gemini(
    api_key: str,
    prompt: str,
    model: str = GEMINI_MODEL,
    timeout_seconds: float = 30.0,
    client: Any | None = None,
) -> dict[str, Any]:
    from google import genai
    from google.genai import types

    genai_client = client if client is not None else genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
    )
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_build_response_schema(),
        temperature=0.1,
    )
    response = genai_client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    raw_text = getattr(response, "text", None)
    if not raw_text:
        raise ValueError("Empty response text from Gemini API")
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("Gemini response JSON is not an object")
    return payload


def enrich_news_item(
    title: str,
    content: str,
    unit: str = "",
    date: str = "",
    category: str = "",
    summary_chars: int = 500,
    api_key: str | None = None,
    model: str = GEMINI_MODEL,
    timeout_seconds: float = 30.0,
    client: Any | None = None,
) -> EnrichmentResult:
    """Run Layer 1 rule engine, then optionally enhance with Gemini Free Tier with automatic fallback."""
    base = rule_engine_enrich(
        title=title,
        content=content,
        unit=unit,
        category=category,
        summary_chars=summary_chars,
    )

    resolved_key = (
        api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "")
    ).strip()
    if not resolved_key and client is None:
        return base

    plain_body = indexer.clean_html_to_markdown(content) if content else base.summary
    prompt = _build_prompt(title=title, unit=unit, date=date, plain_body=plain_body)

    try:
        payload = _call_gemini(
            api_key=resolved_key or "mock-key",
            prompt=prompt,
            model=model,
            timeout_seconds=timeout_seconds,
            client=client,
        )
        ai_summary = str(payload.get("summary", "")).strip()
        ai_keywords = payload.get("policy_keywords", [])
        ai_tags = _normalize_ai_tags(payload.get("ai_tags", []))
        merged_keywords = _merge_keywords(base.policy_keywords, ai_keywords if isinstance(ai_keywords, list) else [])

        return EnrichmentResult(
            summary=indexer.truncate_text(ai_summary, summary_chars) if ai_summary else base.summary,
            policy_keywords=merged_keywords,
            ai_tags=ai_tags,
            used_gemini=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Gemini fallback to rule engine: {exc}", file=sys.stderr)
        base.fallback_reason = str(exc)
        return base
