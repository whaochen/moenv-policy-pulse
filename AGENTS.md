# AGENTS.md

這個資料夾是「環境部新聞專區」的 Obsidian 索引 vault。目標是讓使用者可以用 Obsidian 與 Codex 快速查找環境部新聞。

## 專案結構

- `環境部新聞索引.md`：Obsidian 主入口，含最近新聞、分類、發布單位、年份與政策趨勢入口。
- `00_公開入口/首頁.md`：公開/簡報導向首頁，由索引器產生。
- `01_政策議題/`：政策關鍵字議題頁，由索引器產生。
- `02_環境部新聞_可公開/`：最近新聞、最近30天政策趨勢、年度趨勢與關鍵字總表，由索引器產生。
- `資料/環境部新聞專區/新聞/`：每則新聞一個 Markdown note，依 `西元年/月` 分層。
- `索引/`：分類、發布單位、年份與趨勢索引頁。
- `資料/moenv_news_index.csv`：表格索引資料。
- `資料/moenv_news_index.jsonl`：給 Codex 或其他工具讀取的逐行 JSON。
- `資料/moenv_keyword_database.json`：政策關鍵字資料庫輸出，含同義詞、總量與年度統計。
- `資料/moenv_keyword_years.csv`：關鍵字逐年統計。
- `資料/moenv_news_keywords.csv`：每篇新聞命中的政策關鍵字。
- `資料/moenv_news_manifest.json`：最近一次索引產生時間、筆數與來源。
- `scripts/moenv_news_indexer.py`：抓取環境部新聞列表並產生 Obsidian 檔案的索引器。
- `scripts/send_daily_report.py`：本機 SMTP 寄送每日報告的腳本。
- `Google Drive雲端化操作步驟.md`：Google Drive 備份與桌面同步操作說明。
- `install-windows-tasks.ps1` / `uninstall-windows-tasks.ps1`：本機 Windows 工作排程安裝與移除腳本，用於 09:00/09:30 與登入後補跑。
- `scripts/run_daily_update.ps1`：Windows 工作排程呼叫的更新腳本。
- `scripts/run_daily_email.ps1`：Windows 工作排程呼叫的 SMTP 寄信腳本，讀取 `local-mail.env` 或環境變數。
- `local-mail.env.example`：SMTP/Gmail App Password 設定範本；真正的 `local-mail.env` 不可提交或上傳公開位置。
- `update-index.cmd`：Windows 使用者更新索引的主要入口。
- `update-index.ps1`：`update-index.cmd` 呼叫的 PowerShell 包裝器。
- `README.md`：簡短使用說明。

## 給 Agents 的工作規則

