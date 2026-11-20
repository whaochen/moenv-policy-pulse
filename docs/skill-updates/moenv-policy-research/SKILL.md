---
name: moenv-policy-research
description: Use when producing or publishing evidence-backed Traditional Chinese policy research reports from a MOENV keyword, especially using the local environment-news vault, official Taiwan regulations, agency roles, international policy trends, or Obsidian research notes.
---

# MOENV Policy Research

## Overview

Use this skill to turn one policy keyword into a research-grade Traditional Chinese report grounded in the local Ministry of Environment news index, Taiwan official legal sources, competent-agency responsibilities, and international policy trends.

The core principle: build a policy evidence chain, not a news summary.

## Required Workflow

1. Identify the keyword, likely slug, aliases, and issue type.
2. Read local keyword/news indexes before drafting trend claims.
3. Verify legal names, dates, and status from official legal sources.
4. Verify competent authorities and cooperating agencies from law text or official organization pages.
5. Add international comparison from official or primary sources appropriate to the issue type.
6. Produce a concise report body first; reserve long raw lists for appendices when the user asks for a file.
7. State evidence limits, especially when local note bodies are empty, garbled, or when legal effective dates need article-level confirmation.

## Local Data

When working in the MOENV news project, read `references/moenv-data-map.md` for local file paths, field names, and caveats.

Prefer structured files over generated note bodies:

- `資料/moenv_keyword_database.json`
- `資料/moenv_keyword_years.csv`
- `資料/moenv_news_keywords.csv`
- `資料/moenv_news_index.csv`
- `資料/moenv_news_index.jsonl`
- `資料/moenv_news_manifest.json`

Use generated Markdown notes only for navigation or Obsidian links. If note text is mojibake, rely on CSV/JSONL fields and the official `source_url`.

## Issue Type

Classify the keyword before analysis because report emphasis changes by type:

| Type | Examples | Report emphasis |
|---|---|---|
| Policy framework | 氣候變遷, 淨零轉型 | governance evolution, cross-ministerial policy, long-term goals |
| Policy instrument | 碳費, ETS, 自主減量, 盤查登錄 | legal basis, fee/rate/market mechanism, compliance workflow |
| Pollution control | 空氣品質, 水質, 土壤, 化學物質 | regulatory standards, enforcement, monitoring, health/environmental impact |
| Resource/circularity | 資源循環, 廢棄物, 減塑 | material flow, recycling systems, reuse markets, illegal disposal |
| Governance system | 環評, 稽查, 國際合作, ESG金融 | institutional design, accountability, interagency coordination |
| Social diffusion | 環境教育, 綠領人才, 綠色消費 | public participation, workforce, behavior change |

## Evidence Layers

### News Layer

Quantify the local index:

- matched count and date range
- yearly counts from 2001 to current index date
- top categories and units
- co-occurring keyword slugs
- representative news with date, title, URL, and short index

Do not infer a policy trend from isolated headlines. Use yearly counts, milestone clustering, and co-occurring topics together.

### Legal Layer

Use official sources first:

- 全國法規資料庫: current laws and article text
- 環境部主管法規查詢系統: MOENV regulations, announcements, administrative rules, historical/deprecated entries
- Competent agency pages such as 氣候變遷署, when they publish official explanations or guidance

Always distinguish these dates:

- 公布日
- 發布日
- 修正日
- 施行日
- 生效日
- 廢止日
- 適用起日

If a regulation says "自發布日施行", use the publication date as the effective date and say so. If an announcement has a separate effective date, keep both dates.

For policy evolution, include current and historical rules when relevant. Mark each item as 現行有效, 已廢止, 停止適用, 草案, or 待查證.

### Agency Layer

Do not stop at "環境部". Identify:

- central competent authority
- responsible MOENV agency or office
- internal division when official pages provide it
- local competent authority
- purpose-business competent authorities
- review committee, fund, platform, or task force when relevant
- cooperating ministries and their statutory role

Tie interagency roles to legal articles or official organization pages whenever possible.

### International Layer

Choose sources based on issue type. Prefer official or primary sources:

- UNFCCC, Paris Agreement, COP decisions for climate governance
- World Bank, OECD, EU, IEA for carbon pricing and market instruments
- EU CBAM pages for border carbon adjustment
- IFRS/ISSB for climate disclosure
- WHO, UNEP, Basel/Stockholm/Minamata conventions for pollution or chemical issues

Compare Taiwan's policy position against international trends, but label inference clearly when the source does not directly discuss Taiwan.

## Report Contract

Default report sections:

