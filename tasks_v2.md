# 環策皓脈（Taiwan Environment Observatory）V2 品牌與學術級升級規格書 — `TASKS_V2.md`

> **給 Google Antigravity 的執行指令**：本規格書為「環策皓脈」V2 重大升級藍圖，建立於既有可運行的 Astro + GitHub Actions + Cloudflare Pages 架構之上。請依序完成 **Phase A 至 Phase E** 之實作與驗收測試，每個 Phase 通過後再執行原子化 Git Commit。嚴禁破壞既有 11,489+ 筆歷史新聞紀錄，亦嚴禁將任何 API Key 寫入程式碼或推送至遠端。

## V2 核心定位與設計定案

- **品牌精神**：從 25 年、11,496+ 篇環境部新聞中，為台灣環境政策「**找脈絡、把脈、把關**」，讓一般讀者覺得比官方網站更有故事、更好讀，並成為學術界與研究生優先引用的台灣環境政策研究入口。
- **視覺美學**：**專業顧問／教授智庫誌風格**——沉穩深翠綠（`#0F4C3A`）為主色、暖象牙白（`#F8F9F7`）為底色、細緻暖金／琥珀（`#B45309`）為重點色，排版具備編輯雜誌層次感與優雅動態微互動。
- **品牌資產掛載**：
  - Logo：`web/public/images/logo.png`（支援自動偵測 `.svg` / `.png` / `.webp`，若尚未放入則以精緻文字徽章優雅降級不破圖）。
  - 個人形象圖：`web/public/images/hao-portrait.png`（支援 `.jpg` / `.png` / `.webp`，置於首頁開場與《皓哥說》專欄作者卡）。
- **新聞關聯引擎（路線 3：雙層混合語意網絡）**：結合 **TF-IDF 中文專有名詞向量** 與 **類神經網路語意嵌入向量（Neural Embeddings，Gemini Embedding API 免費層／自動降級 TF-IDF）**，計算全站 11,496+ 篇新聞之雙向語意關聯權重與時間軸前後關係，並以互動式「**巨觀政策神經網絡圖 ＋ 單篇局部關聯小星系圖**」呈現。
- **引用與署名規範**：全站「關於」與一鍵學術引用格式統一署名為 **「環策皓脈」** 並自動帶入當前頁面完整網址（例如：`環策皓脈（2026）。〈文章標題〉。環策皓脈。https://...`）。
- **流量分析**：前台**不放計數器**，保持版面乾淨專業；改於 Cloudflare Dashboard 後台啟用免費無追蹤 Cookie 的 **Cloudflare Web Analytics**。
- **預留未來擴充位（暫不公開）**：在架構中預留 `06_建站方法論/`（草稿制 `status: draft`），未來若決定新增「這個網站是怎麼做出來的」專屬分頁，只需改為 `published` 即可一鍵上線。

## Phase A：根治「原網址連回首頁」痛點 ＋ Obsidian 四層知識結構升級

### 任務目標
確保每篇新增新聞都能精準對應環境部單篇原文網址（絕不再拿官網首頁充數），並將 Obsidian Vault 升級為「原料 → 脈絡 → 觀點 → 研究」四層結構。

