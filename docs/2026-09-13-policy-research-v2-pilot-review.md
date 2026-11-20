# Policy Research V2 Pilot 驗收紀錄

驗證日期：2026-09-13。範圍僅研究資料層；未執行 Website Integration Plan、未修改網站 repository、未部署或啟用排程。

## Task 1-6 執行結果

- [x] Task 1：Draft 2020-12 schema、嚴格欄位及正反 fixture。
- [x] Task 2：canonical loaders、字串 ID、年度 partial 與缺年規則。
- [x] Task 3：來源、引用、統計、範圍、品質語意 validator 及 CLI。
- [x] Task 4：可解釋年度訊號，拒絕低基期膨脹及跨缺年／partial 比較。
- [x] Task 5：個人 Skill 與資料契約雙輸出規則、研究資料 README。
- [x] Task 6：淨零轉型作者輸入、可重現編譯器、通過正式 validator 的 artifact。
- [ ] 使用者確認 Pilot JSON 與原稿的對應、有限抽取範圍及警告可接受。
- [ ] Website Integration Plan：未開始，須另經授權。

計畫要求的逐項 Git commit 未執行：目前 vault 的 Git 狀態查詢不是有效 repository；未初始化 repository，也未偽造提交。Skill 位於 vault 外，另行套用及驗證。

## 新增與修改檔案

以下相對路徑基準為 `G:/我的雲端硬碟/環境部新聞`。

| 動作 | 檔案 |
|---|---|
| 新增 | `schemas/policy_research_v2.schema.json` |
| 新增 | `scripts/policy_research_v2.py` |
| 新增 | `scripts/validate_policy_research_v2.py` |
| 新增 | `scripts/build_policy_research_v2.py` |
| 新增 | `tests/test_policy_research_v2.py` |
| 新增 | `tests/fixtures/policy_research_v2.valid.json` |
| 新增 | `tests/fixtures/policy_research_v2.invalid_missing_source.json` |
| 新增 | `tests/fixtures/policy_research_v2.canonical.json` |
| 新增 | `requirements-policy-research.txt` |
| 新增 | `03_政策研究/研究資料/README.md` |
| 新增 | `03_政策研究/研究資料/作者輸入/net-zero-transition.json` |
| 新增 | `03_政策研究/研究資料/net-zero-transition.v2.json` |
| 新增 | `docs/skill-updates/moenv-policy-research/SKILL.md`（套用留存副本） |
| 新增 | `docs/skill-updates/moenv-policy-research/references/moenv-data-map.md`（套用留存副本） |
| 新增 | 本驗收紀錄 |
| 修改 | `03_政策研究/研究報告/2026-07-10_淨零轉型.md`：僅更新校訂日期、校訂說明及 NDC3.0 核定日 |
| 修改（vault 外） | `C:/Users/aaron/.codex/skills/moenv-policy-research/SKILL.md` |
| 修改（vault 外） | `C:/Users/aaron/.codex/skills/moenv-policy-research/references/moenv-data-map.md` |

另建立本機專用 `.venv-policy-research`，安裝 jsonschema 4.26.0、PyYAML 6.0.3；不是網站可公開產物。

## 測試證據

Task 1-4 分別先確認新增測試失敗，再實作轉綠。Task 6 的 7 個 compiler 測試先因 compiler 不存在失敗，實作後累計 44 項通過；新增 builder CLI 測試先因入口不存在失敗，實作後累計 45 項通過。

```text
python -m unittest tests.test_policy_research_v2 -q
Ran 45 tests
OK

python -m unittest discover -s tests -v
Ran 54 tests
OK
```

實際使用 `.venv-policy-research/Scripts/python.exe`。全專案測試中的抓取輸出是既有 mock 測試，並未執行新聞更新。Skill 的 quick_validate.py 以 UTF-8 執行，結果 `Skill is valid!`。

## V2 Schema 與 Pilot

`schema_version: "2.0"`，Draft 2020-12。必填：schema_version、research_id、topic、scope、statistics、trend_series、key_metrics、key_events、trend_insights、sources、quality、meta。穩定紀錄拒絕未知欄位；source_ids 非空且可解析。此 Pilot 只實作年度新聞量序列，非完整 V2 UI 契約或全議題研究更新。

| 項目 | 結果 |
|---|---|
| research_id | `net-zero-transition` |
| artifact | `G:/我的雲端硬碟/環境部新聞/03_政策研究/研究資料/net-zero-transition.v2.json` |
| canonical 快照 | 2026-09-12T12:35:00+08:00 |
| 統計範圍 | 2001-01-01 至 2026-09-12 |
| 實際命中最早／最新日期 | 2007-11-11／2026-09-12 |
| article_count | 899 |
| 年度資料點／趨勢訊號 | 20／10 |
| metric／event／insight／source | 3／3／1／3 |
| 年度最高觀察值 | 2025 年 133 則，observed |
| 原稿敘事截止 | 2026-07-08，原稿歷史統計 876 則未改寫 |
| quality.status | `needs_review`，技術 PASS 不等於人工驗收 |

