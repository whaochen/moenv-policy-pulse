import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import browser_news_update as flow


class BrowserImportTests(unittest.TestCase):
    def setUp(self):
        self.raw = (json.dumps(dict(news_id='100',date='2026-10-28'))+'\n').encode()
        self.bundle = dict(schemaVersion=1,baseSha256=flow.digest(self.raw),capturedAt=datetime.now(timezone.utc).isoformat(),listURL=flow.LIST_URL,officialTotal=2,listIds=['101','100'],articles=[dict(news_id='101',date='2026-10-31',roc_date='115-10-31',title='官方新聞',category='資源循環',unit='環境部',summary='官方首段摘要',source_url='https://enews.moenv.gov.tw/moenv-news/zh-tw/News/101')])

    def test_valid_new_records(self):
        old, new = flow.validate(self.bundle,self.raw)
        self.assertEqual([r['news_id'] for r in new],['101'])
        self.assertEqual(len(old),1)

    def test_rejects_invalid_evidence_before_write(self):
        changes = [lambda b:b.update(baseSha256='stale'),lambda b:b.update(listIds=['101']),lambda b:b.update(listIds=['101','101','100']),lambda b:b.update(officialTotal=3),lambda b:b.update(articles=[]),lambda b:b['articles'].append(copy.deepcopy(b['articles'][0])),lambda b:b['articles'][0].update(source_url='https://example.com/101'),lambda b:b['articles'][0].update(roc_date='115-10-30'),lambda b:b['articles'][0].update(summary=''),lambda b:b.update(capturedAt='2000-01-01T00:00:00Z'),lambda b:b['articles'][0].update(news_id='100')]
        for change in changes:
            b=copy.deepcopy(self.bundle);change(b)
            with self.subTest(bundle=b),self.assertRaises(ValueError):flow.validate(b,self.raw)

    def test_zero_new_is_valid_only_with_matching_total_and_overlap(self):
        self.bundle.update(articles=[],listIds=['100'],officialTotal=1)
        self.assertEqual(flow.validate(self.bundle,self.raw)[1],[])

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            vault=Path(d);(vault/'資料').mkdir();source=vault/'資料/moenv_news_index.jsonl';source.write_bytes(self.raw)
            evidence=vault/'evidence.json';evidence.write_text(json.dumps(self.bundle),encoding='utf-8')
            flow.import_bundle(vault,evidence,True)
            self.assertEqual(source.read_bytes(),self.raw)
            self.assertFalse((vault/'_local').exists())

    def test_blocked_crawler_leaves_request_not_false_success(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            vault=Path(d);(vault/'資料').mkdir();source=vault/'資料/moenv_news_index.jsonl';source.write_bytes(self.raw)
            blocked=subprocess.CompletedProcess([],1,'','RuntimeError: No news items found on the first page')
            with patch.object(flow.subprocess,'run',return_value=blocked):self.assertEqual(flow.crawler(vault,['--incremental']),20)
            request=flow.read_json(vault/'_local/browser-update/pending.json')
            self.assertEqual(request['baseSha256'],flow.digest(self.raw));self.assertEqual(source.read_bytes(),self.raw)
            success=subprocess.CompletedProcess([],0,'No changes detected','')
            with patch.object(flow.subprocess,'run',return_value=success):self.assertEqual(flow.crawler(vault,['--incremental']),0)
            self.assertFalse((vault/'_local/browser-update/pending.json').exists())

    def test_non_network_failures_and_full_crawls_do_not_trigger_browser(self):
        result=subprocess.CompletedProcess([],1,'','PermissionError: denied')
        with patch.object(flow.subprocess,'run',return_value=result):self.assertEqual(flow.crawler(Path('unused'),['--incremental']),1)
        result.stderr='No news items found'
        with patch.object(flow.subprocess,'run',return_value=result):self.assertEqual(flow.crawler(Path('unused'),['--full']),1)


if __name__=='__main__':unittest.main()
