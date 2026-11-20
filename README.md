# 環境部新聞 Obsidian 索引

這個資料夾可以直接當成 Obsidian vault。索引器會從環境部新聞專區抓取新聞列表，為每則新聞建立 Markdown note，並另外輸出 CSV / JSONL，方便用 Obsidian 全域搜尋或 Codex 搜尋。

目前採用手動更新（2026-09-05 起）。每日更新排程已停用，登入補跑捷徑已移至 `_local_backups/manual-mode-2026-09-05/`。Google Drive 繼續負責同步與備份。

專案優化評估與分階段方案：`docs/2026-09-05-專案優化評估.md`。近期摘要修復與完全無異動時跳過重建已完成；歷史封存狀態、進階趨勢與網站仍是待實作設計。

## 日常更新：批次加入新新聞

在 `G:\我的雲端硬碟\環境部新聞` 開啟 PowerShell，只要跑：

```powershell
.\update-index.cmd
```

這會用增量模式：

1. 讀取 `資料/moenv_news_index.jsonl` 裡既有新聞 ID。
2. 從環境部新聞列表第 1 頁開始抓。
3. 處理完含既有新聞的那一頁後停止，不繼續巡查全部歷史列表。
4. 優先從環境部開放資料取得新新聞第一段作為摘要，最多 500 字；若沒有對應資料才回查新聞內頁。
5. 只有新增新聞或既有新聞的列表欄位確實變更時，才寫入 note 並重建索引頁、CSV、JSONL；完全無異動時不觸碰生成檔案。

如果今天沒有新新聞，通常只會抓第 1 頁，然後顯示 `No new items found.`。

也可以在本專案對 Codex 說：「請手動增量更新環境部新聞，回報新增筆數、最新新聞日期與擷取異常，不做完整重抓，不寄信。」這不需要額外 Skill。

歷史基線 `2001–2020` 不再主動上網核對。不要把 `--full` 當成日常更新方式。

## 手動更新報告

如需同時產生本次更新清單，可執行以下指令。`--daily-report` 是既有參數名稱，只產生報告檔案，不會自行寄信：

```powershell
.\update-index.cmd --daily-report --progress-every 5
```

報告會寫到：

- `資料/daily_update_reports/latest.md`
- `資料/daily_update_reports/latest.json`

email 正文格式如下：

```text
2026-07-04，更新2筆
清單如下
2026-07-04｜氣候變遷｜[新聞標題](<obsidian://open?...>)
```

## Google Drive 模式

若要走 Google Drive，請看 `Google Drive雲端化操作步驟.md`。

Google Drive 做雲端儲存與同步，新聞更新由你手動啟動。保留的 `install-windows-tasks.ps1` 是未來明確決定恢復排程時才使用的工具，日常操作不需要執行。

目前 Google Drive Desktop 主本路徑為：

```text
G:\我的雲端硬碟\環境部新聞
```

請在這份 Drive 版 vault 操作；舊的 D 槽資料夾不是目前工作本。

## 完整重建

```powershell
.\update-index.cmd --full
```

完整重建會重新抓取全部列表頁，只有明確需要重新抓取全部歷史新聞時才使用。網站結構調整應先做少量測試；只改詞庫或頁面應使用離線 `--rebuild-indexes`。

產物：

- `環境部新聞索引.md`：Obsidian 首頁索引。
- `00_公開入口/首頁.md`：適合公開或簡報使用的總入口。
- `01_政策議題/`：依政策關鍵字自動產生的議題頁。
- `02_環境部新聞_可公開/`：最近新聞、年度趨勢、關鍵字總表。
- `資料/環境部新聞專區/新聞/`：每則新聞一個 Markdown note。
- `索引/`：依分類、發布單位、年份、關鍵字與趨勢整理的索引頁。
- `資料/moenv_news_index.csv`：可用 Excel 或試算表開啟。
- `資料/moenv_news_index.jsonl`：給 Codex 或其他工具做進一步分析。
- `資料/moenv_keyword_database.json`：政策關鍵字資料庫、同義詞與年度統計。
- `資料/moenv_keyword_years.csv`：關鍵字逐年統計。
- `資料/moenv_news_keywords.csv`：每篇新聞命中的政策關鍵字。

