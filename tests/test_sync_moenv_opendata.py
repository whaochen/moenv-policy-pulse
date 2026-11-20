from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ai_enricher  # noqa: E402
import moenv_news_indexer as indexer  # noqa: E402
import sync_moenv_opendata as syncer  # noqa: E402


class _FakeModelsOK:
    def generate_content(self, *, model, contents, config):
        payload = {
            "summary": "環境部公布碳費子法與自主減量計畫優惠費率審查原則，協助產業穩健邁向淨零轉型。",
            "policy_keywords": ["碳費徵收", "淨零轉型", "不存在的幻覺議題"],
            "ai_tags": ["碳費子法", "優惠費率", "COP31", "第四個應被截斷"],
        }
        return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))


class _FakeModels429:
    def generate_content(self, *, model, contents, config):
        raise RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded for gemini-2.5-flash-lite")


def _seed_vault(vault: Path) -> Path:
    existing = indexer.NewsItem(
        news_id="14518",
        title="環境部COP31「綠色算力與氣候數位科技」論壇",
        roc_date="115-11-16",
        date="2026-11-16",
        category="氣候變遷",
        unit="環境部氣候變遷署",
        views=None,
        summary="既有歷史新聞摘要，不可被覆寫。",
        source_url="https://enews.moenv.gov.tw/moenv-news/zh-tw/News/14518",
        image_url="",
    )
    indexer.write_outputs(
        vault=vault,
        items=[existing],
        generated_at="2026-11-17T06:53:10+08:00",
        total_from_site=None,
        mode="incremental",
        new_count=1,
    )
    return vault / existing.note_path


def _sample_opendata_records() -> list[dict[str, str]]:
    return [
        # Duplicate by identity (same date + title, different newsno) -> must be skipped
        {
            "newsno": "20261116000001",
            "newstitle": "環境部COP31「綠色算力與氣候數位科技」論壇",
            "newscontent": "<p>重複新聞不應覆寫既有歷史紀錄。</p>",
            "newssource": "環境部氣候變遷署",
            "newsdate": "2026-11-16 09:00:00",
            "relativeurl": "-",
            "attachurl": "-",
            "deletemark": "0",
        },
        # Deleted record -> must be skipped
        {
            "newsno": "20261118000002",
            "newstitle": "已刪除測試新聞",
            "newscontent": "<p>應被略過。</p>",
            "newssource": "環境部綜合規劃司",
            "newsdate": "2026-11-18 10:00:00",
            "relativeurl": "-",
            "attachurl": "-",
            "deletemark": "1",
        },
        # Brand new record -> must be added
        {
            "newsno": "20261118000003",
            "newstitle": "環境部公告碳費自主減量計畫優惠費率審查辦法",
            "newscontent": "<p>環境部今日發布碳費與自主減量計畫相關審查機制，協助企業推動減碳。</p><p>第二段詳細說明。</p>",
            "newssource": "環境部氣候變遷署",
            "newsdate": "2026-11-18 14:30:00",
            "relativeurl": "-",
            "attachurl": "https://data.moenv.gov.tw/files/carbon-fee.pdf",
            "deletemark": "0",
        },
    ]


