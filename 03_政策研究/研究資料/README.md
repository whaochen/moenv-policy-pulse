# Policy Research V2 資料

本目錄保存額外的 machine-readable 研究 artifact；原 Markdown 是人讀的正式敘事來源。JSON 不替代原稿，也不等於網站已發布。

## 檔名與 ID

- JSON 採 UTF-8：`<research_id>.v2.json`，例如 `net-zero-transition.v2.json`。
- `research_id` 是研究層穩定 slug；`topic.slug` 保留 canonical profile 的 `net_zero_transition`。
- 研究改標題或檔名不自動換 research_id；metadata.source_markdown 隨原稿路徑更新，重新產出並驗證。
- 網站 `report-N` 由網站的 report-registry.json 擁有，不得在此回收或重新編號；淨零既有網站 ID 是 report-3，但本 artifact 不改動該 registry。
- `作者輸入/` 保存人工判讀的 metrics/events/insights 與來源選擇，供 Python 重現。日期或政策數據不是網站 parser 猜測的結果。

## 可重現產出

先維護作者輸入及原 Markdown，再於 vault 根目錄執行：

```powershell
.\.venv-policy-research\Scripts\python.exe scripts/build_policy_research_v2.py --authored "03_政策研究/研究資料/作者輸入/net-zero-transition.json" --output "03_政策研究/研究資料/net-zero-transition.v2.json"
```

編譯器先檢核，無 error 才以暫存檔替換輸出；不修改 canonical inputs。重跑只更新 artifact，沒有抓新聞、網站匯入或部署。人工來源選擇及判讀不會自動產生，必須先完成研究核對。

正式 CLI 額外要求 `meta.input_sha256` 中的四個 canonical inputs 與 source_markdown 指紋相符。`dataset_version` 是四個 canonical 指紋按鍵排序後 JSON 的 SHA-256；原稿指紋另外保存。輸入異動後須重新產出並驗證。合成 fixture 不適用正式指紋 gate。

本次驗收紀錄：`docs/2026-09-13-policy-research-v2-pilot-review.md`。

## 執行環境

本專案使用 `.venv-policy-research/Scripts/python.exe`，依賴見根目錄 `requirements-policy-research.txt`。在 vault 根目錄執行：

```powershell
.\.venv-policy-research\Scripts\python.exe -m unittest tests.test_policy_research_v2 -v
.\.venv-policy-research\Scripts\python.exe scripts/validate_policy_research_v2.py --artifact "03_政策研究/研究資料/net-zero-transition.v2.json"
```

新環境可建立獨立 venv，安裝 `pip install -r requirements-policy-research.txt`。不要把 venv 或本機寄信設定加入網站輸出。

## Canonical Inputs

新聞主表使用 `資料/moenv_news_index.jsonl`；membership 使用 `資料/moenv_news_keywords.csv`；議題及年度定義使用 `資料/moenv_keyword_database.json`；快照時間使用 `資料/moenv_news_manifest.json`。

新聞 CSV、keywords JSONL 與生成 note 暫非 authoritative sources。2026-09-12 查核前兩者各落後一筆；不要為了通過驗證而換用較舊檔案或刪除新聞。validator 應核對所有 ID coverage、profile totals 與 yearly counts。

## 結構契約

Schema：`schemas/policy_research_v2.schema.json`，Draft 2020-12，schema_version 固定 2.0。頂層及穩定巢狀紀錄拒絕額外欄位；這是研究 schema，不是網站新聞 schemaVersion 1。

序列契約允許受控 slug 的 `series_id`、非空 `unit`，`frequency` 為 year／quarter／month，`metric_type` 為 count／percentage／amount／emissions／reduction／capacity／other。期間分別為 YYYY、YYYY-Q1 至 Q4、YYYY-MM，validator 驗證曆法、精度、唯一性與順序。count 為非負整數；其他數值可為小數，unknown 必須為 null。非新聞量序列必須附可解析的 source_ids；其數值仍須研究者查證，不由新聞筆數推導。

