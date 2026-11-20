# MOENV Policy Research Website Repository Discovery

查核日期：2026-09-12。範圍：唯讀 repository discovery；未修改網站、未啟動 V2 UI、未 build 或 deploy。

## Repository

- 真正網站 root：`C:/Users/aaron/Documents/Codex/2026-09-09/sites-plugin-sites-openai-bundled/work/site`。
- 對應 Codex 任務：打造環境部新聞分析網站，thread ID `01a0860f-8a77-7990-ac3a-f183d2ebdc4d`。
- 品牌：環策晧脈 HAO POLICY INTELLIGENCE。
- 分支：`main`。
- 查核 HEAD：`8187a9d430bd5a69c5e34abdacb8d73bea9dabfe`。
- `git status --short`：空白，查核時 working tree clean。
- `git remote -v`：無輸出，沒有設定 named remote。
- 任務部署記錄中的 source repository URL：`https://git.chatgpt-team.site/51f08335-b3f9-48f0-a0d6-8eed77025496/appgprj_6aa14cc6ca2881919c52e2fbbc075195.git`；當時是直接指定 URL push HEAD:main。這是歷史來源證據，本次未登入或查遠端 HEAD。
- Sites project：`appgprj_6aa14cc6ca2881919c52e2fbbc075195`，來自 `.openai/hosting.json`。
- 上線網址（設定及歷史發布記錄）：`https://taiwan-environment-observatory.whaochen.chatgpt.site/`。本次不宣稱已即時驗證線上部署版本。

先前在 vault 搜尋不到網站，僅證明網站不在 vault；不能延伸為網站不存在。另找到 ChatGPT 專案「環策晧脈網站開發」，但它不是本機 repository 路徑。

## Framework

- 原生 HTML/CSS/JavaScript ES modules，沒有 React、Vue、Next.js 或 Vite 前端依賴。
- `dist/` 直接保存可編輯前端來源；這個命名不能按一般 bundler 習慣直接視為可刪除產物。
- 入口 `dist/index.html`、`dist/app.js`；共用函式 `dist/core.mjs`。
- `package.json` 採 ESM，套件管理 pnpm。devDependencies 為 drizzle-kit 0.31.10、drizzle-orm 0.45.2，用於資料庫 schema/migration。
- `server/worker.mjs` 提供瀏覽計數 API，其餘請求交給 ASSETS。資料庫用途是瀏覽次數，不是政策研究資料庫。

## Routes

瀏覽器 hash routing，由 `dist/app.js:33` views、`:39` setView、`:66` routeHash 及 `dist/analysis-routes.mjs` 控制。沒有對應每篇研究的伺服器 SSR route。

| 路由 | 用途 |
|---|---|
| #home | 首頁，無 hash 時亦為首頁 |
| #signals、#topics | 近期訊號、議題熱度 |
| #overview、#motion、#river | 趨勢總覽、動態儀表板、政策河流 |
| #network、#lab | 議題網絡、進階分析 |
| #lab/anomalies、#lab/galaxy、#lab/agencies | 異常、政策星系、機關分析 |
| #regions、#local | 地域提及、地域演化 |
| #research | 政策研究目錄 |
| #research/report-N | 固定研究 ID，開啟閱讀 dialog |
| #methods、#methods/license、#data | 方法、授權、資料服務 |
| #haoge | app views 中的晧哥說入口 |

## Policy Research UI

- `dist/app.js:50 researchView()`：研究目錄，依 topic 與搜尋字詞篩選 meta.reports。
- `dist/app.js:57 openReport(id)`：取 `./data/report-N.json`，顯示研究日期、證據截止日、原稿、來源、相關議題與下載。
- `dist/core.mjs:9 markdown()`：自行實作 Markdown → HTML；支援部分標題、清單、表格、引文、行內格式與 HTTP(S) 連結。不是通用完整 Markdown 引擎。
- `pageObservation(r.id)` 另接人工觀察；不要將既有人工評論當作 Skill 自動產生的 trend_insights。
- 正文目前仍是 `{body:string}` JSON 包裝的 Markdown，尚非結構化研究內容。
- `report-registry.json` 保存檔名 → report-N。淨零轉型為 report-3，氣候變遷為 report-2；應保留 ID。