### 執行細項
1. **實作「精準原網址自動配對器」（修補 `scripts/sync_moenv_opendata.py`）**：
   - 問題根因：[環境部開放資料 MNEWS_P_01](https://data.moenv.gov.tw/dataset/detail/MNEWS_P_01) 的 `relativeurl` 欄位常為 `"-"`，導致舊版將 `source_url` 回退成列表首頁。
   - 修正方案：
     1. 增量抓取 `MNEWS_P_01` 後，針對所有 `source_url` 缺少單篇網址（非 `/moenv-news/zh-tw/News/<id>` 或 `/Page/3B3C62C78849F32F/<uuid>`）的新聞，自動啟動輕量 **URL Resolver**：
        - 優先抓取環境部新聞列表頁（`https://enews.moenv.gov.tw/Page/B514A5023133ED27` 或 `https://enews.moenv.gov.tw/News/List?key=11&Lang=zh-tw`）前 2 頁，以「正規化標題＋發布日期」比對出精準的 `/moenv-news/zh-tw/News/<數字ID>`。
        - 若列表頁未命中，嘗試從目前已知最大數字 ID（如 `14518`）往後探測連續編號（最多 `+40` 筆，加上禮貌延遲與逾時保護），比對 `<title>` 或 `<h1>` 吻合即寫回精準 `source_url`。
     2. **零首頁充數原則（嚴格防呆）**：若因暫時性網路或驗證導致極少數篇目尚未配對到單篇網址，**嚴禁填入環境部首頁網址**！請將 `source_url` 設為 `""`、新增欄位 `source_url_status: "pending_official_link"`，並於每日排程自動重試補齊最近 14 天內標記為 `pending` 的篇目；前端顯示時改為「站內閱讀開放資料全文（來源：環境部 MNEWS_P_01，官網單篇連結同步中）」。
     3. **立即回補既有新篇目**：針對 2026-11-16 之後已入庫且連回首頁的新聞（例如 `環境部修正「事業及污水下水道系統水污染防治費收費辦法」第11條、第27條` 應精準配對至 `https://enews.moenv.gov.tw/moenv-news/zh-tw/News/14530`），執行一次自動回補修正。
2. **Obsidian 四層知識演化結構與《皓哥說》把脈工作流**：
   - **自動產出候選雷達 `04_皓哥說/00_待把脈候選雷達.md`**：每次 `sync_moenv_opendata.py` 執行後，自動從近 14 天新聞中篩選具備「高政策訊號關鍵字」（`修正`、`預告`、`草案`、`費率`、`徵收`、`施行`、`辦法`、`準則`、`列管`、`裁罰`、`COP`、`淨零`）的新聞，按日期與訊號分數排序列出，附上標題、發布單位、對應議題與單篇原網址，供皓哥挑題。
   - **升級 `04_皓哥說/_template_draft.md`（皓哥四段把脈模板）**：
     - Frontmatter 固定包含：`title`、`date`、`status`（`draft` | `published`）、`summary`、`topics`、`related_news`（新聞 ID 陣列）、`timeline_slug`（選填，對應政策脈絡線）。
     - 內文固定四段結構：`## 一、看門道（一句話破題）`、`## 二、追脈絡（前世今生）`、`## 三、皓哥把脈與把關（實務衝擊與盲點）`、`## 四、給企業與讀者的行動提醒`。
   - **新增 `05_政策脈絡線/` 資料夾**：存放跨年度重大法規／政策事件時間軸設定檔（例如 `water-pollution-fee.json`、`carbon-fee.json`、`pfas-control.json`、`resource-circulation.json`），支援由 Python 自動從 11,496+ 筆新聞依關鍵規則彙整歷次「預告 → 研商 → 修正發布 → 施行」節點。

### 驗收標準
- [ ] 全資料庫中**零筆**新聞將 `https://enews.moenv.gov.tw/News/List?key=11&Lang=zh-tw` 偽裝為單篇原文連結。
- [ ] 2026-11-17～2026-11-20 新增的環境部新聞（含水污費第 11、27 條修正）均已精準對應至 `/moenv-news/zh-tw/News/<id>`。
- [ ] `04_皓哥說/00_待把脈候選雷達.md` 與 `05_政策脈絡線/` 均已自動生成且格式正確。

## Phase B：雙層混合新聞關聯引擎（路線 3）與前端資料管線升級

### 任務目標
建立 **TF-IDF ＋ 類神經語意向量（Neural Embeddings）** 雙層混合關聯引擎，為全部 11,496+ 篇新聞計算「前世今生」關聯邊與權重，同步強化 Obsidian 雙向連結與網站互動關聯圖，並維持 [Cloudflare Pages 免費額度](https://developers.cloudflare.com/pages/platform/limits/) 與 $0 成本。

### 執行細項
1. **建立雙層混合關聯計算腳本 `scripts/build_news_relations.py`**：
   - **第一層：TF-IDF 中文專有名詞向量（必執行，約 5～10 秒全量運算）**：
     - 使用 `scikit-learn` `TfidfVectorizer` ＋ `jieba`（掛載 `moenv_keyword_database.json` 內 20 大議題同義詞與環保法規專有名詞作為自訂詞典），計算每篇新聞的標題＋摘要詞頻特徵向量與餘弦相似度 $S_{\text{tfidf}}(i, j)$。
   - **第二層：類神經網路語意向量（Neural Embeddings，增量快取，$0 免費層）**：
     - 優先透過 `GEMINI_API_KEY`（Google AI Studio [Free Tier](https://aistudio.google.com/docs/pricing)）呼叫 `gemini-embedding-001`（或本機開源中文向量模型）產生語意向量，並以壓縮快取存於 `_local/embeddings_cache.npz`（不推送龐大向量原始檔至公開網站，只做增量計算——僅對尚未向量化的新增新聞呼叫 API）。
     - **自動降級防呆**：若環境無 `GEMINI_API_KEY` 或遭遇限流（見 [Rate Limits](https://aistudio.google.com/docs/rate-limits)），自動以 100% TF-IDF 權重無縫完成計算，絕不中斷每日排程。
   - **混合權重融合與時間軸方向標記**：
     - 融合公式：$w_{ij} = \alpha \cdot S_{\text{tfidf}}(i, j) + (1 - \alpha) \cdot S_{\text{embed}}(i, j)$（有 Embedding 時預設 $\alpha = 0.45$；降級模式時 $\alpha = 1.0$），另對同政策議題給予適度權重加成。
     - 為每篇新聞擷取最高關聯的 **Top 5 關聯新聞**（過濾低於門檻值之雜訊），並依發布日期自動標記方向：`direction: "earlier"`（前期脈絡／前因）或 `"later"`（後續演進／延伸），保留百分比關聯度 `score`（例如 `0.88`）。
   - **回寫 Obsidian 單篇筆記**：對新增新聞（以及可選批次更新模式）在單篇 `.md` 筆記底部自動寫入 `## 關聯新聞（前世今生）` 雙向連結（`[[...]]`），大幅提升 Obsidian Graph View 的脈絡密度。
2. **擴充 `scripts/export_web_data.py`，於 `web/public/data/` 新增輸出**：
   - `policy_graph.json`（供**巨觀「政策脈絡神經網絡圖」**使用）：
     - `nodes`：五大板塊母節點 ＋ 20 大政策議題節點 ＋ 核心高頻法規／事件群聚節點（含聲量、近 30 天升溫幅度）。
     - `links`：整合議題共現強度與路線 3 語意關聯權重，呈現多層次政策神經網絡。
   - `relations/YYYY.json`（按年份切分約 26 個輕量檔，供**單篇新聞「局部關聯小星系圖」**使用）：
     - 儲存該年度每篇新聞的 Top 5 關聯邊（目標 `news_id`、`date`、`title`、`unit`、`direction`、`score`、`source_url`），單檔輕量、點擊秒載入。
   - `timelines.json`（供**政策演進時間軸**使用）：
     - 自動彙整至少 6 條代表性政策脈絡線（碳費制度與自主減量、水污染防治費收費辦法演進、PFAS 化學物質列管、資源循環與減塑、空氣品質與空污防制、國際氣候會議 COP 參與），列出「預告 → 研商 → 修正發布 → 施行」關鍵節點與精準原網址。
   - `downloads/`（供**學術研究一鍵下載**使用）：
     - `moenv_topic_yearly_matrix.csv`（2001～最新年份 × 20 大議題聲量矩陣，UTF-8 with BOM 確保 Excel 開啟不亂碼）。
     - `moenv_unit_yearly_stats.csv`（環境部各司署歷年發布量統計表）。
     - `moenv_methodology_metadata.json`（含資料截止日、`dataset_version` SHA-256 指紋、20 大議題同義詞規則表與路線 3 關聯演算法說明）。

### 驗收標準
- [ ] `scripts/build_news_relations.py` 成功為全部 11,496+ 篇新聞產出 Top 5 關聯邊，實測水污費第 11、27 條修正新聞（`14530`）的前期關聯能自動命中歷次水污費預告／修正新聞。
- [ ] `web/public/data/` 總檔案數 < 90 檔、單檔均遠低於 25 MiB。
- [ ] 測試無 `GEMINI_API_KEY` 時自動降級至 TF-IDF 模式並以 Exit Code `0` 完成。

## Phase C：首頁「四幕故事鋪陳」＋ 雙層互動關聯圖與智庫級視覺重設計（`web/`）

### 任務目標
以「**有鋪陳、有故事、有引導、有價值**」重構全站體驗，完整融入皓哥個人品牌資產與「巨觀＋微觀」兩層動態關聯圖視覺化。

### 執行細項
1. **全域品牌識別與導覽列**：
   - 頂部導覽列左側掛載 `web/public/images/logo.png` ＋「環策皓脈」標題。
   - 導覽選單：`首頁`、`皓哥說`、`政策神經網`、`趨勢脈絡`、`全量新聞`、`學術研究`、`關於與宣告`。
2. **首頁四幕敘事動線（`web/src/pages/index.astro`）**：
   - **第一幕｜品牌開場 × 皓哥把脈宣言（Hero）**：
     - 左側：主標與定位敘事（「環境部 25 年累積超過一萬篇新聞，然後呢？環策皓脈為你從公告海裡找出政策脈絡，把脈、把關。」）、兩個引導按鈕（「閱讀最新《皓哥說》」、「探索政策神經網絡」）。
     - 右側：精緻呈現 **個人形象圖（`web/public/images/hao-portrait.png`）** 與「**本月政策體溫計**」動態脈搏卡片（柔和 SVG 脈搏動畫 ＋ 近 30 天升溫最快的 Top 3 議題）。
     - 底部 KPI 數字條：平滑 **Count-up 動態跳動效果**（累計收錄篇數、涵蓋年數、已建立新聞關聯邊數、最近自動同步時間）。
   - **第二幕｜主編焦點：《皓哥說》＋ 政策前世今生連動**：
     - 雜誌頭條大卡呈現最新《皓哥說》（含作者卡、一句話破題、議題標籤），右側同步展示該議題相關的「**政策演進時間軸**」精選節點。
   - **第三幕｜巨觀動態「政策脈絡神經網絡圖」（首頁預覽 ＋ 獨立 `/policy-map` 全螢幕專頁）**：
     - 使用 **Apache ECharts 力導向／星系關聯圖**呈現五大板塊 → 20 大議題 → 核心法規群聚的動態神經網絡（節點大小代表聲量、光暈代表近 30 天升溫、連線粗細對應路線 3 關聯權重）。
     - 支援滑鼠懸停「神經傳導式」點亮整條關聯路徑、拖曳縮放、點擊節點直接檢視該議題趨勢與代表新聞，並可一鍵切換「25 年政策重心演變動態折線圖」。
   - **第四幕｜最新新聞快訊 ＋ 單篇微觀「局部關聯小星系圖（Local Graph）」**：
     - 點擊全站任一新聞（首頁快訊、`/news` 檢索室或議題頁）展開閱讀抽屜時，除完整摘要與**精準環境部單篇原網址**外，下方直接呈現：
       1. **迷你互動關聯圖（Local News Graph）**：以本篇新聞為中心，左側連向「前期脈絡（前因）」、右側連向「後續演進（延伸）」，點擊任何關聯節點即可無縫跳讀該篇歷史新聞！
       2. **Top 5 關聯新聞卡片列表**：顯示關聯度百分比（如 `88% 高度相關`）與發布日期。
3. **動態微互動細節（優雅不浮誇）**：
   - 採用輕量 CSS / IntersectionObserver 實作區塊進場淡入（Scroll Reveal）、KPI 數字 Count-up、ECharts 互動動畫與平滑抽屜轉場，並尊重 `prefers-reduced-motion` 無障礙設定。

### 驗收標準
- [ ] 首頁與 `/policy-map` 的巨觀政策神經網絡圖可流暢互動、懸停高亮與點擊導覽。
- [ ] 點開任一篇新聞皆能即時載入該篇的「微觀局部關聯小星系圖」與 Top 5 前世今生新聞，點擊節點可無縫跳讀。
- [ ] Logo 與個人形象圖掛載機制完整，桌機與手機版（RWD）皆無跑版與 Console 紅字錯誤。

## Phase D：學術研究級專區（4 大功能全上）＋ 資料宣告／智財權／免責聲明

### 任務目標
讓研究生、學者與實務顧問將「環策皓脈」列為研究台灣環境政策的第一站，並建立無可挑剔的合法授權與智財權宣告。

### 執行細項
1. **學術研究專區升級（`web/src/pages/research.astro`）**：
   - **① 政策演進「法規時間軸」模組**：互動式切換各條政策脈絡線（碳費、水污費、PFAS、資源循環等），呈現「預告 → 研商 → 修正發布 → 施行」完整歷程，每節點皆直達環境部單篇原文。
   - **② 研究級統計資料開放下載區**：提供 `moenv_topic_yearly_matrix.csv`、`moenv_unit_yearly_stats.csv` 與 `moenv_methodology_metadata.json` 一鍵下載，明確標示資料涵蓋期間、更新日期與 SHA-256 版本指紋。
   - **③ 一鍵複製「標準學術引用格式」元件（全站通用 `CitationBox.astro`）**：
     - 嵌入於每篇《皓哥說》文章頁、`/research` 研究專區與 `/topics/[slug]` 議題專頁。
     - 支援切換並一鍵複製 **APA 7th 格式** 與 **中文學術論文格式**，統一署名為 **「環策皓脈」並自動帶入當前頁面完整網址**，同時提醒並列原始環境部新聞來源。
   - **④ 公開「分類口徑與關聯演算法說明（Methodology）」**：透明公開 20 大議題詞表、同義詞規則、一文多標籤統計口徑、去重演算法與路線 3（TF-IDF ＋ 類神經語意向量）關聯計算原理。
2. **資料宣告、智財權與免責聲明（全站頁尾 ＋ `/about` 專頁）**：
   - **全站頁尾精簡宣告條**：明示「資料來源：中華民國環境部（環境部新聞專區及環境資料開放平臺 `MNEWS_P_01`），依政府資料開放授權條款引用｜本站為獨立政策觀察與研究平台，非環境部官方網站｜《皓哥說》與脈絡分析 © 環策皓脈」，並附 `/about` 完整宣告連結。
   - **專屬 `/about` 頁面（「關於環策皓脈、資料宣告與免責聲明」）**：
     - 品牌緣起與作者理念（放上個人形象圖與「找脈絡、把脈、把關」核心理念）。
     - **資料來源與開放授權宣告**：完整標註 [環境部環境資料開放平臺 MNEWS_P_01](https://data.moenv.gov.tw/dataset/detail/MNEWS_P_01) 與 [政府資料開放授權條款（OGDL 1.0）](https://data.gov.tw/license)。
     - **智慧財產權歸屬說明**：明確區分「官方新聞稿與附檔（歸屬環境部及原發布單位）」與「原創《皓哥說》評論、政策脈絡編排、關聯分析與視覺化圖表（歸屬環策皓脈）」。
     - **獨立立場與免責聲明**：強調本站非政府官方機關，所有法規條文、費率、施行日期與裁罰標準，均以環境部及行政院公報正式公告為準。

### 驗收標準
- [ ] `/research` 頁面的 4 大學術功能（時間軸、CSV/JSON 下載、一鍵 APA／中文引用複製、研究方法與關聯演算法公開）全部正常運作。
- [ ] 全站頁尾與 `/about` 完整呈現資料來源、智財權與免責聲明，且前台無瀏覽計數器雜訊。

## Phase E：建置驗證、GitHub Actions 整合與上線

### 執行細項
1. 更新 `.github/workflows/daily-sync.yml`，確保每日排程依序執行：`sync_moenv_opendata.py` → `build_news_relations.py` → `export_web_data.py` → 資料完整性檢查 → 有異動時自動 commit 並 push `main`。
2. 本機執行完整建置驗證：
   - `python scripts/sync_moenv_opendata.py`
   - `python scripts/build_news_relations.py`
   - `python scripts/export_web_data.py`
   - `cd web && npm run build`
3. 確認 `web/dist/` 總檔案數 **< 600 個**（遠低於 Cloudflare Pages 20,000 檔上限），且 `status: draft` 草稿未外洩至 `dist/`。
4. 更新 `DEPLOYMENT_GUIDE.md`，補充「Cloudflare Dashboard 後台開啟免費 **Cloudflare Web Analytics**」以及「放入 `logo.png` 與 `hao-portrait.png` 到 `web/public/images/`」的簡明操作步驟。
5. 推送至 GitHub `main` 分支，確認 GitHub Actions 與 Cloudflare Pages 均綠燈自動部署完成。