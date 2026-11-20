# 環策晧脈（HAO POLICY INTELLIGENCE）V2.3 互動中樞流光圖譜規格書 — `TASKS_V2_3_FLOW_ATLAS.md`

> **給 Google Antigravity 的執行指令**：本規格書旨在升級 `/architecture`（「建站幕後與系統架構」）頁面的核心區塊，將原本 5 個靜態白框替換為具備頂級科技遙測質感、且綁定真實活數據的互動元件 **「環策晧脈中樞流光圖譜（HAO PULSE FLOW ATLAS）」**。本次不更動 Python 同步管線，請完成元件實作後執行 `cd web && npm run build` 驗證並推送至 `main`。

## 一、設計美學與品牌調性

- **視覺靈感**：對標開發者遙測圖譜（深色高對比發光畫布 ＋ 持續流動的能量粒子 ＋ 弧線／雙向網格切換 ＋ 底部即時狀態列），但全面本土化並融入環策晧脈品牌色票，確保與淺象牙白頁面和諧對比、不顯突兀：
  - **畫布底色**：深墨綠炭黑漸層（`#071A14` → `#04110D`），搭配極淡幾何格線（`rgba(16, 185, 129, 0.08)`）與外框微光（`border border-emerald-500/25 shadow-2xl rounded-2xl`）。
  - **流光色票**：主光束為**翠綠流光（`#10B981` / `#34D399`）**、重點焦點為**暖金琥珀（`#F59E0B`）**、能量粒子為**亮白柔光（`#FFFFFF` 搭配 SVG glow filter）**。
  - **字體混搭**：數據、時間戳記與狀態標籤採等寬字體（`font-mono`），節點說明採清晰易讀的繁體中文，正字嚴格統一為 **「晧」（環策晧脈、晧哥說）**。
- **零假數據原則**：元件載入時必須動態讀取 `/data/manifest.json`（及 `/data/policy_graph.json` 摘要），將真實的累計新聞數、新聞關聯邊數、涵蓋年數與最後自動同步時間即時填入畫布與底部狀態列。

## 二、元件架構：`web/src/components/PulseFlowAtlas.astro`

請以**純原生 SVG ＋ HTML5 Canvas（或高效 SVG `<animateMotion>`）＋ TypeScript** 實作獨立元件，嵌入 `/architecture` 頁面取代原本的靜態 5 步驟白框（檔案輕量、零額外重型套件、60 FPS 流暢渲染）。

### 1. 頂部遙測控制列（Telemetry Header）
- **左側**：發光徽標點 ＋ `HAO PULSE FLOW ATLAS` ＋ 副標「環策晧脈全自動資料流動與 AI 協作中樞」。
- **中間三視圖切換膠囊**：
  - `FLOWS`（資料流光弧線）
  - `ARCS`（AI × 模組神經星芒網）
  - `LOGS`（即時同步遙測紀錄）
- **右側**：
  - 呼吸翠綠圓點 `LIVE` ＋ 真實同步時間戳記。
  - **「▶ 自動巡航 / ⏸ 暫停巡航」**切換按鈕（預設開啟自動巡航：每隔 4 秒自動依序聚焦下一個站點並彈出說明卡，方便訪客像看影片一樣欣賞；一旦使用者點擊或懸停任一節點，自動平順轉為手動探索）。

### 2. 視圖一：`FLOWS`（橫向弧線流光圖 Arc Diagram）
- **水平發光基準軸**：排列 5 大核心站點，各站點下方搭配迷你脈衝刻度條：
  1. `01 · MOENV OPEN DATA`（官方源頭：`MNEWS_P_01` ＋ 單篇原網址自動配對）
  2. `02 · GITHUB ACTIONS`（雲端排程：每日 08:00 增量同步與零幻覺統計）
  3. `03 · GEMINI × TF-IDF`（語意與關聯引擎：雙模型摘要與 56,000+ 條脈絡計算）
  4. `04 · OBSIDIAN VAULT`（晧哥把脈工作台：四層知識庫與《晧哥說》撰寫）
  5. `05 · ASTRO × CLOUDFLARE`（全球極速發布：年度分片靜態站點，永久 $0 託管）
- **發光弧線與持續流動能量粒子**：
  - 站點之間以多條優雅半圓貝茲弧線連接（含主資料流與跨站回饋弧線），並有**多顆亮白／翠綠／暖金發光粒子持續沿弧線穿梭移動**，呈現生動的資料脈動感。