## Data Loading

### 實際發布邊界

```text
環境部新聞 vault
  JSONL + 關鍵字 CSV + profiles JSON + manifest + published Markdown
    → scripts/import-vault.mjs（手動、唯讀來源）
    → dist/data/articles.json + meta.json + report-N.json
    → scripts/build-worker.mjs
    → dist/client（公開投影）+ dist/server/index.js
    → Sites 儲存版本／發布
```

`scripts/import-vault.mjs:9–29` 讀取五類來源。新聞 ID 去重、總筆數與詞庫 total/year_counts assertions；來源若缺少已匯入新聞 ID 則中止。研究只讀 `status: published` 的 Markdown；frontmatter 使用字串/regex 解析，不是 YAML parser。

| 邊界物件 | 欄位／行為 |
|---|---|
| 內部 articles.json | id,date,title,category,unit,summary,url,topics:string[],regions:string[],note |
| 公開 articles.json | 相同但移除 note；`scripts/public-news.mjs` 白名單投影 |
| meta.json | count,start,end,generated,siteTotal,profiles,regions,reports,categories,summaryCount |
| meta.reports[] | id,title,updated,coverage,type,topics,abstract |
| report-N.json | body:string，移除 frontmatter 後的原稿 |
| report-registry.json | 檔名 → 固定 report-N；改名須遷移映射，舊 ID 不回收 |

欄位轉換：news_id → id；source_url → url；note_path → note（僅內部）；keyword_slugs 以分號切成 topics[]；regions 由標題與摘要明確地名派生，不代表事件座標。roc_date、views、image_url、site_topics、body 不進網站新聞投影。

`dist/app.js:65 init()` 初始 fetch meta.json 與 articles.json；研究正文按點擊載入。這是靜態 snapshot，不是即時研究 API。唯一現有 server API 是 GET/POST `/api/visits`。

### 已有 Schema 與版本

`scripts/build-services.mjs:14` 產出 `dist/services/schema.json`：JSON Schema draft 2020-12，定義公開新聞陣列，所有九個欄位 required，additionalProperties=false，topics/regions 為唯一字串陣列。

`services/dataset.json` 有 `schemaVersion:1`，版本為資料截止日加公開新聞 SHA-256 前十二位。查核值 `2026-09-12-d541cb14279f`；新聞 11362、研究目錄 16；sourceGenerated 為 2026-09-12T12:35:00+08:00，importedAt 為 2026-09-12T04:49:04.625Z。

因此「沒有 V1 schema」僅適用於研究 artifact；網站確實已有新聞下載 schema 和 schemaVersion 1，不能當成 V2 research schema 的既有版本。

靜態 services 還有 articles.csv、research.json、dataset.json、news.xml（最近50篇）、attribution.txt、rights.json；CSV 欄為日期、標題、原始分類、發布單位、政策議題、地域提及、官方來源。研究目錄額外帶 `/#research/report-N` URL。這些輸出由 build-services 產生，不是 vault Python 產生。

## Charting

未找到第三方 chart library 的 import 或 package dependency。現有圖表由原生 SVG、HTML/CSS 與 Canvas 自行繪製。

- `dist/app.js:42 yearChart()`：年度圖。
- `dist/animation.mjs`、`animation-core.mjs`：動態圖與地圖。
- `heatmap.mjs`、`network.mjs`、`river.mjs` 及各 core：熱圖、網絡、河流。
- `semantic.mjs:9`：Canvas 2D 語意投影。
- `dist/core.mjs:4 annual()`：在 from 到 to 範圍內生成每年 count，無命中年會得到 0；沒有由來源完整性狀態區分 missing/zero。V2 前需要資料層明確定義，但本次不改圖。

## Build 與 Preview

