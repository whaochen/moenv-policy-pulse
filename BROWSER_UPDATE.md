# 固定更新流程：爬蟲優先，Codex 瀏覽器備援

只在使用者要求更新時執行。不建立排程、不寄信、不全庫重抓。

## 固定入口

- `update-index.cmd`（或系統 PowerShell 無法啟動時 `& .\update-index.ps1`）先執行原增量爬蟲。
- 正常完成：按既有流程核對、同步網站；沒有變更時不要假稱新增。
- 結束碼 **20** / `BROWSER_REQUIRED`：讀取 `_local/browser-update/pending.json`，立即接續以下瀏覽器步驟。這表示來源存取失敗，**不是零篇新增**。
- 其他錯誤：處理該錯誤，不把檔案權限或程式錯誤誤認成 Cloudflare。

## Codex 瀏覽器備援（需要有可用瀏覽器工具的 Codex 工作階段）

1. 透過正常瀏覽器開啟 `https://enews.moenv.gov.tw/News/List?key=11&Lang=zh-tw`。確認畫面確實是新聞列表、取得即時官方總數，不使用搜尋快取總數代替。
2. 讀取目前 JSONL 的新聞 ID。依列表實際順序收集 ID；跨頁直到遇到第一個既有 ID。只收集該 ID 前的新新聞，不改舊新聞。若總數不符或需要歷史補洞，停止並回報差異，不按總數硬湊。
3. 逐篇用可見官方原文連結開啟內頁，取得標題、日期、單位、分類/官方標籤及第一段摘要（最多500字）。有的內頁使用 div 而非 p；找不到首段時停止，不能默填空白。不要把推薦新聞當成正文。
4. 若顯示 CAPTCHA 或安全警告，請使用者接手完成；不自動破解、不提取或持久保存 cookie/token。一般瀏覽器能正常讀取時不需重複問確認。
5. 將公共 DOM 讀取結果寫為 UTF-8 JSON 證據檔，放在本機非公開目錄。結構如下（以下只是結構示例，必須填入實際觀察值）：

```json
{
  "schemaVersion": 1,
  "baseSha256": "pending.json 的 baseSha256",
  "capturedAt": "帶時區的實際擷取時間 ISO8601",
  "listURL": "https://enews.moenv.gov.tw/News/List?key=11&Lang=zh-tw",
  "officialTotal": 11452,
  "listIds": ["新ID", "第一個既有ID"],
  "articles": [{
    "news_id": "新ID", "title": "官方標題",
    "date": "2026-10-31", "roc_date": "115-10-31",
    "category": "官方分類", "unit": "官方單位（未標示時填未標示）",
    "summary": "官方首段", "source_url": "https://enews.moenv.gov.tw/moenv-news/zh-tw/News/新ID",
    "image_url": "", "site_topics": ["官方標籤"]
  }]
}
```

6. 先執行 `& .\update-index.ps1 --browser-import '證據檔完整路徑' --dry-run`。檢查通過後，以相同指令移除 `--dry-run` 正式匯入。若來源已變更，重新核對，不能改雜湊硬過關。
7. 工具以 ID 去重、驗證日期/官方URL/總數/24小時內證據；備份原 JSONL 與證據至 `_local/browser-update/`；沿用原產生器重建索引，僅寫新增新聞筆記，禁止刪除舊筆記，並逐筆檢查舊記錄不變。成功寫入 `last-result.json` 並清除 pending。
8. 匯入是資料處理，沒有網路抓取或自動開瀏覽器功能。單獨執行腳本時，結束碼20要交由 Codex 接續；不能聲稱命令列能自動完成驗證。

## 接續環策晧脈

使用原網站專案 `scripts/import-vault.mjs` → `scripts/audit-source.mjs`，確認缺漏及既有內容差異為0；沿用既有服務輸出、語意分析、評論版本綁定、Worker建置與檢查流程。保留全部人工核定評論、原網址、研究ID、資料授權與瀏覽計數。通過後使用 Sites 原 project_id 發布。不要把 `_local`、備份、證據檔或筆記路徑上傳公開網站。

回報：本次新增篇數、最新新聞日期、兩邊總數、是否使用瀏覽器備援、未完成或異常。只在部署成功回傳後稱已發布。使用者提示詞不必更改。
