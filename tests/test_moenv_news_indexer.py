from pathlib import Path
import argparse
from dataclasses import asdict
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import moenv_news_indexer as indexer


def test_parse_new_news_card_layout():
    html = '''
    <div>每頁顯示 15 筆，共 11,227 筆</div>
    <article role="listitem" class="news-card news-card--linked">
      <a href="/moenv-news/zh-tw/News/13676" class="clickBox" target="_self" title="移至新聞"><span>新聞</span></a>
      <div class="news-card__body">
        <h3 class="news-card__title">新版新聞標題</h3>
        <div class="news-card__info"><span class="news-card__date">115-07-14</span><span class="news-card__dept">環境部氣候變遷署</span></div>
        <div class="news-card__meta"><a class="news-card__badge GoTopicTag" data-title="高溫調適">高溫調適</a><a class="news-card__badge GoTopicTag" data-title="氣候變遷">氣候變遷</a></div>
      </div>
    </article>
    '''
    assert indexer.is_new_list_page(html)
    assert indexer.parse_total(html) == 11227
    items = indexer.parse_list_page(html)
    assert len(items) == 1
    assert items[0].news_id == "13676"
    assert items[0].title == "新版新聞標題"
    assert items[0].date == "2026-07-14"
    assert items[0].category == "高溫調適"
    assert items[0].site_topics == ["高溫調適", "氣候變遷"]
    assert items[0].unit == "環境部氣候變遷署"


def test_news_identity_is_stable_when_the_source_id_changes():
    legacy = indexer.NewsItem(
        news_id="legacy-uuid",
        title="同一則新聞",
        roc_date="115-07-14",
        date="2026-07-14",
        category="未標示",
        unit="未標示",
        views=None,
        summary="",
        source_url="https://example.test/legacy",
        image_url="",
    )
    migrated = indexer.NewsItem(
        news_id="13676",
        title="同一則新聞",
        roc_date="115-07-14",
        date="2026-07-14",
        category="未標示",
        unit="未標示",
        views=None,
        summary="",
        source_url="https://example.test/current",
        image_url="",
    )

    assert indexer.item_identity_key(legacy) == indexer.item_identity_key(migrated)


def test_merge_list_metadata_preserves_note_identity():
    existing = indexer.NewsItem(
        news_id="legacy-id", title="same news", roc_date="115-07-14", date="2026-07-14",
        category="old", unit="old unit", views=None, summary="existing summary",
        source_url="https://legacy.example/news", image_url="",
    )
    current = indexer.NewsItem(
        news_id="13676", title="same news", roc_date="115-07-14", date="2026-07-14",
        category="heat", unit="climate agency", views=None, summary="",
        source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/13676",
        image_url="https://enews.moenv.gov.tw/image.jpg", site_topics=["heat", "climate"],
    )
    indexer.merge_list_metadata(existing, current)
    assert existing.news_id == "legacy-id"
    assert existing.summary == "existing summary"
    assert existing.category == "heat"
    assert existing.site_topics == ["heat", "climate"]
    assert existing.source_url == current.source_url


def test_parse_new_article_content_layout():
    html = '''
    <div class="article-body">
      <div class="article-content">
        <p>新版新聞第一段摘要。</p>
        <p>新版新聞第二段內容。</p>
      </div><!-- /.article-content -->
    </div><!-- /.article-body -->
    '''

    assert indexer.parse_detail_summary(html) == "新版新聞第一段摘要。"
    assert "新版新聞第二段內容。" in indexer.parse_detail_body(html)


def test_detail_summary_falls_back_to_official_open_data_when_detail_is_challenged(monkeypatch):
    item = indexer.NewsItem(
        news_id="14049",
        title="臺灣首度40℃極端高溫實兵演練",
        roc_date="115-09-03",
        date="2026-09-03",
        category="氣候變遷調適",
        unit="環境部氣候變遷署",
        views=None,
        summary="",
        source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/14049",
        image_url="",
    )
    open_data = json.dumps(
        [
            {
                "newsno": "20260903202826",
                "newstitle": "不作秀只解痛！環境部AI轉型挺第一線",
                "newscontent": "<p>官方開放資料第一段摘要。</p><p>第二段內容。</p>",
                "newssource": item.unit,
                "newsdate": "2026-09-03 20:28:26",
                "relativeurl": "-",
                "attachurl": "-",
                "deletemark": "0",
            }
        ],
        ensure_ascii=False,
    )

    def fake_fetch(url, **_kwargs):
        if "data.moenv.gov.tw" in url:
            return open_data
        return '<html><head><title>Just a moment...</title></head></html>'

    monkeypatch.setattr(indexer, "fetch_url", fake_fetch)
    args = argparse.Namespace(
        retries=1,
        timeout=30,
        use_curl=True,
        summary_from_detail=True,
        summary_chars=500,
        include_detail=False,
        progress_every=10,
        delay=0,
    )

    indexer.fetch_detail_pages([item], args)

    assert item.summary == "官方開放資料第一段摘要。"


