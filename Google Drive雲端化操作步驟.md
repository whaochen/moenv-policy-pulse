# Google Drive 同步與手動更新

自2026-09-05起，本專案由使用者手動更新。Google Drive負責檔案同步與備份，不執行新聞更新。

## 目前工作本

```text
G:\我的雲端硬碟\環境部新聞
```

在Obsidian選擇「Open folder as vault」，開啟上述資料夾及 `環境部新聞索引.md`。舊的D槽資料夾不是目前工作本；本次未處理或刪除舊備份。

## 日常操作

1. 確認Google Drive已同步，工作檔案可用。
2. 在上述資料夾執行 `update-index.cmd`，或在Codex本專案說「請手動增量更新環境部新聞」。
3. 查看新增筆數、最新新聞日期與擷取異常。
4. 等Google Drive完成同步。

需要本地報告可使用 `update-index.cmd --daily-report --progress-every 5`，此指令不自行寄信。

## 已停用自動啟動

2026-09-05確認：`MOENV News Update 0900` 已設為Disabled；未找到其他MOENV工作排程；`MOENV News Catch-up.lnk` 已移出Startup。原排程XML與捷徑保存在 `_local_backups/manual-mode-2026-09-05/`，不可納入公開網站。

安裝與寄信腳本保留，只有日後明確要求恢復才使用，不要因更新文件或資料而重新安裝排程。

## 備份與公開

既有雲端備份位置（本次未查核內容）：[環境部新聞 Obsidian Vault](https://drive.google.com/drive/folders/1M1kIBRFZ8p5Ewc3UdIPVl7kkCMtYJ_LV)。

大量note由Drive桌面版同步；需要封存副本時可建立zip，避免連接器逐檔上傳。zip不能直接作為Obsidian vault使用。

公開網站只匯出核准的新聞欄位、議題與研究，不公開整個Drive資料夾。`local-mail.env`、排程備份與私人研究備註不可放入公開包。
