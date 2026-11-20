# Policy Research V2：A-C 契約小修

日期：2026-09-13。依使用者「先做這 3 個小修」處理人工驗收文件 A-C；未執行文件後段的 Website Integration Plan，也未修改網站、部署或啟用排程。

## 完成項目

1. trend_series：series_id 改為受控 slug，unit 為非空字串；frequency 支援 year、quarter、month，metric_type 支援 count、percentage、amount、emissions、reduction、capacity、other。非新聞量序列可存小數且須提供可解析來源；期間格式、曆法、唯一性與順序均受檢核。article_count_yearly 仍精確核對 canonical 新聞量，訊號改為依 ID 尋找此序列。新增序列僅為合成測試 fixture，Pilot 沒有新增第二條序列。
2. key_events：date_precision 支援 day、month、year，date 分別為 YYYY-MM-DD、YYYY-MM、YYYY。schema 與 validator 拒絕格式不符或不存在日期。範圍判斷使用可能日期區間，不把月／年補成假日期；完全在 scope 外為 error，跨越 scope 邊界則為 EVENT_SCOPE_UNCERTAIN warning。Pilot 三個事件原日期與 day 精度完全未變。
3. research_summary：由作者輸入加入 headline、summary、source_ids，經編譯器輸出至 Pilot。base schema 仍 optional；正式 CLI 自動要求摘要，缺少即 SUMMARY_REQUIRED error。合成測試以 --publication 測試相同規則。摘要引用亦須可解析。

schema_version 保持 2.0；pipeline_version 為 2.0.1。

## 測試與驗證

各項新測試先確認舊實作失敗，再實作通過：A 完成後 53 項，B 完成後 57 項，C 完成後 61 項 V2 測試通過。

```text
.venv-policy-research/Scripts/python.exe -m unittest tests.test_policy_research_v2 -q
Ran 61 tests
OK

.venv-policy-research/Scripts/python.exe -m unittest discover -s tests -q
Ran 70 tests
OK

.venv-policy-research/Scripts/python.exe scripts/validate_policy_research_v2.py --artifact "03_政策研究/研究資料/net-zero-transition.v2.json"
PASS: 0 errors, 10 warnings
exit code: 0
```

正式 validator 使用真實 canonical 輸入，未使用 fixture-mode；已自動包含 publication-level 摘要檢核。全專案測試中的抓取訊息來自 mock 測試，並未執行新聞更新。

## 摘要內容

headline：淨零轉型：從組織與目標走向部門執行

summary：本 Pilot 聚焦臺灣淨零治理在 2023 至 2026 年的制度進展：氣候變遷署揭牌、行政院核定 NDC3.0，以及核定六大部門第三期溫室氣體減量行動方案。政策以相較 2005 年的 2030 年 28±2% 與 2035 年 38±2% 淨排放減量目標，連結 2026 至 2030 年部門措施及 20 項減碳旗艦行動計畫。這些證據支持專責組織、量化目標與執行安排逐步串接的判讀，但不代表減量成果已達成；未來研究仍須對照排放、預算與年度成果資料，檢驗承諾與執行之間的差距。

source_ids：moenv-news:3234、moenv-news:2078、moenv-news:1868。本次未新增政策事實或來源，摘要沿用已人工驗收的 Pilot 證據；未建立 phases。

## 保留與限制

已逐項比對修正前後的 statistics、trend_series、key_metrics、key_events、trend_insights、trend_signals、sources、quality，全部一致。仍為 899 則新聞、20 個年度點、10 個訊號、3 metrics、3 events、1 insight、3 sources。

四個 canonical 輸入、新聞索引器與原 Markdown 的 SHA-256 均與修正前相同。只新增摘要與更新 artifact 產出 metadata，沒有重寫原研究敘事。

10 則 validator warnings 全數保留：5 則原研究限制、1 則待人工驗收、1 則官方全站總數未知、1 則敘事／統計截止差異、2 則舊格式快照各少 ID 14099。詳細警告原文見 `docs/2026-09-13-policy-research-v2-pilot-review.md`。

quality.status 保持 needs_review。本次沒有把附件中「完成後可啟動網站」視為網站授權，也未把新摘要視為已獲人工確認；待使用者確認摘要與範圍後，再決定是否改為 passed_with_warnings。

## 本次檔案

| 動作 | Vault 相對路徑 |
|---|---|
| 修改 | schemas/policy_research_v2.schema.json |
| 修改 | scripts/policy_research_v2.py |
| 修改 | scripts/validate_policy_research_v2.py |
| 修改 | tests/test_policy_research_v2.py |
| 新增 | tests/fixtures/policy_research_v2.non_news_series.json |
| 修改 | 03_政策研究/研究資料/作者輸入/net-zero-transition.json |
| 重新產出 | 03_政策研究/研究資料/net-zero-transition.v2.json |
| 修改 | 03_政策研究/研究資料/README.md |
| 新增 | docs/2026-09-13-policy-research-v2-contract-hardening.md |
