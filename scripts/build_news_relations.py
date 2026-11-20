#!/usr/bin/env python3
"""
Dual-layer hybrid news relation engine (Route 3):
  Layer 1: TF-IDF + jieba with custom MOENV environmental policy dictionary (always runs)
  Layer 2: Neural Embeddings via Gemini Free Tier (gemini-embedding-001) with incremental
           local cache (_local/embeddings_cache.npz) and automatic fallback to 100% TF-IDF.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jieba
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import moenv_news_indexer as indexer  # noqa: E402

TAIPEI_TZ = timezone(timedelta(hours=8))
EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_ALPHA = 0.45
DEFAULT_TOP_K = 5
DEFAULT_MIN_SCORE = 0.16
TOPIC_BONUS = 0.05

EXTRA_DOMAIN_TERMS: tuple[str, ...] = (
    "水污染防治費",
    "水污費",
    "收費辦法",
    "事業及污水下水道系統",
    "自主減量計畫",
    "碳費收費辦法",
    "碳費費率",
    "氣候變遷因應法",
    "資源循環促進法",
    "循環雙法",
    "一次用飲料杯",
    "一次用產品",
    "袋袋箱傳",
    "戴奧辛",
    "排放標準",
    "集塵灰",
    "全氟及多氟烷基物質",
    "飲用水水質標準",
    "空氣品質標準",
    "老舊車輛汰舊換新",
    "溫室氣體盤查",
    "產品碳足跡",
    "環境影響評估",
    "淨零綠生活",
    "公正轉型",
    "厭氧共消化",
    "綠領人才",
    "氣候韌性",
    "河川揚塵",
    "COP28",
    "COP29",
    "COP30",
    "COP31",
    "NDC3.0",
    "PFAS",
    "PFOA",
    "PFOS",
    "PM2.5",
)

STOPWORDS: frozenset[str] = frozenset(
    {
        "環境部",
        "環保署",
        "行政院",
        "表示",
        "今日",
        "推動",
        "辦理",
        "相關",
        "透過",
        "持續",
        "加強",
        "進行",
        "提供",
        "協助",
        "共同",
        "提升",
        "落實",
        "以及",
        "同時",
        "此外",
        "針對",
        "強調",
        "指出",
        "呼籲",
        "新聞",
        "公布",
        "說明",
        "活動",
        "今年",
        "年度",
        "臺灣",
        "台灣",
        "全國",
        "我們",
        "可以",
        "已經",
        "目前",
        "未來",
        "作業",
        "計畫",
        "工作",
        "單位",
        "民眾",
    }
)

RELATIONS_SECTION_RE = re.compile(
    r"\n## 關聯新聞（前世今生）\n.*?(?=\n## |\Z)",
    re.S,
)


def _register_custom_dictionary() -> int:
    """Load all 20 KEYWORD_PROFILES titles, aliases, and domain terms into jieba."""
    jieba.setLogLevel(40)  # suppress verbose jieba startup logs
    terms: set[str] = set(EXTRA_DOMAIN_TERMS)
    for profile in indexer.KEYWORD_PROFILES:
        terms.add(profile.title)
        for alias in profile.aliases:
            if alias.strip():
                terms.add(alias.strip())
    for term in terms:
        jieba.add_word(term, freq=50000)
    return len(terms)


def tokenize_news(item: indexer.NewsItem) -> str:
    """Tokenize title (weighted x2) + summary into space-separated Chinese/English terms."""
    text = f"{item.title} {item.title} {item.summary}"
    tokens: list[str] = []
    for raw in jieba.cut(text, cut_all=False):
        tok = raw.strip().lower()
        if len(tok) < 2:
            continue
        if tok in STOPWORDS:
            continue
        if tok.isdigit() and len(tok) <= 2:
            continue
        if re.fullmatch(r"[\W_]+", tok):
            continue
        tokens.append(tok)
    return " ".join(tokens)


def _load_embedding_cache(cache_path: Path) -> dict[str, np.ndarray]:
    if not cache_path.is_file():
        return {}
    try:
        data = np.load(cache_path, allow_pickle=False)
        ids = data["ids"].tolist()
        vectors = data["vectors"]
        return {str(nid): vectors[idx] for idx, nid in enumerate(ids)}
    except Exception:  # noqa: BLE001
        return {}


def _save_embedding_cache(cache_path: Path, cache: dict[str, np.ndarray]) -> None:
    if not cache:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ids = np.array(list(cache.keys()), dtype=str)
    vectors = np.stack([cache[k] for k in cache], axis=0).astype(np.float32)
    np.savez_compressed(cache_path, ids=ids, vectors=vectors)


def _compute_neural_embeddings(
    items: list[indexer.NewsItem],
    cache_path: Path,
    api_key: str,
    max_new_embeds: int = 100,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    """
    Incrementally compute Gemini embeddings for items missing from cache.
    Automatically falls back to None (100% TF-IDF) if API key is missing or API fails.
    """
    meta: dict[str, Any] = {
        "mode": "tfidf_only",
        "model": EMBEDDING_MODEL,
        "cached_vectors": 0,
        "newly_embedded": 0,
        "fallback_reason": "",
    }
    cache = _load_embedding_cache(cache_path)
    meta["cached_vectors"] = len(cache)

    if not api_key:
        meta["fallback_reason"] = "GEMINI_API_KEY not set"
        return None, meta

    missing_items = [item for item in items if item.news_id not in cache][:max_new_embeds]
    if missing_items:
        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            batch_size = 50
            for start in range(0, len(missing_items), batch_size):
                batch = missing_items[start : start + batch_size]
                contents = [f"{it.title}\n{it.summary[:300]}" for it in batch]
                resp = client.models.embed_content(model=EMBEDDING_MODEL, contents=contents)
                embeddings = getattr(resp, "embeddings", None) or []
                for it, emb in zip(batch, embeddings):
                    vec = np.asarray(emb.values, dtype=np.float32)
                    norm = float(np.linalg.norm(vec))
                    if norm > 0:
                        vec = vec / norm
                    cache[it.news_id] = vec
                    meta["newly_embedded"] += 1
            _save_embedding_cache(cache_path, cache)
            meta["cached_vectors"] = len(cache)
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Neural embedding fallback to TF-IDF: {exc}", file=sys.stderr)
            meta["fallback_reason"] = str(exc)

    # Only blend neural embeddings when full coverage exists
    if len(cache) >= len(items) and all(item.news_id in cache for item in items):
        matrix = np.stack([cache[item.news_id] for item in items], axis=0).astype(np.float32)
        meta["mode"] = "hybrid_tfidf_neural"
        return matrix, meta

    if not meta["fallback_reason"]:
        meta["fallback_reason"] = f"partial_embedding_coverage ({len(cache)}/{len(items)})"
    return None, meta


def _update_note_relations_section(
    vault: Path,
    item: indexer.NewsItem,
    neighbors: list[dict[str, Any]],
    note_path_by_id: dict[str, str],
) -> bool:
    """Append or update '## 關聯新聞（前世今生）' wikilinks in a single Obsidian note."""
    if not item.note_path or not neighbors:
        return False
    full_path = vault / item.note_path
    if not full_path.is_file():
        return False

    section_lines = ["", "## 關聯新聞（前世今生）", ""]
    for rel in neighbors:
        target_id = str(rel["news_id"])
        target_note = note_path_by_id.get(target_id, "")
        direction_zh = "前期脈絡" if rel["direction"] == "earlier" else "後續演進"
        pct = int(round(float(rel["score"]) * 100))
        if target_note:
            link = indexer.obsidian_wiki_link(target_note, rel["title"])
        else:
            link = rel["title"]
        section_lines.append(f"- [{direction_zh}｜{pct}%] {rel['date']} {link}")
    section_block = "\n".join(section_lines) + "\n"

    original = full_path.read_text(encoding="utf-8")
    if "## 關聯新聞（前世今生）" in original:
        updated = RELATIONS_SECTION_RE.sub(section_block.rstrip("\n"), original)
    else:
        updated = original.rstrip() + "\n" + section_block

    if updated != original:
        full_path.write_text(updated, encoding="utf-8", newline="\n")
        return True
    return False


def build_news_relations(
    vault: Path,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
    alpha: float = DEFAULT_ALPHA,
    batch_size: int = 512,
    write_notes_days: int = 14,
    gemini_api_key: str | None = None,
) -> dict[str, Any]:
    """Compute Top-K hybrid news relations for all items and persist outputs."""
    t0 = time.perf_counter()
    items = indexer.load_existing_items(vault)
    items = sorted(items, key=indexer.item_sort_key, reverse=True)
    n = len(items)
    if n == 0:
        return {"total_items": 0, "total_edges": 0, "mode": "empty"}

    dict_size = _register_custom_dictionary()
    docs = [tokenize_news(item) for item in items]

    vectorizer = TfidfVectorizer(
        max_features=35000,
        sublinear_tf=True,
        min_df=2,
        token_pattern=r"(?u)\b\w+\b",
    )
    tfidf_matrix = vectorizer.fit_transform(docs)  # L2-normalized sparse matrix

    resolved_key = (
        gemini_api_key if gemini_api_key is not None else os.environ.get("GEMINI_API_KEY", "")
    ).strip()
    cache_path = vault / "_local" / "embeddings_cache.npz"
    embed_matrix, embed_meta = _compute_neural_embeddings(items, cache_path, resolved_key)
    use_hybrid = embed_matrix is not None
    eff_alpha = alpha if use_hybrid else 1.0

    # Precompute topic sets for lightweight same-topic boost
    matches_by_id = indexer.build_keyword_matches(items)
    topic_sets: list[frozenset[str]] = [
        frozenset(m.profile.slug for m in matches_by_id.get(item.news_id, []))
        for item in items
    ]
    dates = [item.date or "" for item in items]
    ids = [item.news_id for item in items]
    titles = [item.title for item in items]
    units = [item.unit or "未標示" for item in items]
    urls = [item.source_url or "" for item in items]
    url_statuses = [item.source_url_status or "" for item in items]
    note_path_by_id = {item.news_id: item.note_path for item in items if item.note_path}

    # Precompute topic inverted index for fast same-topic bonus lookup
    topic_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, tset in enumerate(topic_sets):
        for slug in tset:
            topic_to_indices[slug].append(idx)

    relations_by_id: dict[str, list[dict[str, Any]]] = {}
    relations_by_year: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    total_edges = 0

    candidate_pool = max(top_k * 6, 30)

    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        sim_block = (tfidf_matrix[start:end] @ tfidf_matrix.T).toarray()
        if use_hybrid and embed_matrix is not None:
            embed_block = embed_matrix[start:end] @ embed_matrix.T
            sim_block = eff_alpha * sim_block + (1.0 - eff_alpha) * embed_block

        for local_i in range(end - start):
            global_i = start + local_i
            row = sim_block[local_i]
            row[global_i] = -1.0  # exclude self

            # Pick top candidate pool quickly using argpartition
            k_pool = min(candidate_pool, n - 1)
            if k_pool <= 0:
                relations_by_id[ids[global_i]] = []
                continue
            cand_indices = np.argpartition(row, -k_pool)[-k_pool:]

            my_topics = topic_sets[global_i]
            scored_cands: list[tuple[float, int]] = []
            for j in cand_indices:
                base_score = float(row[j])
                if base_score <= 0.0:
                    continue
                bonus = TOPIC_BONUS if (my_topics and (my_topics & topic_sets[j])) else 0.0
                final_score = min(0.99, base_score + bonus)
                if final_score >= min_score:
                    scored_cands.append((final_score, int(j)))

            scored_cands.sort(key=lambda pair: (-pair[0], dates[pair[1]]), reverse=False)
            top_neighbors: list[dict[str, Any]] = []
            seen_titles: set[str] = {titles[global_i]}
            for score, j in scored_cands:
                if titles[j] in seen_titles:
                    continue
                seen_titles.add(titles[j])
                direction = "earlier" if (dates[j], ids[j]) < (dates[global_i], ids[global_i]) else "later"
                top_neighbors.append(
                    {
                        "news_id": ids[j],
                        "date": dates[j],
                        "title": titles[j],
                        "unit": units[j],
                        "direction": direction,
                        "score": round(score, 3),
                        "source_url": urls[j],
                        "source_url_status": url_statuses[j],
                    }
                )
                if len(top_neighbors) >= top_k:
                    break

            nid = ids[global_i]
            year = dates[global_i][:4] if len(dates[global_i]) >= 4 else "unknown"
            relations_by_id[nid] = top_neighbors
            relations_by_year[year][nid] = top_neighbors
            total_edges += len(top_neighbors)

    # Save canonical JSONL to 資料/moenv_news_relations.jsonl
    data_dir = vault / "資料"
    data_dir.mkdir(parents=True, exist_ok=True)
    rel_jsonl = data_dir / "moenv_news_relations.jsonl"
    with rel_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(
                json.dumps(
                    {
                        "news_id": item.news_id,
                        "date": item.date,
                        "relations": relations_by_id.get(item.news_id, []),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    # Save metadata summary to 資料/moenv_news_relations_meta.json
    generated_at = datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")
    elapsed = round(time.perf_counter() - t0, 2)
    meta_out = {
        "generated_at": generated_at,
        "algorithm": "Route 3 Hybrid (TF-IDF + jieba domain dict + optional Gemini Neural Embeddings)",
        "mode": embed_meta["mode"],
        "alpha": eff_alpha,
        "top_k": top_k,
        "min_score": min_score,
        "topic_bonus": TOPIC_BONUS,
        "domain_dict_terms": dict_size,
        "vocab_size": int(tfidf_matrix.shape[1]),
        "total_items": n,
        "total_edges": total_edges,
        "elapsed_seconds": elapsed,
        "embedding_meta": embed_meta,
    }
    (data_dir / "moenv_news_relations_meta.json").write_text(
        json.dumps(meta_out, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    # Write back wikilinks ONLY to post-baseline Open Data notes (>= 2026-11-17) so 11,489 historical notes remain untouched
    notes_updated = 0
    if write_notes_days > 0 and dates:
        latest_date = max(d for d in dates if d)
        cutoff = max(
            "2026-11-17",
            (datetime.strptime(latest_date, "%Y-%m-%d") - timedelta(days=write_notes_days)).strftime("%Y-%m-%d"),
        )
        for item in items:
            if item.date and item.date >= cutoff and len(item.news_id) >= 12:
                if _update_note_relations_section(vault, item, relations_by_id.get(item.news_id, []), note_path_by_id):
                    notes_updated += 1

    meta_out["notes_updated"] = notes_updated
    return meta_out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Route 3 hybrid news relations for MOENV archive.")
    parser.add_argument("--vault", type=Path, default=Path.cwd(), help="Path to Obsidian vault root.")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Top-K neighbors per article.")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE, help="Minimum similarity threshold.")
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA, help="TF-IDF blend weight when embeddings exist.")
    parser.add_argument("--write-notes-days", type=int, default=14, help="Only write back wikilinks to notes within recent N days (0 to disable).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_news_relations(
        vault=args.vault.resolve(),
        top_k=args.top_k,
        min_score=args.min_score,
        alpha=args.alpha,
        write_notes_days=args.write_notes_days,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