政策數據為 2030 年 28±2%、2035 年 38±2% 目標與 20 項減碳旗艦行動計畫；均非成果指標。事件區分 2023-08-22 揭牌、2025-11-03 核定 NDC3.0、2026-02-26 核定部門方案。來源新聞發布日分別為 2023-08-22、2025-11-06、2026-03-12。

來源逐筆核對使用官方新聞：[3234](https://enews.moenv.gov.tw/moenv-news/zh-tw/News/3234)、[2078](https://enews.moenv.gov.tw/moenv-news/zh-tw/News/2078)、[1868](https://enews.moenv.gov.tw/moenv-news/zh-tw/News/1868)，查核日期 2026-09-12。來源 title、URL、發布日、發布單位由 canonical 主表帶入；來源所支持的政策日由研究者判讀，不從新聞發布日推定。

## 正式 Validator 輸出

執行：`.venv-policy-research/Scripts/python.exe scripts/validate_policy_research_v2.py --artifact "03_政策研究/研究資料/net-zero-transition.v2.json"`。未使用 fixture-mode，exit code 0。

```text
WARNING AUTHOR_WARNING quality.warnings: 2001-2006 缺少本議題年度統計鍵，視為 unknown，不補零；不能據此推定當時沒有相關政策。
WARNING AUTHOR_WARNING quality.warnings: 2026 為截至資料快照日期的 partial 年度，不與完整年度直接判斷全年增減。
WARNING AUTHOR_WARNING quality.warnings: 原 Markdown 保留 2026-07-08 研究範圍及 876 則歷史快照；V2 採 2026-09-12 canonical 快照。差額亦含歷史資料修訂，不代表單純新增新聞數。
WARNING AUTHOR_WARNING quality.warnings: 本 Pilot 僅結構化原稿部分高信心證據，並非完整抽取法規、機關、國際比較與所有研究論點。
WARNING AUTHOR_WARNING quality.warnings: 本議題詞庫包含低碳與減碳；新聞量是詞庫命中的溝通頻率，不是減碳績效或狹義淨零政策數量。
WARNING HUMAN_REVIEW_REQUIRED quality.status: Technical validation does not constitute human acceptance
WARNING OFFICIAL_TOTAL_UNKNOWN manifest.site_total: Cannot establish full-site completeness
WARNING NARRATIVE_SNAPSHOT_DIFFERS meta.narrative_coverage_end: Narrative and statistics have different cutoffs
WARNING LEGACY_SNAPSHOT_MISMATCH G:\我的雲端硬碟\環境部新聞\資料\moenv_news_index.csv: Non-authoritative snapshot: rows=11361, missing=['14099'], extra=[], duplicates=0
WARNING LEGACY_SNAPSHOT_MISMATCH G:\我的雲端硬碟\環境部新聞\資料\moenv_news_keywords.jsonl: Non-authoritative snapshot: rows=11361, missing=['14099'], extra=[], duplicates=0
PASS: 0 errors, 10 warnings
```

新聞主表與 canonical membership 均為 11,362 筆；較舊 CSV 與 keywords JSONL 只報警告，不用來改寫 canonical 統計。`site_total: null` 不能據此宣稱全站完整。

## 未變動資料的 SHA-256

完成後與實作前基線一致：

```text
scripts/moenv_news_indexer.py
69869F0D7B937B13D085FF94084FE92CAD78C771E7FBEF2E0B1E86C02A98EE48
資料/moenv_news_index.jsonl
DCBA114BEF86B6485B58CFFE3A3F859C14D958B4675ED8C2FB744B3F2C92662D
資料/moenv_news_keywords.csv
A5B97DEC7B5CF158FD789FF352F81703D3810DEE5B491DAF693296F281E53163
資料/moenv_keyword_database.json
C3D979A8B5285D62FC16605F29313456CC969C494962F6F386CE0A366A8CE480
資料/moenv_news_manifest.json
6B6CC169A6AF1FE0638066EB5A17E5F5E2E16F203D2AE6C6B6B9BA07F1FFFE18
```

artifact 另保存 canonical 與原 Markdown 的指紋；日後任何輸入更新都須重新編譯驗證。原 Markdown 仍屬歷史已發布敘事，不因本次 Pilot 技術驗證而自動成為全面更新或重新發布的研究。
