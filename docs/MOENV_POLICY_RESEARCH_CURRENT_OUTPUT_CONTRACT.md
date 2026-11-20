# MOENV Policy Research Current Output Contract

查核日期：2026-09-12。性質：實作與磁碟快照的現況基線，非 V1 定版、非 V2 schema 設計。

本次使用者授權範圍為 Current Output Contract 與 Website Repository Discovery；附件中的 UI、validator、部署與後續工作指令不在本次執行範圍。補充文件位於 `C:/Users/aaron/Downloads/MOENV_POLICY_RESEARCH_V2_DISCOVERY_ADDENDUM.md`；同目錄已找到 `MOENV_POLICY_RESEARCH_V2_SPEC.md`，本次未將其視為實作授權。

## 1. Ownership 與證據

- Vault：`G:/我的雲端硬碟/環境部新聞`。
- 個人 Skill：`C:/Users/aaron/.codex/skills/moenv-policy-research/SKILL.md`，另有 `references/moenv-data-map.md`、`agents/openai.yaml`。Skill 是研究指引，該目錄未有 Python 研究執行器。
- Python 索引器位於 vault 的 `scripts/moenv_news_indexer.py`，不是 Skill 目錄內的子程式。
- 研究 Markdown 由 Codex 依 Skill、官方來源及本地資料撰寫；不是索引器自動產生的研究論文。
- 原始資料程式依據：`NewsItem` 第 272 行、`keyword_matches_for_item` 第 753 行、`build_keyword_stats` 第 929 行、`write_keyword_data_files` 第 1587 行、`write_outputs` 第 1792 行、`append_summary_cache` 第 2138 行。
- 網站另有 Git repository 與輸出契約，詳見同目錄 `MOENV_POLICY_RESEARCH_WEBSITE_REPOSITORY_DISCOVERY.md`。

## 2. 快照核對

| 項目 | 實測結果 |
|---|---|
| manifest.generated_at | 2026-09-12T12:35:00+08:00 |
| manifest.indexed_count / site_total | 11362 / null；null 表示官方總量未知 |
| 新聞 JSONL | 11362 筆，11362 個唯一 news_id |
| JSONL 日期範圍 | 2001-01-01 至 2026-09-12 |
| 新聞 CSV | 11361 筆，最新 2026-09-11，缺少 ID 14099 |
| 新聞關鍵字 CSV | 11362 筆 |
| 新聞關鍵字 JSONL | 11361 筆，最新 2026-09-11，缺少 ID 14099；與關鍵字 CSV 不同步 |
| 關鍵字 profiles / 年度 CSV | 20 組 / 461 列 |
| 關鍵字總數核對 | 20 組 profile.total 均等於關鍵字 CSV 的逐議題命中列數 |
| 人工研究 Markdown | 16 篇；不代表各篇都符合所有模板章節 |
| JSONL 欄位缺失 | 對 13 個 NewsItem 欄位全量核對，均無缺鍵 |
| JSONL 空值 | views 全部 null；summary 19 筆空字串；image_url 1 筆空字串；body 全部空字串 |
| site_topics JSONL 型別 | 全部為陣列；PowerShell Object[]，不是分隔字串 |

上述結果是查核時的磁碟狀態，不是全站完整性認證，也不能由 manifest 推定每個輸出檔已同步。

## 3. JSONL

### 3.1 資料/moenv_news_index.jsonl

Producer：`write_outputs()`，逐列 `json.dumps(asdict(item), ensure_ascii=False)`。UTF-8、每行一個 object、LF。正常 producer 按日期與 ID 倒序輸出。

「必填」在此指 producer 每筆都輸出的鍵；Python dataclass 型別註記不是執行期 schema validator。「可空」區分 null 與空字串。

