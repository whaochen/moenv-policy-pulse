# 本機版精簡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove retired cloud/Codex automation and duplicate vault navigation while generating an evidence-based 30-day policy trend page locally.

**Architecture:** Keep the indexer as the only generator of Obsidian outputs. Add deterministic recent-window statistics to the indexer and route every topic link to one generated policy-topic directory. Daily reporting returns to news-only output; policy research becomes user-invoked.

**Tech Stack:** Python standard library, unittest, Markdown, PowerShell task scheduling, Codex automation records.

**Spec:** `docs/superpowers/specs/2026-09-04-local-simplification-design.md`

## Global Constraints

- Do not recrawl or batch-validate news dated on or before 2020-12-31 unless the user explicitly requests it.
- Modify `scripts/moenv_news_indexer.py`, then rebuild generated output; never hand-edit generated pages.
- Preserve daily Windows update/email behavior and all original news notes, CSV, JSONL and summaries.

---

### Task 1: Remove retired scheduler and cloud configuration

**Files:** Delete `.github/workflows/moenv-news-update.yml`, `.github/workflows/moenv-news-email.yml`, `雲端化操作步驟.md`; modify `AGENTS.md`, `README.md`, `Google Drive雲端化操作步驟.md`; delete Codex automation ids `10` and `22-00`.

- [ ] Verify the two automation records and workflow files.
- [ ] Delete only those two automation records and cloud workflow files.
- [ ] Update surviving documentation to describe local Windows scheduling, Drive synchronization, manual policy research, and the 2021+ health-check default.
- [ ] Search for removed workflow names, health-check schedule and Friday 22:00 schedule.

### Task 2: Add recent-30-day trend output

**Files:** Modify `scripts/moenv_news_indexer.py`, `tests/test_moenv_news_indexer.py`.

**Interface:** `render_recent_policy_trend(items: list[NewsItem], stats: dict[str, KeywordStats], generated_at: str) -> str` writes `02_環境部新聞_可公開/最近30天政策趨勢.md`.

- [ ] Write a fixed-date failing test that asserts `2026-08-05 至 2026-09-03`, a prior-window comparison, and representative news links.
- [ ] Run the focused test and confirm the renderer is absent.
- [ ] Implement date-window helpers, deterministic trend labels, weekly counts, keyword ranking and representative links.
- [ ] Write the page in `write_outputs` and link it from master/public entry pages.
- [ ] Run the focused test to PASS.

### Task 3: Consolidate navigation and manual research

**Files:** Modify `scripts/moenv_news_indexer.py`, `03_政策研究/政策研究關鍵字清單.md`, `03_政策研究/政策研究索引.md`, `tests/test_research_review_queue.py`; delete generated `索引/關鍵字.md`, `索引/關鍵字/`, `99_內部工作區_不公開/`.

- [ ] Write a test that a daily report payload has no `research_review_file`.
- [ ] Remove research-review generation from daily reporting.
- [ ] Generate `01_政策議題/政策議題總覽.md`, and route master navigation to it.
- [ ] Rewrite research notes for manual keyword consolidation and remove duplicate report list.
- [ ] Run the focused test modules to PASS.

### Task 4: Rebuild and verify

**Files:** Delete `_test-output/`, `logs/`, `.codex-drive-write-test`, `.codex-write-probe.md`; regenerate generated indexes.

- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run `./update-index.cmd --rebuild-indexes` without network access.
- [ ] Verify the 30-day page, absence of duplicate topic index, 2021+ rule, and matching note/CSV/JSONL counts.
- [ ] Commit the completed change if this checkout is a usable Git worktree.