1. 關鍵字判讀與同義詞
2. 政府正確解釋
3. 本地新聞資料統計
4. 2001年至今政策趨勢
5. 重點新聞索引
6. 法規與制度清單
7. 主管機關與配合機關
8. 國際趨勢與比較
9. 學術式議題分析
10. 未來研究議題與方向

For Codex conversation output, keep the report readable and cite core sources inline. For Obsidian, Word, or spreadsheet output, put complete law/news tables in appendices or separate sheets.

## Obsidian Publishing

When the user asks to publish, save, or output a formal research note in the MOENV Obsidian vault:

1. Write manual research outputs under `03_政策研究/`, not generated folders.
2. Use `03_政策研究/研究報告/YYYY-MM-DD_<topic>.md` for the main report.
3. Use `03_政策研究/附錄/` for long law/news/source tables.
4. Use or create `03_政策研究/模板/政策研究報告模板.md` when a reusable template is needed.
5. Use or create `03_政策研究/政策研究索引.md` as the research entry point.

Required frontmatter for each report:

- `type: policy-research`
- `status`
- `topic`
- `issue_type`
- `keywords`
- `aliases`
- `created`
- `updated`
- `coverage_start`
- `coverage_end`
- `tags`

Keep the main note self-contained enough for reading in Obsidian: include official source URLs, the local data snapshot date, and the evidence limits. Do not manually edit generated news notes or generated index pages to publish research.

## Analysis Standard

Write like an academic policy researcher who understands consulting practice:

- separate facts, legal interpretation, trend inference, and recommendations
- identify turning points and institutionalization
- discuss policy instruments and implementation capacity
- connect local news trends with law, agency design, and international pressure
- name uncertainties and follow-up data needs

## Quality Checks

Before finalizing, verify:

- the keyword slug and aliases are correct or the ambiguity is stated
- counts, date range, and representative news come from local structured data
- every legal name is exact
- effective dates are not confused with amendment or news dates
- agency roles are not overgeneralized
- international trends use current primary or official sources
- sources are linked

## Common Mistakes

| Mistake | Correction |
|---|---|
| Treating a large topic and a policy tool with the same template | Classify issue type first |
| Writing "環境部主管" only | Identify bureau/division and cooperating agencies |
| Mixing 公布日, 發布日, 生效日, and 施行日 | Keep separate date fields |
| Using news date as legal effective date | Verify from law text or official announcement |
| Listing only current law | Include historical law when explaining policy evolution |
| Using international trend as generic background | Select sources relevant to the issue type |

## Research V2 Dual Output

For newly saved formal research, produce both the human-readable Markdown and
a UTF-8 JSON artifact. Conversation-only analysis does not require files.
Do not mass-convert existing published notes unless explicitly requested.

- Markdown: `03_政策研究/研究報告/YYYY-MM-DD_<topic>.md`.
- Artifact: `03_政策研究/研究資料/<research_id>.v2.json`.
- Contract: `schemas/policy_research_v2.schema.json` in the news vault,
  with `schema_version: "2.0"`. This is independent of the website news schema.
- Read `03_政策研究/研究資料/README.md` for execution, IDs, and pilot limitations.

Python derives yearly counts, period status, deterministic trend signals and
verifies source existence and snapshot consistency. The research author selects
sources and explicitly authors metrics, events, significance, phases and
insights. Do not infer policy facts by parsing Markdown in the website.

Every metric, event and insight must have nonempty stable `source_ids`.
For a MOENV article use `moenv-news:<exact news_id>`; preserve string IDs,
including leading zeros. Map the news unit only to source publisher, never
automatically to a legal competent authority. Keep event/approval dates separate
from news publication and law effective dates.

Use news JSONL and keyword CSV as the canonical pair, plus profiles JSON and
manifest. Reject ID coverage, count or yearly-count inconsistency. Missing years
are unknown, never invented zeros; incomplete cutoff years are partial.
Keep the narrative cutoff distinct from refreshed statistical coverage and
record the input fingerprints. A snapshot change invalidates previous validation.

Before newly setting `status: published`, run from the vault:
`python scripts/validate_policy_research_v2.py --artifact "<artifact-path>"`.
Use the isolated environment and dependencies documented in the artifact README.
Require exit 0, review all warnings, and obtain content acceptance for a pilot.
Never use `--fixture-mode` as a publication gate. Technical PASS does not mean
the author or user has accepted policy claims. Low-confidence insights require
review and must not enter the default production projection.

A saved draft may have `quality.status: needs_review`. Preserve an existing
report's historical statistics unless explicitly updating them; document narrow
evidence corrections. Research IDs belong to the research layer, not the
website's `report-N` registry. Do not modify website files, import, enable
schedules or deploy merely because an artifact validates.

