# 環策晧脈（moenv-policy-pulse）5 分鐘上線設定清單

本指南協助您將本機已驗證完成的 `moenv-policy-pulse` 專案推送至 GitHub，並完成 **GitHub Actions 每日全自動排程**、**Cloudflare Pages 永久免費託管** 與 **Obsidian Git 零摩擦寫作串接**。

---

## 步驟一：建立全新 GitHub 儲存庫並推送（1 分鐘）

1. 前往 [GitHub New Repository](https://github.com/new) 建立全新儲存庫，名稱建議為 `moenv-policy-pulse`（公開或私有皆可；**不要**勾選 Add README / .gitignore）。
2. 在本機 `D:\Projects\moenv-policy-pulse` 開啟終端機，先執行一次推送前安全確認，確保無任何金鑰或私有資料夾被追蹤：
   ```powershell
   git status
   git ls-files | Select-String -Pattern "\.env$|key\.env|_local|99_內部工作區"
   ```
   （第二行應無任何輸出。）
3. 綁定遠端並推送 `main` 分支：
   ```powershell
   git remote add origin https://github.com/<你的帳號>/moenv-policy-pulse.git
   git push -u origin main
   ```

---

## 步驟二：設定 GitHub Repository Secrets（1 分鐘）

前往 GitHub 儲存庫頁面 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，新增以下兩個變數：

| Secret 名稱 | 是否必填 | 取得方式與建議 |
| --- | --- | --- |
| `MOENV_API_KEY` | **必填** | 前往[環境部環境資料開放平臺](https://data.moenv.gov.tw/)重新換發一組全新 API Key（因舊歷史腳本曾出現過舊金鑰，建議直接輪替換新）。 |
| `GEMINI_API_KEY` | 選填 | 前往 [Google AI Studio](https://aistudio.google.com/apikey) 申請免費層 API Key（免綁信用卡）。若不填寫或遇限流（HTTP 429），管線會自動無縫降級為純 Python 規則引擎。 |

---

## 步驟三：驗證 GitHub Actions 自動排程（1 分鐘）

1. 切換至 GitHub 儲存庫的 **Actions** 分頁。
2. 點選左側 **Daily MOENV News Sync**，點擊右側 **Run workflow** → **Run workflow**（`workflow_dispatch` 手動觸發）。
3. 確認所有步驟綠燈通過：
   - `Sync MOENV Open Data (MNEWS_P_01) incrementally`
   - `Export static JSON shards for web frontend`
   - `Verify exported web data integrity`
   - `Commit and push data updates`
4. 之後系統會於**每日台灣時間 08:00（UTC 00:00）** 自動執行，有新新聞時自動提交回 `main` 並觸發 Cloudflare Pages 重新建置。

---

## 步驟四：綁定 Cloudflare Pages 部署新版網站（1 分鐘）

1. 登入 [Cloudflare Dashboard](https://dash.cloudflare.com/) → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**。
2. 選擇 `moenv-policy-pulse` 儲存庫，設定以下建置參數：
   - **Production branch**：`main`
   - **Framework preset**：`Astro`
   - **Root directory**：`web`
   - **Build command**：`npm run build`
   - **Build output directory**：`dist`
3. 展開 **Environment variables (advanced)**，新增：
   - `NODE_VERSION` = `20`
   - `ASTRO_TELEMETRY_DISABLED` = `1`
4. 點擊 **Save and Deploy**，約 30～60 秒後即可取得專屬 `*.pages.dev` 公開網址（既有 `chatgpt.site` 舊站完全不受影響）。

---

## 步驟五：Obsidian Git 外掛串接《晧哥說》寫作流程（1 分鐘）

1. 開啟 **Obsidian** → **Open folder as vault** → 選擇本機純 Git 目錄 `D:\Projects\moenv-policy-pulse`（切勿使用舊的 Google Drive 雙向同步目錄）。
2. 前往 Obsidian **Settings → Community plugins**，安裝並啟用 **Obsidian Git**。
3. 建議外掛設定：
   - **Pull on startup**：開啟（每次開啟 Obsidian 自動拉取 GitHub Actions 每日同步的最新環境部新聞）。
   - **Auto pull interval**：可設為 `60` 分鐘。
   - **Auto commit-and-sync**：關閉（由您自行控制發布時機）。
4. 撰寫與發布《晧哥說》專欄：
   - 複製 `04_晧哥說/_template_draft.md` 並重新命名（檔名**不可**以底線 `_` 開頭，例如 `2026-11-20-carbon-fee-insight.md`）。
   - 撰寫期間維持 `status: draft`（網站完全不會顯示或生成頁面）。
   - 定稿後改為 `status: published`，在 `related_news` 填入新聞編號（如 `"14518"`）。
   - 於 Obsidian 按下 **Ctrl+P** → 執行 **Obsidian Git: Commit all changes** 與 **Push**，約 1～2 分鐘後 Cloudflare Pages 即自動上線新文章！

---

## 步驟六（V2 選配）：掛載品牌 Logo 與個人形象照（1 分鐘）

本站已內建自動偵測與無破圖降級機制，您無須修改任何程式碼：

1. 將您的品牌 Logo 放入 `web/public/images/logo.png`（支援 `.svg` / `.png` / `.webp`，建議正方形透明背景）。
2. 將您的個人形象照放入 `web/public/images/hao-portrait.png`（支援 `.jpg` / `.png` / `.webp`，將自動顯示於首頁開場、《晧哥說》作者卡與 `/about` 頁面）。
3. 提交並推送至 GitHub `main` 分支（或於 Obsidian 執行 `Git: Commit all changes` + `Git: Push`），約 1 分鐘後即自動呈現於線上網站。

---

## 步驟七（V2 選配）：於 Cloudflare Dashboard 啟用免費 Web Analytics（免 Cookie）

為維持專業智庫誌版面乾淨，前台刻意不放訪客計數器；建議改於後台開啟免費、無追蹤 Cookie 的 **Cloudflare Web Analytics**：

1. 登入 [Cloudflare Dashboard](https://dash.cloudflare.com/) → 進入 **Workers 和 Pages** → 點選 **`moenv-policy-pulse`**。
2. 切換至上方 **指標（Metrics）** 或左側 **Analytics & Logs → Web Analytics**。
3. 點擊 **啟用 Web Analytics（Enable Web Analytics）**，選擇 `moenv-policy-pulse.pages.dev` 即可一鍵自動注入輕量統計，無需改動程式碼，且永久免費。