## 關鍵字資料庫與政策趨勢

索引器內建第一版政策關鍵字詞庫，例如 `碳費徵收`、`自主減量計畫`、`碳定價與ETS`、`溫室氣體盤查登錄`、`淨零轉型`、`資源循環`、`減塑與一次用產品`、`空氣品質`、`環評制度` 等。每篇新聞會依標題、分類、發布單位與摘要比對同義詞，寫入：

- note frontmatter 的 `policy_keywords`
- note tags 的 `moenv/topic/...`
- note 內文的 `圖譜關聯` wikilink，供 Obsidian Graph 建立關聯邊
- `資料/moenv_keyword_database.json`
- `01_政策議題/`
- `索引/趨勢.md`

如果只是修改詞庫或索引版型，不需要重新抓網站，執行：

```powershell
.\update-index.cmd --rebuild-indexes
```

這會從既有 `資料/moenv_news_index.jsonl` 重建 note、關鍵字資料與 Obsidian 索引。

## Obsidian Graph 關聯

索引頁的新聞標題連結使用 `obsidian://open`，這能避免 Obsidian 誤開空白 note，但 Graph 不會把它視為內部連結。

為了讓 Graph 有可互動的關聯，每篇新聞 note 會另外產生 `## 圖譜關聯`，內容使用 Obsidian wikilink，例如：

```markdown
[[01_政策議題/碳費徵收|碳費徵收]]
[[索引/分類/氣候變遷|氣候變遷]]
[[索引/年份/2026|2026]]
```

因此若 Graph 畫面仍像一團沒有線的點，請在 Obsidian 等待重新索引，或重新開啟 vault；關聯邊來自這些 `[[...]]` wikilink。

## 測試少量頁面

如果剛改過索引器，建議用另一個測試輸出資料夾跑前 2 頁：

```powershell
.\update-index.cmd --full --max-pages 2 --vault .\_test-output
```

確認沒問題後再刪除 `_test-output`，並對正式 vault 跑：

```powershell
.\update-index.cmd
```

## 全文模式

預設只抓列表資料：標題、日期、分類、摘要、發布單位、原始連結。若要把每篇新聞內文也寫入 note，可加上：

```powershell
.\update-index.cmd --include-detail --delay 0.2
```

在增量模式下，全文模式只會抓新新聞的內頁。若搭配 `--full`，才會抓全部一萬多個新聞內頁，建議保留較長 delay。

## 批次補長摘要

如果既有新聞 note 的摘要仍是列表頁截斷版，可以批次改成新聞內頁第一段，最多 500 字：

```powershell
.\update-index.cmd --refresh-summaries --summary-chars 500 --max-detail-items 500 --delay 0.15
```

這會分批抓新聞內頁，並把結果寫進 `資料/moenv_detail_summaries.jsonl` 快取。重複執行同一個指令會從尚未完成的新聞繼續補，不會重抓已快取的摘要。之後日常增量更新的新新聞會自動使用同樣的第一段摘要。

## 建議的 Obsidian 使用方式

- 從 `00_公開入口/首頁.md` 看公開版入口。
- 從 `01_政策議題/碳費徵收.md` 這類頁面看單一政策脈絡。
- 從 `索引/趨勢.md` 看 2001 年以來的年度議題變化。
- 從 `01_政策議題/政策議題總覽.md` 進入議題，從 `02_環境部新聞_可公開/關鍵字總表.md` 看詞庫。
- 原始新聞 note 以 `資料/環境部新聞專區/新聞/` 為正式來源；不要再使用根目錄 `新聞/`。


## 固定瀏覽器備援

日常入口不變。爬蟲遇到官方驗證頁或列表存取異常時，以退出碼20與 BROWSER_REQUIRED 明確交由 Codex 接續瀏覽器補入。請依 [瀏覽器備援操作說明](BROWSER_UPDATE.md) 執行；只新增、保留舊資料，不啟用排程。單獨腳本不會自動操控瀏覽器或通過驗證。
