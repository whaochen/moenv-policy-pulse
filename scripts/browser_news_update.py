"""Incremental crawler entry point and validated browser-evidence importer.

No browser credentials, cookie extraction, CAPTCHA solving or browser launching.
The Codex browser tool supplies public DOM evidence according to BROWSER_UPDATE.md.
"""
import argparse
import os
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

LIST_URL = 'https://enews.moenv.gov.tw/News/List?key=11&Lang=zh-tw'
BROWSER_REQUIRED = 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def source_bytes(vault):
    return (vault / '資料/moenv_news_index.jsonl').read_bytes()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate(bundle, raw):
    old = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
    ids = {r['news_id'] for r in old}
    require(len(ids) == len(old), 'Existing source has duplicate IDs')
    require(bundle.get('schemaVersion') == 1, 'Unsupported evidence schema')
    require(bundle.get('baseSha256') == digest(raw), 'Source changed; collect evidence against the current source')
    url = urlparse(bundle.get('listURL', ''))
    require(url.scheme == 'https' and url.netloc == 'enews.moenv.gov.tw' and url.path == '/News/List'
            and parse_qs(url.query).get('key') == ['11'] and parse_qs(url.query).get('Lang') == ['zh-tw'], 'Official news list URL required')
    captured = datetime.fromisoformat(bundle.get('capturedAt', '').replace('Z', '+00:00'))
    require(captured.tzinfo is not None and 0 <= (datetime.now(timezone.utc)-captured).total_seconds() <= 86400, 'Evidence must be captured within the last 24 hours')
    listed = bundle.get('listIds', [])
    require(isinstance(listed, list) and listed and all(isinstance(x, str) and x.isdigit() for x in listed), 'Visible list IDs required')
    require(len(listed) == len(set(listed)), 'Duplicate IDs in browser list')
    overlap = next((i for i, x in enumerate(listed) if x in ids), None)
    require(overlap is not None, 'Continue browsing until an existing news ID is reached')
    expected = set(listed[:overlap])
    rows = bundle.get('articles', [])
    require(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), 'Article objects required')
    new_ids = [r.get('news_id') for r in rows]
    require(len(new_ids) == len(set(new_ids)) and set(new_ids) == expected, 'Provide exactly the new articles before the first existing ID; never edit old records')
    total = bundle.get('officialTotal')
    require(type(total) is int and total == len(old) + len(rows), 'Official total differs; stop for reconciliation, do not fabricate or delete records')
    allowed = {'news_id','title','roc_date','date','category','unit','summary','source_url','image_url','site_topics'}
    for r in rows:
        require(set(r) <= allowed, 'Unknown article fields')
        require(all(isinstance(r.get(k), str) and r[k].strip() for k in ['title','roc_date','date','category','unit','summary','source_url']), 'Missing official article fields or summary')
        require(re.fullmatch(r'https://enews\.moenv\.gov\.tw/moenv-news/zh-tw/News/'+r['news_id'], r['source_url']) is not None, 'Article URL and ID must match')
        dt = datetime.strptime(r['date'], '%Y-%m-%d')
        require(r['roc_date'] == f'{dt.year-1911:03d}-{dt.month:02d}-{dt.day:02d}', 'ROC and Gregorian dates differ')
        require(r['date'] >= max(x['date'] for x in old) and r['date'] <= datetime.now().astimezone().date().isoformat(), 'Unexpected historical or future article')
        require(len(r['summary']) <= 500, 'Summary exceeds 500 characters')
        require(not r.get('image_url') or r['image_url'].startswith('https://enews.moenv.gov.tw/'), 'Unofficial image URL')
        require(isinstance(r.get('site_topics', []), list) and all(isinstance(t, str) for t in r.get('site_topics', [])), 'Invalid official topic labels')
    return old, rows