- package script：`pnpm build` → `node scripts/build-worker.mjs`。
- build-worker 先執行 buildGalaxy、buildServices、buildEditorials，再複製白名單資產到 dist/client，將 articles.json 改寫為不含 note 的公開投影。
- Worker 輸出 dist/server/index.js；hosting 與 drizzle migrations 複製到 dist/.openai。
- README 明定公開預覽使用 **dist/client**；不可直接把 dist 根目錄當公開服務，內部 dist/data 帶 note 路徑。
- 工作目錄上層有 `work/preview.mjs`，可用 `node ../preview.mjs dist/client`，預設 127.0.0.1:4173。它在網站 repository 外，沒有 package preview script。
- 歷史任務也使用過 Python HTTP server（4173–4175）；本次未啟動 server，亦未驗證目前 port。
- 靜態 preview 不提供 D1 計數 API。未找到獨立 staging 環境設定或 staging URL，不將本機預覽等同完整 production runtime。

## Production Deploy

Hosting 為 Sites；`.openai/hosting.json` 含 project_id 與 D1 binding 名 DB。歷史完成任務顯示流程：驗證 → build → commit → 取得短期 repository write credential → 指定 source repository URL push → package-site.sh 打包 → Sites save_site_version(commit_sha,archive) → deploy_site_version → get_deployment_status。

這是任務紀錄中實際使用的部署流程，不是 package.json deploy script，也沒有找到本 repo 的 CI workflow。最後任務記錄顯示已發布首頁五秒計數動畫，但本次未調用託管查詢或線上測試，無法保證遠端現在仍等於本機 HEAD。

## Environment Variables / Feature Flags

- runtime bindings：`env.DB`（D1）、`env.ASSETS`（静態資產）。
- build/import：vault 路徑由 command argument 傳入；production origin 在 build-services 內直接寫定。
- 未找到政策研究前端所需的 secret env variable 或中央 feature flag 設定；部署短期憑證與資料庫 binding 不等於研究功能旗標。
- 語意星系有模式選擇與資料版本不符時回退原文字模式；這是功能內 fallback，不是研究 V2 全站開關。
- 本次未讀取憑證或輸出 secret 值。

## Rollback

有 Git commit 歷史、Sites 儲存版本流程及部分歷史 tar.gz 包，可作版本追溯。未找到已驗證的 rollback runbook、自動回滾流程或 D1 反向 migration。

重新部署已保存版本是待在 Sites 平台確認的回復途徑；本次沒有實際回滾，也不將其標記為已驗證。應區分静態資產回復與資料庫遷移回復。

## V2 Integration Point（Discovery 結論，非實作規格）

1. 生產端應在 vault/研究層建立獨立 artifact；現有 Skill 本身沒有 Python 執行引擎。
2. 網站接收點已存在：scripts/import-vault.mjs 的匯入邊界，以及 build-worker/public-news 的公開輸出邊界。
3. 消費端為 researchView/openReport 與 report-N 固定路由。保留 report-registry ID；新 artifact 的 ID 對應尚需正式設計。
4. 現有新聞 JSON Schema 可繼續服務新聞下載；不應把 schemaVersion:1 改名成研究 V1。
5. Markdown 保留為原稿／既有閱讀 fallback，但新研究結構不能只是另一個 body 字串。
6. 網站主程式在目前 writable workspace 外。本次讀取已完成 discovery；未在網站端實作。後續網站修改應切換到上述網站 repository 任務，或依權限機制取得明確寫入許可。

## 查核方式與限制

已讀 package.json、README、hosting、Git metadata、import/build/service scripts、路由／研究 renderer／圖表程式、data-services 文件與網站任務最近部署記錄。部分首次廣域列檔遇到 work/qrdeps 存取限制，之後縮小至 work/site 直接查核，不影響所引用檔案。

本次未執行可寫入 website 的 build/test/import、未取得部署憑證、未重新發布。V2 Spec 在 Downloads 已找到，但逐欄 V2 mapping、WP2 validator 計畫與 V2 UI 不在本次交付。