| 欄位 | JSON 型別 | 必填 | 可 null | 空值／來源與語意 |
|---|---|---|---|---|
| news_id | string | 是 | 否 | 官方 ID，舊資料可為 UUID、新資料可為數字字串，不可轉 integer |
| title | string | 是 | 否 | 新聞標題 |
| roc_date | string | 是 | 否 | 民國日期；不是 ISO date |
| date | string | 是 | 否 | 通常 YYYY-MM-DD；程式容許空字串，現有快照均非空 |
| category | string | 是 | 否 | 原始分類／解析值；不可視為研究主題 |
| unit | string | 是 | 否 | 發布單位，可為「未標示」；不等於法定主管機關 |
| views | integer 或 null | 是 | 是 | 官方瀏覽數不可得時為 null |
| summary | string | 是 | 否 | 可為空字串；通常官方開放資料或內頁摘要，非全文 |
| source_url | string | 是 | 否 | 官方原文；保留舊站與新站 URL |
| image_url | string | 是 | 否 | 可空；不表示已取得素材使用權或下載圖片 |
| site_topics | array<string> | 是 | 否 | 官方網站標記；預設 []，與研究詞庫分開 |
| note_path | string | 是 | 否 | 相對 vault 的本機 note 路徑；預設空字串 |
| body | string | 是 | 否 | 全文模式可填；預設空字串，現有快照全空 |

`site_topics`、`note_path`、`body` 有 dataclass 預設值；其他欄位是建構參數。正常 writer 按 asdict 欄位順序寫出，但 consumer 不應依賴 JSON 鍵順序。

### 3.2 資料/moenv_news_keywords.jsonl

Producer：`write_keyword_data_files()`。所有鍵固定輸出且值均為 string；允許空字串、不輸出 null。

欄位順序：`news_id,date,title,category,unit,keyword_slugs,keywords,matched_aliases,note_path,source_url`。

- 每篇新聞一列，包含未命中議題的新聞；不是一筆新聞乘一筆議題的正規化關聯表。
- `keyword_slugs`：以 `;` 串接 slug。
- `keywords`：以 `;` 串接顯示名稱。
- `matched_aliases`：`slug:alias1,alias2;slug2:alias3`；不是 JSON object。
- 輸出按日期與 ID 倒序；有 CSV 同形版本。
- 同形不等於同快照：本次 JSONL 只有 11361 筆，CSV 有 11362 筆。
- `KeywordMatch.score` 只存在記憶體中，未輸出為本檔欄位。

### 3.3 資料/moenv_detail_summaries.jsonl

Producer：`append_summary_cache()`，append 模式。固定 string 鍵：`news_id,source_url,summary,cached_at`，不輸出 null。`cached_at` 為本機帶時區 ISO datetime，非新聞發布日。這是摘要快取，不是唯一新聞主表，不應假設每篇都有一筆或與現行官方 ID 一一對應。

## 4. JSON

### 4.1 資料/moenv_keyword_database.json

固定頂層鍵：`generated_at:string, source:string, source_url:string, note_root:string, profiles:array<object>`；正常 producer 不輸出 null。

每個 profile 固定鍵：

| 欄位 | 型別 | 說明 |
|---|---|---|
| slug | string | `KEYWORD_PROFILES` 定義的識別字 |
| title / group / description | string | 議題顯示名稱、分群與說明 |
| aliases | array<string> | 同義詞／命中字串 |
| total | integer | 此議題命中的新聞筆數 |
| year_counts | object<string,integer> | 年份字串對應命中筆數，僅加入出現過的年份 |

原始 `KeywordProfile.public:boolean = True` 是程式設定，未輸出到此 JSON。profiles 按 keyword_rank 排序；消費端應以 slug 關聯，不依陣列位置。

### 4.2 資料/moenv_news_manifest.json

固定鍵：`source:string,source_url:string,generated_at:string,mode:string,new_count:integer,indexed_count:integer,site_total:integer|null,note_root:string,keyword_profiles:integer`。

`generated_at` 是本次索引產生時間；`new_count` 是該次操作記錄，並非累計新文章數。没有 `schema_version`、逐檔 checksum、交易 ID 或逐年度完整性狀態。

### 4.3 條件性作業輸出