- **焦點脈衝與懸浮資訊卡（Tooltip Card）**：
  - 當前聚焦站點（自動巡航或使用者點擊）亮起暖金／翠綠雙層脈衝光環，並於畫布上方（或右側）平滑呈現半透明深色玻璃態資訊卡，顯示該站點的：**核心工具／AI 模型名稱、處理規模（帶入真實數據）、關鍵工程價值（白話 2～3 點）**。
  - 右下角顯示迷你巡航進度指示器（例如 `03 / 05 · AI ENGINE`）。

### 3. 視圖二：`ARCS`（AI 模型 × 系統能力雙向神經星芒網）
- **左右對照高密度發光連線網格**：
  - **左側（資料源、AI 模型與開發協作）**：
    - `MOENV MNEWS_P_01`
    - `GitHub Actions`
    - `Gemini 2.5 Flash-Lite`
    - `gemini-embedding-001`
    - `TF-IDF + Jieba`
    - `Obsidian Git`
    - `Google Antigravity`
  - **右側（四大系統治理與產出模組）**：
    - `DATA`：官方原文擷取、單篇原網址自動配對、雙重指紋去重
    - `MEMORY`：25 年全量語料庫、56,175+ 條跨年關聯邊、Obsidian 四層筆記
    - `RULES`：零幻覺純程式統計、免費層自動降級備援、草稿安全閘門
    - `DELIVERY`：年度輕量分片 JSON、互動神經網絡圖、研究級 CSV 與引用格式
- **神經傳導互動高亮**：
  - 所有真實相依關係以細緻發光貝茲曲線連接並帶有慢速流動光點。
  - 滑鼠移上或點擊任一左側工具／右側模組時，**與它相連的所有光束瞬間高亮加粗為亮翠綠／暖金色，其餘非關聯連線柔暗至 12% 透明度**，並於畫布下方顯示一句白話解說該連結如何運作。

### 4. 視圖三：`LOGS`（終端機風格真實同步遙測紀錄）
- 以深墨綠終端機（CLI）美學呈現系統真實運作快照（由 `/data/manifest.json` 動態組裝真實時間與筆數）：
  - `[SYNC] MOENV MNEWS_P_01 incremental check ...... OK`
  - `[LINK] Official article URL resolver ............ MATCHED (0 homepage fallback)`
  - `[AI]   Gemini 2.5 Flash-Lite + Rule Fallback .... READY ($0 Free Tier)`
  - `[NET]  TF-IDF + gemini-embedding-001 graph ...... {real_links} edges indexed`
  - `[DATA] Yearly JSON shards + Research CSVs ....... EXPORTED (< 90 files)`
  - `[LIVE] Astro static build -> Cloudflare Pages ... DEPLOYED ($0/mo)`
- 支援一鍵「模擬重播每日 08:00 同步流程」逐行打字機動畫，讓一般讀者也能直覺看懂系統每天早上如何自動運作。

### 5. 底部常駐即時遙測狀態列（Telemetry Footer Bar）
固定於畫布最下方，以等寬字體呈現 6 項真實活數據：
- `NEWS`: `{total_news} 篇`（讀自 `manifest.json`）
- `RELATIONS`: `{total_links} 條`（讀自關聯統計）
- `SPAN`: `2001–2026 (26 YRS)`
- `AI ENGINE`: `GEMINI + TF-IDF`
- `INFRA COST`: `$0 / MO`
- `STATUS`: `LIVE · AUTO-SYNC ✓`

## 三、RWD、效能與驗收標準

- [ ] `/architecture` 頁面原本的 5 個靜態白框已完全替換為 `PulseFlowAtlas` 互動流光畫布。
- [ ] `FLOWS`、`ARCS`、`LOGS` 三個視圖皆可流暢切換；`FLOWS` 具備持續流動的發光粒子與自動巡航模式，`ARCS` 具備滑鼠懸停／點擊高亮神經路徑效果。
- [ ] 畫布中顯示的新聞總數、關聯邊數與同步時間戳記皆來自 `/data/manifest.json` 真實數據（非寫死假數字）。
- [ ] 手機版自動切換為直向緊湊流光版面不溢位，且尊重 `prefers-reduced-motion` 無障礙設定。
- [ ] `cd web && npm run build` 零錯誤完成並推送 `main` 成功自動上線。