def test_incremental_falls_back_to_new_list_api_when_legacy_first_page_fails(monkeypatch):
    existing = indexer.NewsItem(
        news_id="existing-id",
        title="既有新聞",
        roc_date="115-07-14",
        date="2026-07-14",
        category="未標示",
        unit="未標示",
        views=None,
        summary="",
        source_url="https://example.test/existing",
        image_url="",
    )
    html = '''
    <div>每頁顯示 20 筆，共 1 筆</div>
    <article role="listitem" class="news-card news-card--linked">
      <a href="/moenv-news/zh-tw/News/13676" class="clickBox" target="_self" title="移至新聞"><span>新聞</span></a>
      <div class="news-card__body">
        <h3 class="news-card__title">既有新聞</h3>
        <div class="news-card__info"><span class="news-card__date">115-07-14</span><span class="news-card__dept">環境部氣候變遷署</span></div>
      </div>
    </article>
    '''

    def fail_legacy_fetch(*_args, **_kwargs):
        raise RuntimeError("legacy list blocked")

    monkeypatch.setattr(indexer, "fetch_url", fail_legacy_fetch)
    monkeypatch.setattr(indexer, "fetch_new_list_page", lambda page, retries, timeout: html)

    args = argparse.Namespace(
        retries=1,
        timeout=30,
        use_curl=True,
        summary_from_detail=False,
        limit=None,
        max_pages=None,
        delay=0,
        progress_every=10,
        include_detail=False,
    )

    items, total, new_ids, note_ids_to_write = indexer.crawl_incremental(args, [existing])

    assert total == 1
    assert new_ids == set()
    assert note_ids_to_write == {"existing-id"}
    assert items[0].news_id == "existing-id"
    assert items[0].unit == "環境部氣候變遷署"


def test_incremental_unchanged_existing_item_needs_no_output_write(monkeypatch):
    existing = indexer.NewsItem(
        news_id="14049",
        title="既有新聞",
        roc_date="115-09-03",
        date="2026-09-03",
        category="氣候變遷調適",
        unit="環境部氣候變遷署",
        views=None,
        summary="既有摘要。",
        source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/14049",
        image_url="https://enews.moenv.gov.tw/image.jpg",
        site_topics=["氣候變遷調適", "高溫調適"],
    )
    current = indexer.NewsItem(**asdict(existing))
    current.summary = ""

    monkeypatch.setattr(indexer, "fetch_first_list_page", lambda _args: ("", [current], True, 1))
    args = argparse.Namespace(
        retries=1,
        timeout=30,
        use_curl=True,
        summary_from_detail=False,
        limit=0,
        max_pages=0,
        delay=0,
        progress_every=10,
        include_detail=False,
    )

    items, total, new_ids, note_ids_to_write = indexer.crawl_incremental(args, [existing])

    assert total == 1
    assert new_ids == set()
    assert note_ids_to_write == set()
    assert items[0].summary == "既有摘要。"