| 檔案 | Producer／條件 | 固定鍵與型別 |
|---|---|---|
| 資料/daily_update_reports/latest.json | write_daily_report，要求 daily report 時 | generated_at、report_date、subject、body_file 為 string；count 為 integer |
| 資料/daily_update_reports/last_sent.json | send_daily_report.py:140，成功寄送後 | sent_at、to、subject、body_file、report_date 為 string |

latest.json 的 report_date 優先取本次新增新聞中最新日期，無新增時才取 generated_at 前十字元。查核時 latest.json 仍為 2026-09-05，不可当作最新新聞快照時間。寄信標記含收件資訊，屬本機作業資料；本次未讀取其值、未寄信。

## 5. CSV

Python DictWriter，UTF-8 BOM、標頭列；讀取時所有儲存格先是文字，再由 consumer 解析。

| 檔案 | Producer | Columns |
|---|---|---|
| 資料/moenv_news_index.csv | write_outputs | news_id,title,roc_date,date,category,unit,views,summary,source_url,image_url,site_topics,note_path,body |
| 資料/moenv_news_keywords.csv | write_keyword_data_files | news_id,date,title,category,unit,keyword_slugs,keywords,matched_aliases,note_path,source_url |
| 資料/moenv_keyword_years.csv | write_keyword_data_files | keyword_slug,keyword,group,year,count |

- `views=None` 在 CSV 是空儲存格，不能與 integer 0 混用。
- `site_topics` 是 Python list 的字串表示，例如 `['氣候變遷']`，不是合法 JSON 陣列序列化；不要直接 JSON.parse，也不要使用 eval。
- 年度 CSV 的 year 是字串，count 語意上為 integer。
- 目前新聞 CSV 比 JSONL 少一筆。網站實際讀新聞 JSONL，而非此新聞 CSV；這只能解釋網站為何仍有 11362 筆，不能消除 CSV 不同步。

## 6. Markdown

### 6.1 自動生成新聞 note

Producer：`render_note()` 第 997 行。正常目標路徑 `資料/環境部新聞專區/新聞/YYYY/MM/YYYY-MM-DD_ID_標題.md`。

預期 frontmatter：title、source、source_url、news_id、roc_date、date、category、unit、views、image_url、site_topics、tags、policy_keywords。文字以 YAML scalar 輸出；date 可為 null；views 可為 null；標記預期為陣列。

實作偏差：程式先加入 `site_topics:` 再加入 `tags:`，之後才加入 site_topics 的元素。因此有網站標記時，site_topics 實際為 YAML null，網站標記混入 tags。2026-09-01 ID 14026 note 已實際看到此情形；沒有標記的分支還會將最後的 `tags:` 替換為 `site_topics: []`。這不是可依賴的乾淨 frontmatter schema。本次不修復。

正文：H1 標題、日期／分類／單位／官方 URL 清單；條件式 `## 圖譜關聯`、`## 摘要`、`## 內文`。索引點擊連結為 obsidian URI；Graph 使用 wikilink。

### 6.2 自動生成索引與公開閱讀頁

`write_outputs()` 第 1817–1871 行生成：

| 輸出 | Renderer |
|---|---|
| 環境部新聞索引.md | render_master_index |
| 索引/分類.md、發布單位.md、年份.md 與各分頁 | render_group_index、render_group_page |
| 索引/趨勢.md | render_trend_index |
| 00_公開入口/首頁.md | render_public_home |
| 01_政策議題/各議題.md | render_keyword_page(public_variant=True) |
| 01_政策議題/政策議題總覽.md | render_policy_topic_overview |
| 02_環境部新聞_可公開/最近新聞.md | render_public_recent |
| 同目錄 最近30天政策趨勢.md、關鍵字總表.md、年度趨勢.md | render_recent_policy_trend、render_public_keyword_table、render_public_year_trends |

這些頁面為標題、統計表、年度／議題區塊與新聞連結清單；不是網站 API。`render_year_sparkline()` 只產生年份與計數的文字序列。程式另有 `render_research_review_queue()`，搜尋僅找到定義，未找到寫檔呼叫，不能宣稱已自動輸出研究更新佇列。