`article_count_yearly` 的 year／count／則語意與 canonical 年度數量檢核維持不變。只有這條序列套用新聞快照的 partial／zero 完整性規則及 deterministic signals，依 ID 尋找，不依陣列位置。Pilot 沒有新增第二條實際 series；月／季的額外資料目前只存在合成測試 fixture。其他序列的目標／實績及 partial 意義由研究者依來源判讀，不套用新聞快照年份。自動子議題分類、額外序列擷取與對應網站 UI 均未實作。

來源 ID 使用 `moenv-news:<exact news_id>`；舊 UUID 與數字字串原樣保存。metric/event/insight source_ids 必須非空、唯一且可解析。新聞來源的 title、URL、published_at、publisher 必須與 canonical news 相符。publisher 不等於主管機關。

## 日期與計數

- scope.date_from/date_to 表示統計範圍。Pilot 使用完整所選 profile 快照；縮小範圍卻保留 profile.total 會失敗。
- 原稿 updated 與 coverage_end 分別保存在 meta.research_updated_at、meta.narrative_coverage_end；更新統計不自動重寫原稿歷史數字。
- 已有年份 key 為 observed；截止年度未到 12/31 且有計數時為 partial。
- 缺年不補 0：過去缺年省略並列入 scope.missing_years；截止未完整年度缺計數則輸出 value:null、unknown。
- 零命中不等於已證明全年度收錄完整。雖 schema 辨識 zero 狀態，新聞量序列在沒有 coverage_complete 證據時拒絕 zero；其他序列的 zero 表示有來源支持的數值 0，不代表新聞完整性。
- peak_year 按有觀察值年份的最大新聞量計算，同量取最早年份，並攜帶 period_status。它不等於 trend_signals 的局部峰值。

事件 `date_precision` 可為 day／month／year，`date` 對應 YYYY-MM-DD／YYYY-MM／YYYY。沒有日證據不得補成 01 日。validator 只在檢查 scope 時使用可能日期區間，完全落在 scope 外為 error，跨越邊界則為 EVENT_SCOPE_UNCERTAIN warning，不改寫原日期。來源新聞的 published_at 仍使用完整發布日。

## 趨勢訊號規則

只比較相鄰且完整的 observed 年度；unknown、缺年與 partial 打斷比較。強度保守標為 medium，不宣稱統計顯著性。

| 訊號 | 規則 |
|---|---|
| rapid_growth / rapid_decline | 前期至少5則、絕對變化至少5則、變化比率至少50% |
| sustained_growth / sustained_decline | 三個連續年度，兩次各增加／減少至少5則 |
| peak | 有前後相鄰完整年度的嚴格局部高點；前三年平均至少5則，高於平均至少50%且至少10則 |

暫不產出 structural_shift 或 new_topic_emergence；沒有資料完整性或額外持續性證據，不把首次命中當新政策誕生。訊號保存 baseline、method 與 description，validator 會重算核對。

## 驗證與人工 Gate

CLI exit 0 表示結構及已實作語意檢查無 error，並不保證政策內容的事實正確或因果關係成立。所有 warnings 應隨 artifact 留存／在查核紀錄列出。

`--fixture-mode` 只讀固定的獨立合成測試資料；不是 production gate。不能以 fixture pass 驗收 Pilot。

base schema 與 `validate_artifact(..., publication=False)` 保留摘要 optional，供研究草稿使用。正式 CLI（非 fixture-mode）自動執行 publication-level 檢核，要求 `research_summary` 含 headline、summary、source_ids，並核對引用；合成測試可加 `--publication` 驗證同一條規則。缺摘要為 SUMMARY_REQUIRED error。此為公開資料契約檢查，不是人工驗收或發布動作。編譯器可保存草稿，但不能以編譯成功取代正式 CLI gate。

2026-09-13 A–C 小修保留 schema_version 2.0，pipeline_version 更新為 2.0.1。Pilot 新增摘要後仍保留 needs_review，待使用者確認摘要；沒有自動升級 quality.status 或啟動 Website Integration Plan。

正式新研究雙輸出均須驗證；一般對話分析不強制存檔。既有報告不自動批次轉換。低信心 insight 不可宣告 publication-ready。Pilot 使用 `quality.status: needs_review` 直到使用者完成人工驗收；技術 PASS 與 human acceptance 分開。

在 Pilot 驗收前，不執行 Website Integration Plan、網站匯入或部署。現有新聞索引器與生成 note 的問題另案處理。
