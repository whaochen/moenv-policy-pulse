# MOENV News Project Data Map

Use this reference when working in the local project `G:\我的雲端硬碟\環境部新聞`.

## Primary Structured Files

| File | Use |
|---|---|
| `資料/moenv_news_manifest.json` | Index date, total count, keyword profile count |
| `資料/moenv_keyword_database.json` | Keyword slugs, titles, groups, aliases, descriptions, totals |
| `資料/moenv_keyword_years.csv` | Yearly counts by keyword slug |
| `資料/moenv_news_keywords.csv` | News-keyword matches, category, unit, aliases, note path, source URL |
| `資料/moenv_news_keywords.jsonl` | Same match data in JSONL form |
| `資料/moenv_news_index.csv` | Full news index metadata |
| `資料/moenv_news_index.jsonl` | Full news index metadata in JSONL form |

## Manual Research Outputs

Use `03_政策研究/` for human-authored research outputs that should survive index rebuilds:

- `03_政策研究/政策研究索引.md`: Obsidian entry point for formal policy research notes.
- `03_政策研究/研究報告/`: Main research reports, one Markdown file per topic.
- `03_政策研究/附錄/`: Long evidence tables and appendices.
- `03_政策研究/模板/`: Reusable report templates.

## Important Fields

`moenv_news_keywords.csv`:

- `news_id`
- `date`
- `title`
- `category`
- `unit`
- `keyword_slugs`
- `keywords`
- `matched_aliases`
- `note_path`
- `source_url`

`moenv_news_index.csv/jsonl`:

- `news_id`
- `title`
- `roc_date`
- `date`
- `category`
- `unit`
- `views`
- `summary`
- `source_url`
- `note_path`

## Current Keyword Profiles

The project currently includes 20 policy keyword profiles:

- `water_quality`: 水質保護
- `waste_crime`: 廢棄物與環保犯罪
- `enforcement`: 環境執法與稽查
- `air_quality`: 空氣品質
- `resource_circulation`: 資源循環
- `environmental_education`: 環境教育與綠領人才
- `net_zero_transition`: 淨零轉型
- `climate_adaptation`: 氣候變遷與調適
- `chemical_management`: 化學物質與毒化物
- `soil_groundwater`: 土壤及地下水
- `international_cooperation`: 國際環境合作
- `ghg_inventory`: 溫室氣體盤查登錄
- `eia`: 環評制度
- `bioenergy`: 生質能與再生能源
- `green_consumption`: 綠色消費與標章
- `plastic_reduction`: 減塑與一次用產品
- `carbon_pricing_ets`: 碳定價與ETS
- `carbon_fee`: 碳費徵收
- `esg_finance`: ESG與永續金融
- `voluntary_reduction`: 自主減量計畫

## Caveats

- The manifest may contain mojibake in display strings; trust numeric fields and structured CSV/JSONL values.
- Generated Markdown news notes may contain mojibake. Prefer structured index files and official `source_url` pages for text.
- The `body` field in the index may be empty. Use title, summary, metadata, and official source pages.
- Official law and international sources can change; verify live before presenting current legal status, agency roles, rates, or standards.
- Generated folders should not be manually batch-edited. Publish formal research in `03_政策研究/` instead of modifying generated news indexes.

## Research V2 Canonical Contract

The authoritative pair is `資料/moenv_news_index.jsonl` (news) and
`資料/moenv_news_keywords.csv` (membership). Validate their complete ID sets,
profile totals and yearly counts against `資料/moenv_keyword_database.json`
and `資料/moenv_news_manifest.json` before producing an artifact.

At the 2026-09-12 discovery snapshot the news CSV and keywords JSONL each lagged
by one row; do not use them as authoritative replacements. Generated news YAML
also has a known site_topics/tags issue. The news JSONL additionally contains
`image_url`, `site_topics` (array) and `body` (currently empty).

V2 JSON lives under `03_政策研究/研究資料/<research_id>.v2.json`; its independent
schema is `schemas/policy_research_v2.schema.json` and its read-only CLI is
`scripts/validate_policy_research_v2.py`. The sibling README documents the
contract and reproducible compilation. Sources, metrics, events and insights
use stable IDs; missing years and partial years remain explicit. A news unit
is a publisher, not proof of legal competence.