### 6.3 人工研究報告

路徑 `03_政策研究/研究報告/YYYY-MM-DD_議題.md`；producer 是研究流程／人工編寫，模板為 `03_政策研究/模板/政策研究報告模板.md`。

Skill 要求 frontmatter：type 固定 policy-research；status、topic、issue_type、created、updated、coverage_start、coverage_end 為 scalar；keywords、aliases、tags 為陣列。日期一般 YYYY-MM-DD，未引號時 YAML parser 可能轉為 date object。模板另含 source_project。沒有 validator 強制必填、enum 或 nullable。

模板 section contract：摘要；關鍵字判讀與同義詞；政府正確解釋；本地新聞資料統計；2001 年至今政策趨勢；重點新聞索引；法規與制度清單；主管機關與配合機關；國際趨勢與比較；學術式議題分析；未來研究議題與方向；研究限制與待查證事項；來源。

實際並不完全同形：2026-07-10_淨零轉型.md 使用「政策趨勢」，沒有獨立「重點新聞索引」H2。模板是寫作規範，不是已被強制驗證的解析格式。索引與關鍵字清單也是人工維護，不由新聞更新自動完成研究內容。

## 7. Statistics 與日期語意

- 搜尋文本：title、category、unit、summary、body 合併；不是只比標題，亦不直接加入 site_topics。
- 英數 alias 不分大小寫，中文使用字串出現比對；不是語意分類器。
- 同篇同議題只在 build_keyword_stats 加一筆；同篇可以命中多議題，跨議題 total 加總不是唯一新聞量。
- year_counts 取 `date[:4]`，日期空值則 `unknown`。缺少年份 key 沒有明確 missing/zero 判定。
- 沒有 period_status、coverage_complete 或 partial_year 欄位；2026 是未完整曆年，但目前 artifact 未編碼。
- 沒有證據可把未出現年份直接解讀為完整資料下的零命中。
- 發布日、索引產生時間、快取時間、研究涵蓋截止日、網站匯入與建置時間各有不同語意，不能互換。

## 8. Provenance

| 需求 | 現有來源 | 限制 |
|---|---|---|
| 原始來源 URL | source_url；manifest.source_url | 新聞逐筆 URL 與列表 URL 不同層次 |
| 來源 ID | news_id | 官方 ID 格式曾變動；沒有完整 canonical ID 映射欄位 |
| 新聞發布日期 | date / roc_date | 不是法規生效日 |
| 組織 | unit | 是新聞發布單位，不能推定法定主管、配合機關 |
| 法規名稱與各種日期 | 人工報告內文與表格 | 沒有 law_id、日期類型、法規版本或驗證時間結構 |
| 國際來源與論點 | Markdown 超連結與論述 | 無統一 source record、claim_id、source_ids[] |
| 研究 ID | 網站 report-registry.json | 已有 report-N；不是 vault frontmatter 固定欄位 |
| 資料版本 | 網站 services/dataset.json SHA-256 | 是公開新聞投影版本，不是整份研究證據鏈版本 |

## 9. 已知限制與本次邊界

1. CSV、JSONL 與 note 的快照同步已有實際差異；不能將所有格式視為可互換。
2. 有新聞 note frontmatter 結構偏差，應優先消費新聞 JSONL。
3. 所有 body 目前為空；摘要不足以支持完整文獻或法律條文查證。
4. Skill data map 比實作少列 image_url、site_topics、body；現況應以程式及實檔共同核對。
5. 沒有版本化研究 artifact、研究 validator、型別化法規／機關／claim；但網站已有新聞匯出 JSON Schema，不能泛稱整個系統完全沒有 schema。
6. `write_outputs` 是逐檔寫入，沒有跨檔 atomic snapshot contract。此處未推定本次不同步的原因。
7. 本次未執行抓取、重建、寄信、網站匯入、build 或 deploy；所有差異保留供後續修正決策。
