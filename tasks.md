# 環策皓脈（Taiwan Environment Observatory）全自動化遷移施工規格書 — `TASKS.md`

> **給 Google Antigravity 的執行指令**：請依序完成以下 Phase 0 至 Phase 4 之實作與驗收測試。每個 Phase 完成並通過所有驗收標準後，請進行清楚的原子化 Git Commit；嚴禁破壞既有 11,489 筆歷史新聞紀錄，亦嚴禁將任何 API Key 寫入程式碼或推送至遠端儲存庫。

---

## 專案總覽與架構原則

- **專案名稱**：環策皓脈（建議 GitHub Repo 名稱：`moenv-policy-pulse`）
- **核心目標**：將既有環境部新聞 Obsidian Vault 脫離 Google Drive 雙向同步與手動爬蟲，全面升級為「**環境部 Open Data (`MNEWS_P_01`) ＋ GitHub Actions 每日全自動排程 ＋ Gemini API 免費層（自動降級規則引擎）＋ Obsidian Git ＋ Astro on Cloudflare Pages**」的永久零元自動化架構。
- **核心架構約束（必須嚴格遵守）**：
  1. **永久 $0 零帳單架構**：
     - 資料源：[環境部開放資料 MNEWS_P_01（環保新聞）](https://data.moenv.gov.tw/dataset/detail/MNEWS_P_01)（免費）。
     - 排程引擎：[GitHub Actions](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions) 標準 `ubuntu-latest` Runner（公開 Repo 免費；私有 Repo 每月內含 $12 USD 免費算力，每日執行 1 分鐘遠低於額度）。
     - 網站託管：[Cloudflare Pages Free Plan](https://developers.cloudflare.com/pages/platform/limits/)（每月 500 次建置、單站上限 20,000 檔、單檔上限 25 MiB）。
     - AI 語意引擎：[Google AI Studio Gemini API Free Tier](https://aistudio.google.com/docs/pricing)（免綁信用卡，不具扣款風險），僅針對**每日新增差額新聞**執行，並內建規則引擎自動降級備援。
  2. **全量歷史資料保留與分片策略**：
     - Obsidian Vault（Git Repo）完整保留既有 11,489+ 篇 `.md` 歷史筆記與 `[[01_政策議題/...]]` 雙向連結。
     - Astro 公開網站採**資料驅動靜態架構**：由 Python 將 2001～最新年份的全部新聞依年份切分為約 26 個靜態 JSON 分片（`web/public/data/news/YYYY.json`），避免將上萬篇新聞編譯為上萬個 `.html` 檔而觸發 Cloudflare Pages 的 20,000 檔上限與建置逾時。
  3. **既有舊站零影響**：本專案建立於全新 GitHub Repo 與 Cloudflare Pages，不更動既有 `chatgpt.site` 舊站點。

---

## Phase 0：本機工作庫搬遷、Git 初始化與金鑰安全淨化

### 任務目標
將專案從 Google Drive 雙向同步目錄獨立至本機純 Git 目錄，建立安全隔離規則，並徹底移除舊腳本中的硬編碼金鑰。

### 執行細項
1. **建立純本機 Git 工作目錄**（切勿直接於 Google Drive 同步資料夾內初始化 `.git`）：
   - 將既有 `環境部新聞` 資料夾內容複製至本機獨立目錄（例如 `D:\Projects\moenv-policy-pulse`）。
   - 初始化 Git（預設分支 `main`）。
2. **建立 `.gitignore`（隔離私有工作區與暫存檔）**：
   - 必須排除以下路徑，確保私有備份、虛擬環境與金鑰不外洩至 GitHub：
     - `.env`、`.env.*`
     - `_local/`、`_local_backups/`、`99_內部工作區_不公開/`
     - `.venv*/`、`__pycache__/`、`*.pyc`、`.pytest_cache/`
     - `.obsidian/workspace*.json`（避免每次開啟 Obsidian 造成無意義 Git 衝突）
     - `web/node_modules/`、`web/dist/`、`web/.astro/`
3. **資安修正（最高優先級）**：
   - 檢查 `scripts/moenv_news_indexer.py` 中的 `OPEN_DATA_NEWS_API_URL`，**立即移除寫死的 `api_key` 字串**。
   - 改由環境變數 `os.environ.get("MOENV_API_KEY")` 讀取，並建立 `.env.example` 範本檔：
     ```env
     MOENV_API_KEY=your_moenv_opendata_api_key_here
     GEMINI_API_KEY=optional_gemini_free_tier_api_key_here
     ```
4. **建立《皓哥說》專欄區與範本**：
   - 新增根目錄資料夾 `04_皓哥說/`。
   - 建立一篇範本草稿 `04_皓哥說/_template_draft.md`，YAML Frontmatter 固定規範如下：
     ```yaml
     ---
     title: "（文章標題）"
     date: 2026-11-20
     status: draft          # draft（草稿，網站不顯示）| published（正式上線）
     summary: "（一句話核心觀點摘要）"
     topics:
       - "碳費徵收"
       - "淨零轉型"
     related_news:
       - "14518"            # 填入新聞 news_id 或 newsno，網站自動串連新聞卡片
     ---
     ```

### 驗收標準
- [ ] 全專案搜尋無任何硬編碼的環境部或 Gemini API Key。
- [ ] `.gitignore` 正確忽略 `_local/`、`_local_backups/`、`99_內部工作區_不公開/` 與 `.env`。
- [ ] 執行既有的 `pytest`（`test_moenv_news_indexer.py`）全數通過。

---

## Phase 1：環境部 Open Data (`MNEWS_P_01`) 增量同步 ＋ Gemini Free Tier 雙軌管線

### 任務目標
以官方開放資料 API 取代脆弱的 HTML 爬蟲與手動瀏覽器補抓，實作全自動、零中斷、永久免費的增量同步與統計重算管線。

### 執行細項
1. **建立／重構增量同步主腳本 `scripts/sync_moenv_opendata.py`**（可複用 `scripts/moenv_news_indexer.py` 內的 `KEYWORD_PROFILES`、`item_identity_key` 與 Markdown 產生邏輯）：
   - **資料擷取規格**：
     - 端點：`https://data.moenv.gov.tw/api/v2/mnews_p_01`
     - 參數：`api_key=${MOENV_API_KEY}&format=JSON&limit=1000&offset=0&sort=NewsDate%20desc`
     - 支援自動分頁、指數退避重試（exponential backoff，最多 3 次）與逾時保護（30 秒）。
     - 欄位對應：
       | MNEWS_P_01 欄位 | 系統欄位 | 處理規則 |
       | --- | --- | --- |
       | `newsno` | `news_id` | 保留原字串作為新文章唯一編號 |
       | `newstitle` | `title` | 去除首尾空白與多餘換行 |
       | `newscontent` | `body` / `summary` | 清理 HTML 標籤，取首段（≤ 500 字）作規則引擎預設摘要 |
       | `newssource` | `unit` | 發布司署／單位名稱 |
       | `newsdate` | `date` / `roc_date` | 轉為 `YYYY-MM-DD` 與民國年 `YYY-MM-DD` |
       | `relativeurl` | `source_url` | 若為空或 `"-"`，則回退至 `https://enews.moenv.gov.tw/News/List?key=11&Lang=zh-tw` |
       | `attachurl` | `attach_url` | 若非空且非 `"-"` 則收錄於筆記附註 |
       | `deletemark` | （過濾條件） | 若 `deletemark` 非 `"0"` 且非空字串，略過不收錄 |
   - **歷史資料無縫銜接與去重**：
     - 讀取既有 `資料/moenv_news_index.jsonl`（11,489 筆基準）。
     - 同時比對 `news_id` 與既有的「日期＋正規化標題指紋（`item_identity_key`）」，**只新增差額篇數，絕不覆寫或刪除既有 11,489 筆歷史紀錄**。
2. **實作雙軌零成本分類與摘要模組 `scripts/ai_enricher.py`**：
   - **第一層（必執行，純 Python 規則引擎）**：使用既有 20 大 `KEYWORD_PROFILES` 比對標題與 `newscontent` 內文，產出基準 `policy_keywords` 與首段 `summary`。
   - **第二層（選配增強，Gemini API Free Tier）**：
     - 僅針對**本次新抓取的差額篇數**呼叫（嚴禁回頭批次重跑 11,489 篇歷史資料）。
     - 若 `GEMINI_API_KEY` 未設定，直接跳過並回傳第一層結果。
     - 若有設定，呼叫 `gemini-2.5-flash-lite`（透過 `google-genai` SDK），使用 **Structured Output JSON Schema** 強制輸出：
       - `summary`：120～200 字精簡政策重點摘要（繁體中文）。
       - `policy_keywords`：陣列，值**嚴格限定於既有 20 大政策議題標準名稱**內，與規則引擎取聯集。
       - `ai_tags`：最多 3 個關鍵法規或事件標籤（如 `碳費子法`、`PFAS`、`COP31`）。
     - **強制防呆降級機制**：遭遇 HTTP 429 限流（見 [Gemini API Rate Limits](https://aistudio.google.com/docs/rate-limits)）、逾時或任何 API 例外時，印出 `[WARN] Gemini fallback to rule engine` 並自動採用第一層規則引擎結果，**不得拋出未捕獲例外導致排程失敗**。
3. **純程式化重算 Obsidian 筆記與統計總表（零幻覺）**：
   - 為每篇新增新聞寫入 `資料/環境部新聞專區/新聞/YYYY/MM/YYYY-MM-DD_<news_id>_<safe_title>.md`，完全相容原有 YAML Frontmatter 與 `[[01_政策議題/...]]` 雙向連結格式。
   - 更新 `資料/moenv_news_index.jsonl`、`資料/moenv_news_index.csv`、`資料/moenv_keyword_database.json`、`資料/moenv_news_keywords.csv`、`資料/moenv_keyword_years.csv` 與 `資料/moenv_news_manifest.json`。
   - 自動覆寫 `02_環境部新聞_可公開/` 下的 `年度趨勢.md`、`最近30天政策趨勢.md`、`關鍵字總表.md`、`最近新聞.md`。

### 驗收標準
- [ ] 本機執行 `python scripts/sync_moenv_opendata.py` 成功補齊 2026-11-16 之後的新增環境部新聞（不重複、不覆寫既有 11,489 筆）。
- [ ] 新增單元測試驗證三種模式皆以 Exit Code `0` 完成：(a) 正常呼叫 Gemini API（Mock）、(b) 未設 `GEMINI_API_KEY`、(c) Gemini 回傳 HTTP 429 觸發規則引擎降級。
- [ ] `02_環境部新聞_可公開/` 內所有統計數字與 `moenv_news_index.jsonl` 筆數 100% 吻合。

---

## Phase 2：前端全量分片資料匯出腳本（`scripts/export_web_data.py`）

### 任務目標
將 25 年全量新聞、趨勢統計與政策研究轉換為輕量靜態 JSON 分片，輸出至 `web/public/data/`，確保網站能即時查詢全部 11,489+ 篇新聞且不撞 Cloudflare Pages 檔案上限。

### 執行細項
建立 `scripts/export_web_data.py`，每次同步完成後自動產出以下檔案至 `web/public/data/`：
1. `manifest.json`：總新聞數、涵蓋起訖日、最後更新時間（UTC+8）、20 大議題數。
2. `trends.json`：
   - `yearly_totals`：2001～最新年份每年新聞總量。
   - `topic_yearly_matrix`：20 大政策議題 × 各年度新聞筆數矩陣。
   - `last_30_days`：最近 30 天 vs 前 30 天總量、各議題動能變化（增減筆數與百分比）、每週新聞量。
   - `unit_ranking`：環境部各司署（`unit`）近一年與歷年發布量排行。
3. `topics.json`：20 大政策議題的 `slug`、`title`、`group`、`description`、`aliases`、歷年總筆數、近 30 天筆數與最新 10 篇代表新聞。
4. `news/YYYY.json`（按年份切分，約 26 個檔案）：
   - 每筆包含：`news_id`、`date`、`roc_date`、`title`、`unit`、`summary`、`policy_keywords`、`ai_tags`、`source_url`、`attach_url`。
5. `search_index.json`（精簡檢索索引）：
   - 僅保留 `id`、`d`（日期）、`t`（標題）、`u`（單位）、`k`（議題 slug 陣列），控制在 3 MiB 以內，供前端毫秒級篩選全站 11,489+ 篇新聞，點擊時再按年份動態載入對應 `news/YYYY.json` 顯示完整摘要與連結。
6. `research.json`：掃描 `03_政策研究/研究資料/*.v2.json` 與 `03_政策研究/研究報告/*.md`，輸出可供前端呈現的研究清單與統計序列。

### 驗收標準
- [ ] `web/public/data/` 下檔案總數 < 50 個，單一檔案大小均遠低於 25 MiB（`search_index.json` 建議 < 3 MiB）。
- [ ] `news/YYYY.json` 各年度筆數加總等於 `manifest.json` 的總新聞數。

---

## Phase 3：Astro 公開網站「環策皓脈」前端建置（`web/`）

### 任務目標
打造專業政策智庫風格的「環策皓脈」互動網站，原生整合 `04_皓哥說` 專欄與全量 25 年環境部新聞檢索、趨勢圖表。

### 技術棧與視覺規範
- **框架**：Astro 5.x（`output: 'static'`）＋ Tailwind CSS ＋ Apache ECharts（或 Chart.js）。
- **視覺風格**：政策觀測站／智庫編輯風（深翠綠 `#0F4C3A` 主色 ＋ 暖象牙白 `#F8F9F7` 背景 ＋ 琥珀重點色 `#D97706`，高對比易讀排版、完整 RWD 支援手機與桌機）。

### 必備頁面與功能
1. **首頁儀表板（`/`）**：
   - 頂部 KPI 統計條：累計收錄新聞數（11,489+）、收錄跨度（2001～至今）、近 30 天新聞量（含較前 30 天增減幅）、最後自動同步時間。
   - **《皓哥說》最新專欄區**：自動顯示最新 3 篇 `status: published` 文章卡片（若尚無已發布文章，優雅顯示「專欄籌備中」不破版）。
   - **近 30 天政策議題動能圖**：水平長條圖呈現升溫最快的前 10 大政策議題。
   - **最新環境部新聞快訊**：顯示最新 10 篇新聞卡片（含日期、單位、政策標籤與摘要預覽）。
2. **趨勢分析室（`/trends`）**：
   - 互動式 **2001～2026 歷年政策聲量折線／面積圖**：支援複選任意多個政策議題疊加對比、切換年份區間（全部 / 近 5 年 / 近 10 年）。
   - **近 30 天 vs 前 30 天動能對比表**與**發布單位（司署）聲量排行圖**。
3. **政策議題總覽與專頁（`/topics`、`/topics/[slug]`）**：
   - 依群組（氣候與碳定價、資源循環與廢棄物、污染防制、治理與制度、社會溝通與人才）展示 20 大議題卡片。
   - 單一議題專頁內含：該議題 2001～2026 專屬走勢圖、同義詞說明、該議題完整歷史新聞分頁清單、以及對應的《皓哥說》與 `03_政策研究` 報告連結。
4. **全量新聞檢索室（`/news`）**：
   - 載入 `search_index.json`，支援即時搜尋 **2001～2026 全部 11,489+ 篇**新聞（關鍵字、年份下拉、政策議題、發布單位多維度交叉篩選，分頁顯示）。
   - 點擊任一新聞即展開側邊閱讀抽屜（Drawer）或彈窗，按年份即時載入 `news/YYYY.json` 呈現完整摘要、政策標籤、附件與環境部官方連結。
5. **《皓哥說》專欄（`/hao-talks`、`/hao-talks/[slug]`）**：
   - 透過 Astro Content Collections（或自訂 loader）直接讀取根目錄 `../04_皓哥說/*.md`。
   - **嚴格發布閘門**：只編譯與公開 `status === "published"` 的文章；`status: draft` 與 `_template_draft.md` 絕對不得生成任何公開頁面或出現在站內清單。
   - 文章頁底部自動解析 `related_news` 的 ID，渲染對應的環境部原新聞卡片與連結。
6. **政策研究專區（`/research`）**：
   - 呈現 `03_政策研究` 既有的深度分析報告與 `.v2.json` 統計圖表。

### 驗收標準
- [ ] 執行 `cd web && npm run build` 零錯誤完成，建置時間 < 60 秒。
- [ ] 檢查 `web/dist/` 總檔案數 **< 500 個**（遠低於 Cloudflare Pages 20,000 檔上限）。
- [ ] 建立一篇 `status: draft` 與一篇 `status: published` 測試文章，確認 `dist/` 中僅出現 `published` 文章，完全不含 `draft` 內容。
- [ ] 本機預覽所有 6 個路由皆無 Console 紅字錯誤，圖表與全量搜尋正常運作。

---

## Phase 4：GitHub Actions 全自動排程、Cloudflare Pages 部署與 Obsidian Git 串接

### 任務目標
完成「睡覺時也自動更新上線」的 CI/CD 閉環，並建立零摩擦的 Obsidian 寫作同步流程。

### 執行細項
1. **建立 `.github/workflows/daily-sync.yml`**：
   - 觸發條件：
     - `schedule`: `cron: '0 0 * * *'`（每日 UTC 00:00 ＝ 台灣時間每日 08:00）。
     - `workflow_dispatch`: 允許於 GitHub 網頁一鍵手動觸發。
   - 執行步驟：
     1. `actions/checkout@v4`（`fetch-depth: 1`）
     2. `actions/setup-python@v5`（Python 3.12）並安裝 `requirements.txt`（精簡依賴，如 `google-genai`、`pyyaml`）
     3. 執行 `python scripts/sync_moenv_opendata.py`（傳入 Secrets：`MOENV_API_KEY`、選配 `GEMINI_API_KEY`）
     4. 執行 `python scripts/export_web_data.py`
     5. 執行快速資料完整性檢查腳本（確認 `manifest.json` 有效且非空）
     6. 檢查 `git status --porcelain`：若有資料變動，以 `github-actions[bot]` 自動 `git add`、`git commit -m "chore(data): auto-sync MOENV news YYYY-MM-DD"` 並 `git push origin main`。
2. **撰寫 `DEPLOYMENT_GUIDE.md`（給使用者的 5 分鐘上線清單）**：
   - GitHub Repo Secrets 設定步驟：`MOENV_API_KEY`（必填，建議至環境部開放資料平台重新換發一組新 Key）與 `GEMINI_API_KEY`（選填，Google AI Studio 免費層 Key，免綁信用卡）。
   - Cloudflare Pages 綁定步驟：
     - Framework preset：`Astro`
     - Root directory：`web`
     - Build command：`npm run build`
     - Build output directory：`dist`
     - Node version：`20`（透過環境變數 `NODE_VERSION=20`）
   - Obsidian Git 外掛設定步驟（本機開啟純 Git 目錄作為 Vault，設定開啟自動 Pull，寫完《皓哥說》改為 `status: published` 後按一鍵 Commit & Push，約 1～2 分鐘即自動上線）。

### 驗收標準
- [ ] `.github/workflows/daily-sync.yml` 語法通過驗證（無硬編碼密鑰、具備 `permissions: contents: write`）。
- [ ] `requirements.txt` 完整且可於乾淨 Python 3.12 環境成功安裝執行。
- [ ] 推送至 GitHub 後，手動觸發一次 `workflow_dispatch` 綠燈通過，且 Cloudflare Pages 自動建置並成功上線「環策皓脈」新版網站。