def load_indexer(vault):
    spec = importlib.util.spec_from_file_location('moenv_browser_indexer', vault/'scripts/moenv_news_indexer.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def import_bundle(vault, path, dry_run=False):
    raw = source_bytes(vault)
    bundle = read_json(path)
    old_dicts, rows = validate(bundle, raw)
    report = dict(status='validated', added=len(rows), sourceCount=len(old_dicts)+len(rows), latest=max([r['date'] for r in old_dicts+rows]), mode='browser-incremental')
    if dry_run:
        print(json.dumps(report, ensure_ascii=False)); return
    state = vault/'_local/browser-update'
    state.mkdir(parents=True, exist_ok=True)
    if not rows:
        (state/'last-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        (state/'pending.json').unlink(missing_ok=True)
        print(json.dumps(report, ensure_ascii=False)); return
    m = load_indexer(vault)
    old = m.load_existing_items(vault)
    snapshot = {i.news_id: copy.deepcopy(vars(i)) for i in old}
    for item in old:
        m.normalize_item(item)
        require(vars(item) == snapshot[item.news_id] and m.note_relative_path(item).as_posix() == item.note_path, 'Existing record would change; stop')
    new = [m.NewsItem(**r, views=None) if 'image_url' in r else m.NewsItem(**r, views=None, image_url='') for r in rows]
    stamp = datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%f')
    (state/f'{stamp}-source-before.jsonl').write_bytes(raw)
    (state/f'{stamp}-evidence.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
    require(source_bytes(vault) == raw, 'Source changed during validation')
    # Browser append never removes stale notes or rewrites existing news notes.
    m.remove_stale_markdown = lambda *args, **kwargs: None
    m.write_outputs(vault, old+new, datetime.now().astimezone().isoformat(timespec='seconds'), bundle['officialTotal'],
                    mode='incremental', new_count=len(new), note_ids_to_write={i.news_id for i in new})
    after = m.load_existing_items(vault)
    require(len(after) == len(old)+len(new), 'Post-import count mismatch; do not publish')
    for item in after:
        if item.news_id in snapshot:
            require(vars(item) == snapshot[item.news_id], 'Existing record changed; do not publish')
    report.update(status='imported', oldRecordsUnchanged=len(old))
    (state/'last-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (state/'pending.json').unlink(missing_ok=True)
    print(json.dumps(report, ensure_ascii=False))


def crawler(vault, args):
    result = subprocess.run([sys.executable, '-B', str(vault/'scripts/moenv_news_indexer.py'), '--vault', str(vault), *args], capture_output=True, text=True, encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    print(result.stdout, end=''); print(result.stderr, end='', file=sys.stderr)
    state = vault/'_local/browser-update'
    if result.returncode == 0:
        (state/'pending.json').unlink(missing_ok=True)
        return 0
    failure = result.stdout + result.stderr
    if any(x in args for x in ['--full','--rebuild-indexes','--refresh-summaries']) or not any(t in failure for t in ['No news items found','Failed to fetch','HTTP Error 403','HTTP Error 429','Cloudflare']):
        return result.returncode
    raw = source_bytes(vault)
    state.mkdir(parents=True, exist_ok=True)
    (state/'pending.json').write_text(json.dumps(dict(schemaVersion=1,status='browser_required',listURL=LIST_URL,baseSha256=digest(raw),createdAt=datetime.now().astimezone().isoformat(),sourceCount=len(raw.decode('utf-8-sig').splitlines())), indent=2), encoding='utf-8')
    print('BROWSER_REQUIRED: crawler could not read official news. Codex must follow BROWSER_UPDATE.md; no source records were imported. Exit code 20 is not zero new articles.')
    return BROWSER_REQUIRED


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vault', type=Path, required=True)
    parser.add_argument('--browser-import', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    opts, rest = parser.parse_known_args()
    if opts.browser_import:
        require(not rest, 'Crawler options cannot be combined with browser import')
        import_bundle(opts.vault.resolve(), opts.browser_import, opts.dry_run); return 0
    require(not opts.dry_run, '--dry-run requires --browser-import')
    return crawler(opts.vault.resolve(), rest)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