- 自 2026-09-05 起採用手動更新。只有使用者明確要求更新才執行抓取；不要自行建立、恢復或啟用 Windows、Codex、GitHub Actions 更新／寄信／研究排程，也不要恢復登入補跑。Google Drive 同步與備份照常。
- 使用者說「更新環境部新聞」時，在本 vault 執行 `update-index.cmd`，回報新增筆數、最新新聞日期與擷取異常；不要順帶完整重抓、全庫摘要補抓或寄信。`--daily-report` 只產生本地報告，寄信需另外取得明確授權。
- 修改索引產生邏輯時，優先改 `scripts/moenv_news_indexer.py`，不要手動批次改 `資料/環境部新聞專區/新聞/`、`索引/`、`00_公開入口/`、`01_政策議題/`、`02_環境部新聞_可公開/` 或 `資料/` 內的生成檔。
- `資料/環境部新聞專區/新聞/`、`索引/`、`00_公開入口/`、`01_政策議題/`、`02_環境部新聞_可公開/`、`資料/` 是可重建產物；使用者若手動加註心得，應另外放在非生成資料夾，避免下次更新被覆蓋。
- 政策關鍵字詞庫在 `scripts/moenv_news_indexer.py` 的 `KEYWORD_PROFILES`。調整同義詞或新增議題後，執行 `update-index.cmd --rebuild-indexes`，不用重新抓網站。
- 抓取網站需要網路權限。日常使用 `update-index.cmd`，此包裝器預設會加上 `--incremental`，只批次加入新新聞；新增新聞會自動抓內頁第一段作為摘要，最多 500 字。
- 例行維護、完整性核對與缺漏補齊以 `2021` 年以後的新聞為範圍；`2001–2020` 已完成歷史基線，除非使用者明確要求重新核對，否則不要重跑早期新聞。
- 「環境部新聞健康檢查（每10天）」的自動排程已取消。健康檢查改為僅在使用者手動要求時執行與回報，不要自行建立或啟用定期檢查。
- 每日 email 報告使用 `update-index.cmd --daily-report --progress-every 5`。這會執行增量更新並輸出 `資料/daily_update_reports/latest.md` 與 `資料/daily_update_reports/latest.json`。
- 本 vault 目前不使用更新或寄信排程。Windows 排程安裝腳本僅保留供使用者日後明確要求恢復時使用。
- Google Drive 只負責同步與備份，不是 Python 執行環境。
- 使用 Google Drive 連接器大量同步 Obsidian vault 時，不要嘗試逐檔上傳一萬多個 note；先用 zip 備份，或讓使用者安裝 Google Drive for desktop 由桌面同步程式處理大量檔案。
- 使用 Google Drive Desktop + 本機補跑方案時，Windows 工作排程應安裝在 Google Drive 版 vault 路徑，不要繼續指向舊的 `D:\個人\環境部新聞`。
- 目前 Google Drive Desktop 主本路徑是 `G:\我的雲端硬碟\環境部新聞`。2026-09-05 實機查核僅有 `MOENV News Update 0900`，現已停用；未找到寄信排程。Startup 的 `MOENV News Catch-up.lnk` 已移至 `_local_backups/manual-mode-2026-09-05/`，同處保存原排程 XML；備份不可納入網站公開輸出。
- SMTP 密碼只放在本機 `local-mail.env` 或環境變數，絕不提交或同步到公開位置。
- 完整重建請使用 `update-index.cmd --full`。完整重建會抓約數百個列表頁。
- 只重建 note frontmatter、關鍵字資料、公開入口與索引頁，使用 `update-index.cmd --rebuild-indexes`。這只讀本地 `資料/moenv_news_index.jsonl`，不連網。
- 既有新聞要批次補長摘要時，使用 `update-index.cmd --refresh-summaries --summary-chars 500 --max-detail-items 500 --delay 0.15`。這會分批抓新聞內頁，並用 `資料/moenv_detail_summaries.jsonl` 續跑。
- 全文模式 `--include-detail` 會多抓一萬多個新聞內頁，除非使用者明確需要全文離線保存，否則不要預設使用。
- 搜尋本地檔案時優先用 `rg`。
- 新聞日期同時保留民國日期 `roc_date` 與西元日期 `date`。排序以 `date` 為主。
- 發布單位若原站未標示，索引器會寫成 `未標示`，不要當成錯誤。
- 索引頁中的 `.md` 內部連結請使用 `obsidian://open?vault=...&file=...` URI 精準指向檔案。不要使用 `[[新聞/...]]`、`[[索引/...]]` 或 `../../新聞/...md` 這類路徑連結；目前使用者的 Obsidian 會把路徑連結誤判成新空白 note 或觸發 `getParentPrefix` 錯誤。
- Obsidian Graph 需要真正的內部 wikilink 才會畫出關聯邊。新聞 note 內的 `## 圖譜關聯` 區塊要保留 `[[01_政策議題/...]]`、`[[索引/分類/...]]`、`[[索引/年份/...]]` 等 wikilink；不要改成 `obsidian://open`。原則是：索引清單連結用 URI 保持點擊穩定，Graph 關聯用 wikilink 產生邊。
- 正式新聞 note 路徑是 `資料/環境部新聞專區/新聞/`。索引、搜尋與資料輸出都應指向這個路徑，避免引用舊的重複輸出或測試資料。

## 操作步驟

### 1. 在 Obsidian 開啟

1. 開啟 Obsidian。
2. 選擇「Open folder as vault」。
3. 選取這個資料夾：`G:\我的雲端硬碟\環境部新聞`。
4. 打開 `環境部新聞索引.md` 作為首頁。

### 2. 找新聞

在 Obsidian 裡可以用：

- 全域搜尋：搜尋關鍵字，例如 `袋袋箱傳`、`淨零`、`土壤污染`。
- `環境部新聞索引.md`：看最近新聞、分類排行與發布單位排行。
- `00_公開入口/首頁.md`：看公開版入口。
- `01_政策議題/`：依政策議題找新聞與年度趨勢。
- `01_政策議題/政策議題總覽.md`、`02_環境部新聞_可公開/關鍵字總表.md`：依政策關鍵字、同義詞與關聯議題找。
- `索引/趨勢.md`：看年度趨勢與近十年主要議題。
- `索引/分類/`：依新聞分類找。
- `索引/發布單位/`：依發布單位找。
- `索引/年份/`：依年份找。

Codex 或命令列可用：

```powershell
rg -n "袋袋箱傳" .\資料\環境部新聞專區\新聞 .\索引 .\環境部新聞索引.md
```

### 3. 日常更新：批次加入新新聞

在 `G:\我的雲端硬碟\環境部新聞` 執行：

```powershell
.\update-index.cmd
```

這是增量更新。流程是：

1. 讀取 `資料/moenv_news_index.jsonl` 裡既有新聞 ID。
2. 從環境部新聞列表第 1 頁開始抓。
3. 處理完含既有新聞的那一頁後停止。
4. 優先從環境部開放資料取得新新聞第一段作為摘要，最多 500 字；若沒有對應資料才回查新聞內頁。
5. 只有新增新聞或既有新聞的列表欄位確實變更時，才寫入 note 並重建索引頁、CSV、JSONL；完全無異動時不觸碰生成檔案。

