from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "moenv_news_indexer.py"
SPEC = importlib.util.spec_from_file_location("moenv_news_indexer", MODULE_PATH)
assert SPEC and SPEC.loader
indexer = importlib.util.module_from_spec(SPEC)
sys.modules["moenv_news_indexer"] = indexer
SPEC.loader.exec_module(indexer)


class DailyReportTests(unittest.TestCase):
    def test_daily_report_is_news_only(self) -> None:
        item = indexer.NewsItem(
            news_id="daily-news",
            title="環境部發布最新政策",
            roc_date="115-09-03",
            date="2026-09-03",
            category="氣候變遷",
            unit="環境部",
            views=None,
            summary="",
            source_url="https://example.test/daily-news",
            image_url="",
            note_path="資料/環境部新聞專區/新聞/2026/09/daily-news.md",
        )

        written: dict[str, str] = {}

        def capture_write(path: Path, text: str) -> None:
            written[path.as_posix()] = text

        vault = ROOT / "daily-report-test-vault"
        with patch.object(indexer, "write_text", side_effect=capture_write):
            indexer.write_daily_report(vault, [item], {item.news_id}, "2026-09-04T09:00:00+08:00")
        body = written[(vault / "資料" / "daily_update_reports" / "latest.md").as_posix()]
        payload = json.loads(written[(vault / "資料" / "daily_update_reports" / "latest.json").as_posix()])

        self.assertNotIn("研究報告待審", body)
        self.assertNotIn("research_review_file", payload)
        self.assertEqual(payload["count"], 1)


if __name__ == "__main__":
    unittest.main()