def test_sync_mode_a_gemini_mock_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    existing_note = _seed_vault(tmp_path)
    original_note_text = existing_note.read_text(encoding="utf-8")

    monkeypatch.setenv("MOENV_API_KEY", "test-moenv-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    fake_client = SimpleNamespace(models=_FakeModelsOK())
    result = syncer.sync_opendata(
        vault=tmp_path,
        moenv_api_key="test-moenv-key",
        gemini_api_key="test-gemini-key",
        fetch_fn=lambda url, r, t: _sample_opendata_records(),
        gemini_client=fake_client,
        list_fetcher=lambda page: [],
        detail_fetcher=lambda url: "",
    )

    assert result["existing_count"] == 1
    assert result["new_count"] == 1
    assert result["total_count"] == 2
    assert result["gemini_used_count"] == 1
    assert result["gemini_fallback_count"] == 0

    # Existing historical note untouched
    assert existing_note.read_text(encoding="utf-8") == original_note_text

    # JSONL contains 2 records with enriched fields on the new record
    rows = [
        json.loads(line)
        for line in (tmp_path / "資料" / "moenv_news_index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    new_row = next(r for r in rows if r["news_id"] == "20261118000003")
    assert new_row["date"] == "2026-11-18"
    assert new_row["roc_date"] == "115-11-18"
    assert new_row["source_url"] == ""
    assert new_row["source_url_status"] == "pending_official_link"
    assert new_row["attach_url"] == "https://data.moenv.gov.tw/files/carbon-fee.pdf"
    assert (tmp_path / "04_皓哥說" / "00_待把脈候選雷達.md").is_file()
    assert "碳費子法" in new_row["ai_tags"]
    assert len(new_row["ai_tags"]) == 3
    assert "碳費徵收" in new_row["ai_policy_keywords"]
    assert "自主減量計畫" in new_row["ai_policy_keywords"]
    assert "淨零轉型" in new_row["ai_policy_keywords"]
    assert "不存在的幻覺議題" not in new_row["ai_policy_keywords"]

    # Public markdown stats match JSONL count
    year_trends = (tmp_path / "02_環境部新聞_可公開" / "年度趨勢.md").read_text(encoding="utf-8")
    assert "- 新聞筆數：2" in year_trends


def test_sync_mode_b_without_gemini_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_vault(tmp_path)
    monkeypatch.setenv("MOENV_API_KEY", "test-moenv-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    monkeypatch.setattr(
        syncer,
        "fetch_incremental_records",
        lambda **kwargs: _sample_opendata_records(),
    )
    exit_code = syncer.main(["--vault", str(tmp_path), "--no-dotenv", "--no-resolve-urls"])
    assert exit_code == 0

    rows = [
        json.loads(line)
        for line in (tmp_path / "資料" / "moenv_news_index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    new_row = next(r for r in rows if r["news_id"] == "20261118000003")
    assert new_row["summary"] == "環境部今日發布碳費與自主減量計畫相關審查機制，協助企業推動減碳。"
    assert new_row["ai_tags"] == []


def test_sync_mode_c_gemini_429_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_vault(tmp_path)
    monkeypatch.setenv("MOENV_API_KEY", "test-moenv-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    fake_429_client = SimpleNamespace(models=_FakeModels429())
    result = syncer.sync_opendata(
        vault=tmp_path,
        moenv_api_key="test-moenv-key",
        gemini_api_key="test-gemini-key",
        fetch_fn=lambda url, r, t: _sample_opendata_records(),
        gemini_client=fake_429_client,
        resolve_urls=False,
    )

    captured = capsys.readouterr()
    assert "[WARN] Gemini fallback to rule engine" in captured.err
    assert result["new_count"] == 1
    assert result["gemini_used_count"] == 0
    assert result["gemini_fallback_count"] == 1

    # Also verify CLI exit code 0 when Gemini raises 429
    monkeypatch.setattr(
        ai_enricher,
        "_call_gemini",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("429 Too Many Requests")),
    )
    monkeypatch.setattr(
        syncer,
        "fetch_incremental_records",
        lambda **kwargs: _sample_opendata_records(),
    )
    exit_code = syncer.main(["--vault", str(tmp_path), "--no-dotenv", "--no-resolve-urls"])
    assert exit_code == 0


def test_url_resolver_list_and_sequential_probe(tmp_path: Path) -> None:
    _seed_vault(tmp_path)
    records = [
        {
            "newsno": "20261120095929",
            "newstitle": "環境部修正「事業及污水下水道系統水污染防治費收費辦法」第11條、第27條",
            "newscontent": "<p>水污染防治費收費辦法修正公告。</p>",
            "newssource": "環境部水質保護司",
            "newsdate": "2026-11-20 09:59:29",
            "relativeurl": "-",
            "attachurl": "-",
            "deletemark": "0",
        }
    ]

    def fake_detail(url: str) -> str:
        if url.endswith("/14530"):
            return "<html><head><title>環境部修正「事業及污水下水道系統水污染防治費收費辦法」第11條、第27條 - 環境部新聞專區</title></head></html>"
        return "<html><head><title>Not Found</title></head></html>"

    result = syncer.sync_opendata(
        vault=tmp_path,
        moenv_api_key="test-moenv-key",
        fetch_fn=lambda url, r, t: records,
        list_fetcher=lambda page: [],
        detail_fetcher=fake_detail,
    )
    assert result["url_resolved_count"] == 1
    assert result["url_pending_count"] == 0
    rows = [
        json.loads(line)
        for line in (tmp_path / "資料" / "moenv_news_index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    resolved = next(r for r in rows if r["news_id"] == "20261120095929")
    assert resolved["source_url"] == "https://enews.moenv.gov.tw/moenv-news/zh-tw/News/14530"
    assert resolved["source_url_status"] == ""