def test_incremental_main_leaves_generated_files_untouched_when_nothing_changed(tmp_path, monkeypatch):
    item = indexer.NewsItem(
        news_id="14049",
        title="既有新聞",
        roc_date="115-09-03",
        date="2026-09-03",
        category="氣候變遷調適",
        unit="環境部氣候變遷署",
        views=None,
        summary="既有摘要。",
        source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/14049",
        image_url="",
        site_topics=["氣候變遷調適"],
        note_path="資料/環境部新聞專區/新聞/2026/09/14049.md",
    )
    data_dir = tmp_path / "資料"
    data_dir.mkdir()
    (data_dir / "moenv_news_index.jsonl").write_text(
        json.dumps(asdict(item), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest = data_dir / "moenv_news_manifest.json"
    manifest.write_text('{"sentinel": true}\n', encoding="utf-8")
    current = indexer.NewsItem(**asdict(item))
    current.summary = ""

    monkeypatch.setattr(indexer, "fetch_first_list_page", lambda _args: ("", [current], True, 1))
    monkeypatch.setattr(sys, "argv", ["moenv_news_indexer.py", "--incremental", "--vault", str(tmp_path)])

    assert indexer.main() == 0
    assert manifest.read_text(encoding="utf-8") == '{"sentinel": true}\n'
    assert not (tmp_path / "環境部新聞索引.md").exists()


class CrawlPaginationTests(unittest.TestCase):
    def test_full_reconciliation_preserves_existing_detail_when_list_has_none(self):
        existing = indexer.NewsItem(
            news_id="13992",
            title="既有新聞",
            roc_date="115-08-26",
            date="2026-08-26",
            category="氣候變遷",
            unit="環境部氣候變遷署",
            views=None,
            summary="既有摘要。",
            source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/13992",
            image_url="",
            body="既有全文。",
        )
        crawled = indexer.NewsItem(
            news_id="13992",
            title="既有新聞",
            roc_date="115-08-26",
            date="2026-08-26",
            category="氣候變遷",
            unit="環境部氣候變遷署",
            views=None,
            summary="",
            source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/13992",
            image_url="",
            body="",
        )

        reconciled = indexer.reconcile_full_crawl_items([crawled], [existing])

        self.assertEqual(reconciled[0].summary, "既有摘要。")
        self.assertEqual(reconciled[0].body, "既有全文。")

    def test_full_crawl_continues_when_new_list_api_does_not_report_total(self):
        first_item = indexer.NewsItem(
        news_id="13992",
        title="第一頁新聞",
        roc_date="115-08-26",
        date="2026-08-26",
        category="未標示",
        unit="未標示",
        views=None,
        summary="",
        source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/13992",
        image_url="",
        )
        second_item = indexer.NewsItem(
        news_id="13991",
        title="第二頁新聞",
        roc_date="115-08-25",
        date="2026-08-25",
        category="未標示",
        unit="未標示",
        views=None,
        summary="",
        source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/13991",
        image_url="",
        )
        fetched_pages = []

        def fetch_page(page, retries, timeout):
            fetched_pages.append(page)
            return {2: "second", 3: "empty"}[page]

        args = argparse.Namespace(
            max_pages=0,
            limit=0,
            delay=0,
            progress_every=1,
            include_detail=False,
            summary_from_detail=False,
            retries=1,
            timeout=30,
            use_curl=False,
        )

        with (
            patch.object(indexer, "fetch_first_list_page", return_value=("", [first_item], True, None)),
            patch.object(indexer, "fetch_new_list_page", side_effect=fetch_page),
            patch.object(indexer, "parse_list_page", side_effect=lambda html: [second_item] if html == "second" else []),
        ):
            items, total = indexer.crawl(args)

        self.assertIsNone(total)
        self.assertEqual([item.news_id for item in items], ["13992", "13991"])
        self.assertEqual(fetched_pages, [2, 3])

    def test_incremental_crawl_checks_later_pages_when_total_is_unknown(self):
        new_item = indexer.NewsItem(
            news_id="13992",
            title="新新聞",
            roc_date="115-08-26",
            date="2026-08-26",
            category="未標示",
            unit="未標示",
            views=None,
            summary="",
            source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/13992",
            image_url="",
        )
        existing = indexer.NewsItem(
            news_id="13991",
            title="既有新聞",
            roc_date="115-08-25",
            date="2026-08-25",
            category="未標示",
            unit="未標示",
            views=None,
            summary="",
            source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/13991",
            image_url="",
        )
        fetched_pages = []

        def fetch_page(page, retries, timeout):
            fetched_pages.append(page)
            return "existing" if page == 2 else "empty"

        args = argparse.Namespace(
            max_pages=0,
            limit=0,
            delay=0,
            progress_every=1,
            include_detail=False,
            summary_from_detail=False,
            retries=1,
            timeout=30,
            use_curl=False,
        )

        with (
            patch.object(indexer, "fetch_first_list_page", return_value=("", [new_item], True, None)),
            patch.object(indexer, "fetch_new_list_page", side_effect=fetch_page),
            patch.object(indexer, "parse_list_page", side_effect=lambda html: [existing] if html == "existing" else []),
            patch.object(indexer, "fetch_detail_pages"),
        ):
            items, total, new_ids, note_ids_to_write = indexer.crawl_incremental(args, [existing])

        self.assertIsNone(total)
        self.assertEqual([item.news_id for item in items], ["13992", "13991"])
        self.assertEqual(new_ids, {"13992"})
        self.assertEqual(note_ids_to_write, {"13992"})
        self.assertEqual(fetched_pages, [2])


def test_new_list_api_request_uses_ajax_browser_headers(monkeypatch):
    captured = {}

    class FakeResponse:
        class Headers:
            @staticmethod
            def get_content_charset():
                return "utf-8"

        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"<div></div>"

    def fake_urlopen(request, timeout, context):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["data"] = request.data
        return FakeResponse()

    monkeypatch.setattr(indexer, "urlopen", fake_urlopen)

    assert indexer.fetch_new_list_page(1, retries=1, timeout=30) == "<div></div>"

    headers = captured["headers"]
    assert captured["url"].endswith("/WebAPI/WebsiteList/NewsList")
    assert b"Key=11" in captured["data"]
    assert headers["Referer"] == "https://enews.moenv.gov.tw/News/List?key=11&Lang=zh-tw"
    assert headers["Origin"] == "https://enews.moenv.gov.tw"
    assert headers["X-requested-with"] == "XMLHttpRequest"


def test_generic_urllib_fetch_uses_browser_headers(monkeypatch):
    captured = {}

    class FakeResponse:
        class Headers:
            @staticmethod
            def get_content_charset():
                return "utf-8"

        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"<html></html>"

    def fake_urlopen(request, timeout, context):
        captured["headers"] = dict(request.header_items())
        return FakeResponse()

    monkeypatch.setattr(indexer, "urlopen", fake_urlopen)

    assert indexer.fetch_url_with_urllib("https://enews.moenv.gov.tw/moenv-news/zh-tw/News/13908", 30) == "<html></html>"

    headers = captured["headers"]
    assert headers["User-agent"].startswith("Mozilla/5.0 (Windows NT 10.0")
    assert headers["Referer"] == "https://enews.moenv.gov.tw/News/List?key=11&Lang=zh-tw"
    assert headers["Accept-language"] == "zh-TW,zh;q=0.9,en;q=0.8"


def test_detail_fetch_failure_does_not_abort_remaining_items(monkeypatch):
    blocked = indexer.NewsItem(
        news_id="blocked",
        title="blocked detail",
        roc_date="115-08-17",
        date="2026-08-17",
        category="未標示",
        unit="未標示",
        views=None,
        summary="",
        source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/blocked",
        image_url="",
    )
    reachable = indexer.NewsItem(
        news_id="reachable",
        title="reachable detail",
        roc_date="115-08-17",
        date="2026-08-17",
        category="未標示",
        unit="未標示",
        views=None,
        summary="",
        source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/reachable",
        image_url="",
    )

    def fake_fetch(url, **_kwargs):
        if url.endswith("/blocked"):
            raise RuntimeError("HTTP Error 403: Forbidden")
        return '<div class="article-content"><p>可讀摘要。</p></div><!-- /.article-content -->'

    monkeypatch.setattr(indexer, "fetch_url", fake_fetch)
    args = argparse.Namespace(
        retries=1,
        timeout=30,
        use_curl=True,
        summary_from_detail=True,
        summary_chars=500,
        include_detail=False,
        progress_every=10,
        delay=0,
    )

    indexer.fetch_detail_pages([blocked, reachable], args)

    assert blocked.summary == ""
    assert reachable.summary == "可讀摘要。"


class RecentPolicyTrendTests(unittest.TestCase):
    def test_recent_policy_trend_compares_two_30_day_windows_from_latest_news_date(self):
        def item(news_id: str, date: str, title: str) -> object:
            return indexer.NewsItem(
                news_id=news_id,
                title=title,
                roc_date="115-09-03",
                date=date,
                category="氣候變遷",
                unit="環境部",
                views=None,
                summary="",
                source_url=f"https://example.test/{news_id}",
                image_url="",
                note_path=f"資料/環境部新聞專區/新聞/{date[:4]}/{date[5:7]}/{news_id}.md",
            )

        items = [
            item("current-1", "2026-09-03", "碳費制度最新說明"),
            item("current-2", "2026-08-05", "碳費徵收申報提醒"),
            item("previous-1", "2026-08-04", "碳費制度說明會"),
        ]

        rendered = indexer.render_recent_policy_trend(
            items,
            indexer.build_keyword_stats(items, indexer.build_keyword_matches(items)),
            "2026-09-04T09:00:00+08:00",
        )

        self.assertIn("2026-08-05 至 2026-09-03", rendered)
        self.assertIn("前 30 天", rendered)
        self.assertIn("碳費徵收", rendered)
        self.assertIn("current-1", rendered)
