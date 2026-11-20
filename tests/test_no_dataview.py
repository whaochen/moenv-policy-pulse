from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "moenv_news_indexer.py"
SPEC = importlib.util.spec_from_file_location("moenv_news_indexer", MODULE_PATH)
assert SPEC and SPEC.loader
indexer = importlib.util.module_from_spec(SPEC)
sys.modules["moenv_news_indexer"] = indexer
SPEC.loader.exec_module(indexer)


def make_item(sequence: int = 0) -> object:
    news_id = f"carbon-fee-{sequence:03d}"
    return indexer.NewsItem(
        news_id=news_id,
        title=f"環境部說明碳費制度 {sequence:03d}",
        roc_date="115-07-10",
        date="2026-07-10",
        category="氣候變遷",
        unit="環境部",
        views=None,
        summary="碳費制度與自主減量相關新聞。",
        source_url=f"https://example.test/{news_id}",
        image_url="",
        note_path=f"資料/環境部新聞專區/新聞/2026/07/{news_id}.md",
    )


def stats_with_items(items: list[object]) -> dict[str, object]:
    stats = {
        profile.slug: indexer.KeywordStats(profile=profile, items=[], years={})
        for profile in indexer.KEYWORD_PROFILES
    }
    carbon_fee = stats["carbon_fee"]
    carbon_fee.items.extend(items)
    carbon_fee.years["2026"] = len(items)
    return stats


class NoDataviewRenderTests(unittest.TestCase):
    def assert_no_dataview(self, rendered: str) -> None:
        self.assertNotIn("Dataview", rendered)
        self.assertNotIn("```dataview", rendered)
        self.assertNotIn("FROM \"資料/環境部新聞專區/新聞\"", rendered)

    def test_master_index_does_not_render_dataview_queries(self) -> None:
        items = [make_item()]
        rendered = indexer.render_master_index(
            items,
            "2026-07-10T09:00:00+08:00",
            1,
            stats_with_items(items),
        )

        self.assert_no_dataview(rendered)
        self.assertIn("## 最近新聞", rendered)

    def test_keyword_pages_do_not_render_dataview_queries_or_guidance(self) -> None:
        items = [make_item(sequence) for sequence in range(161)]
        stat = stats_with_items(items)["carbon_fee"]
        rendered = indexer.render_keyword_page(stat, {"carbon_fee": {}}, {})

        self.assert_no_dataview(rendered)
        self.assertIn("## 最近新聞", rendered)

    def test_index_pages_only_can_be_combined_with_rebuild_indexes(self) -> None:
        with patch.object(sys, "argv", ["moenv_news_indexer.py", "--rebuild-indexes", "--index-pages-only"]):
            args = indexer.parse_args()

        self.assertTrue(args.rebuild_indexes)
        self.assertTrue(args.index_pages_only)

    def test_write_text_falls_back_to_atomic_replace_on_permission_error(self) -> None:
        def write_side_effect(path_self: Path, *args: object, **kwargs: object) -> int:
            if path_self.name == "temporary-lock.md":
                raise PermissionError("locked")
            return 12

        with (
            patch.object(Path, "write_text", autospec=True, side_effect=write_side_effect) as write_mock,
            patch.object(Path, "replace", autospec=True) as replace_mock,
        ):
            indexer.write_text(Path("temporary-lock.md"), "content")

        self.assertEqual(write_mock.call_count, 2)
        replace_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