更新完成後檢查：

```powershell
Get-Content -Encoding UTF8 .\資料\moenv_news_manifest.json
```

`indexed_count` 應與本地索引筆數一致；目前新站可能回傳 `site_total: null`，這表示來源總數未知，不能據此宣稱全站完整或缺漏。即使兩者相等，也不能取代 ID 與日期範圍核對。

### 4. 手動更新報告

手動更新並產生報告檔案（不寄信）：

```powershell
.\update-index.cmd --daily-report --progress-every 5
```

輸出：

- `資料/daily_update_reports/latest.md`：email 正文。
- `資料/daily_update_reports/latest.json`：email subject、body file 與更新筆數。

報告格式：

```text
YYYY-MM-DD，更新N筆
清單如下
YYYY-MM-DD｜分類｜[新聞標題](<obsidian://open?...>)
```

僅在使用者明確要求寄信時，才讀取 `latest.json` 的 `subject` 與 `body_file`，透過本機寄信設定寄送；不要臨時重組格式，也不要自行恢復 09:30 排程。

### 5. 完整重建

只有使用者明確要求重新抓取全部歷史新聞時，才執行（只改本地詞庫或頁面請用下一節的離線重建）：

```powershell
.\update-index.cmd --full
```

### 6. 重建關鍵字與 Obsidian 索引

只改詞庫、頁面版型或公開入口時，不需要重新抓網站：

```powershell
.\update-index.cmd --rebuild-indexes
```

這會重寫新聞 note 的 `policy_keywords` 與 `moenv/topic/...` tags，並重建 `00_公開入口/`、`01_政策議題/`、`02_環境部新聞_可公開/`、`索引/` 與關鍵字資料檔。

### 7. 批次補長摘要

既有新聞 note 若摘要是截斷版，執行：

```powershell
.\update-index.cmd --refresh-summaries --summary-chars 500 --max-detail-items 500 --delay 0.15
```

這會分批抓新聞內頁，摘要改成第一段最多 500 字。摘要會寫入 `資料/moenv_detail_summaries.jsonl` 快取，重複執行同一指令即可續跑。

### 9. 先測試少量頁面

如果剛改過索引器，先用測試資料夾跑前 2 頁：

```powershell
.\update-index.cmd --full --max-pages 2 --vault .\_test-output
```

確認輸出正常後，再跑完整更新：

```powershell
.\update-index.cmd
```

### 10. 產生全文版

一般不需要。若使用者明確想把每則新聞內文也存進 note，才執行：

```powershell
.\update-index.cmd --include-detail --delay 0.2
```

增量模式下，全文模式只抓新新聞的內頁。若搭配 `--full`，會抓全部新聞內頁，請保留較長 delay，避免對來源網站造成太大壓力。

## 常用驗證

確認 note、CSV、JSONL 筆數：

```powershell
$rows = Import-Csv -Encoding UTF8 .\資料\moenv_news_index.csv
[pscustomobject]@{
  Notes = (rg --files '.\資料\環境部新聞專區\新聞' | Measure-Object).Count
  CsvRows = $rows.Count
  JsonlRows = (Get-Content -Encoding UTF8 .\資料\moenv_news_index.jsonl | Measure-Object).Count
  KeywordRows = (Import-Csv -Encoding UTF8 .\資料\moenv_news_keywords.csv | Measure-Object).Count
  MissingTitle = ($rows | Where-Object { -not $_.title }).Count
  MissingDate = ($rows | Where-Object { -not $_.date }).Count
  MissingCategory = ($rows | Where-Object { -not $_.category }).Count
  MissingUnit = ($rows | Where-Object { -not $_.unit }).Count
}
```

正常情況下，`MissingTitle`、`MissingDate`、`MissingCategory`、`MissingUnit` 都應為 `0`。

## 固定瀏覽器備援（2026-11-01）

使用者要求更新時，優先原增量更新；固定入口現透過 scripts/browser_news_update.py 協調。若退出碼20或顯示 BROWSER_REQUIRED，必須接續閱讀並執行 BROWSER_UPDATE.md，使用正常瀏覽器讀取官方新聞列表與首段摘要，交由 --browser-import 驗證、去重與增量匯入。不能以爬蟲失敗結束並稱沒有新增，也不能只提供重試建議而略過可用瀏覽器。

瀏覽器備援以目前 JSONL 雜湊綁定證據；必須找到第一個既有ID、確認官方總數與新增數相符，只寫新增新聞。未出現CAPTCHA時無需另問確認；出現CAPTCHA或安全警告則依瀏覽器規則請使用者接手。不得複製cookie、停用防護或聲稱單獨執行命令列能自動驗證。失敗或總數不符時不得發布。

成功後沿用原環策晧脈匯入、分析、24則以上動態核定評論保留與Sites發布流程；評論筆數應讀取現存已核定資料，不硬編碼24。_local/browser-update內的證據、請求及備份不得公開。新流程不啟用任何更新或寄信排程。使用者下次提示詞不必改變。