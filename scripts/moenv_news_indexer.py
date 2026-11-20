#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import posixpath
import re
import ssl
import subprocess
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlencode
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


BASE_URL = "https://enews.moenv.gov.tw"
LIST_PATH = "/Page/B514A5023133ED27"
NEW_LIST_PATH = "/News/List?key=11&Lang=zh-tw"
SOURCE_NAME = "環境部新聞專區"
OBSIDIAN_VAULT_NAME = "環境部新聞"
OPEN_DATA_NEWS_API_BASE = "https://data.moenv.gov.tw/api/v2/mnews_p_01"
OPEN_DATA_NEWS_API_URL = (
    f"{OPEN_DATA_NEWS_API_BASE}?format=JSON&limit=1000&sort=NewsDate%20desc"
)
NOTE_ROOT = Path("資料") / SOURCE_NAME / "新聞"
NOTE_ROOT_QUERY = NOTE_ROOT.as_posix()
RESEARCH_REPORT_ROOT = Path("03_政策研究") / "研究報告"
RESEARCH_REVIEW_ROOT = Path("99_內部工作區_不公開") / "研究更新佇列"
USER_AGENT = (
    "Mozilla/5.0 (compatible; MoenvObsidianIndexer/1.0; "
    "+https://enews.moenv.gov.tw/)"
)
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Referer": f"{BASE_URL}{NEW_LIST_PATH}",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

ITEM_RE = re.compile(
    r'<li>\s*<a\s+target="_self"\s+href="(?P<href>/page/3b3c62c78849f32f/[^"]+)"'
    r'\s+title="(?P<title>.*?)">(?P<body>.*?)</a>\s*</li>',
    re.I | re.S,
)
NEW_ITEM_RE = re.compile(
    r'<article\b[^>]*class="[^"]*\bnews-card\b[^"]*"[^>]*>\s*'
    r'<a\b[^>]*href="(?P<href>/moenv-news/zh-tw/News/\d+)"[^>]*>.*?</a>'
    r'(?P<body>.*?)</article>',
    re.I | re.S,
)
TOTAL_RE = re.compile(r'(?:id="ctl06_lbTolRecs">\s*|共\s*)([\d,]+)(?:\s*</span>|\s*筆)', re.I)
DATE_RE = re.compile(r'<span\s+class="date">\s*(.*?)\s*</span>', re.I | re.S)
CLASSIFY_RE = re.compile(r'<span\s+class="classify">\s*(.*?)\s*</span>', re.I | re.S)
TITLE_RE = re.compile(r'<h2\s+class="ellipsis-item">\s*(.*?)\s*</h[23]>', re.I | re.S)
SUMMARY_RE = re.compile(r'<p\s+class="ellipsis-item"[^>]*>\s*(.*?)\s*</p>', re.I | re.S)
UNIT_RE = re.compile(r'<div\s+class="gov-group">\s*(.*?)\s*</div>', re.I | re.S)
VIEWS_RE = re.compile(r'<div\s+class="view-wrap">.*?<span>\s*([\d,]+)\s*</span>', re.I | re.S)
IMG_RE = re.compile(r'<img\s+src="([^"]+)"\s+class="print_img"', re.I)
NEW_TITLE_RE = re.compile(r'<h[23]\b[^>]*class="[^"]*\bnews-card__title\b[^"]*"[^>]*>\s*(.*?)\s*</h[23]>', re.I | re.S)
NEW_DATE_RE = re.compile(r'<span\b[^>]*class="[^"]*\bnews-card__date\b[^"]*"[^>]*>\s*(.*?)\s*</span>', re.I | re.S)
NEW_UNIT_RE = re.compile(r'<span\b[^>]*class="[^"]*\bnews-card__dept\b[^"]*"[^>]*>\s*(.*?)\s*</span>', re.I | re.S)
NEW_CATEGORY_RE = re.compile(r'<a\b[^>]*class="[^"]*\bnews-card__badge\b[^"]*"[^>]*data-title="(.*?)"', re.I | re.S)
NEW_IMG_RE = re.compile(r'<img\b[^>]*src="([^"]+)"', re.I)
DETAIL_BODY_RE = re.compile(
    r'<div\s+class="news-info-paragraph">\s*(?P<body>.*?)\s*</div>',
    re.I | re.S,
)
NEW_DETAIL_BODY_RE = re.compile(
    r'<div\b[^>]*class="[^"]*\barticle-content\b[^"]*"[^>]*>\s*'
    r'(?P<body>.*?)\s*</div>\s*<!--\s*/\.article-content\s*-->',
    re.I | re.S,
)
PARAGRAPH_RE = re.compile(r"<p\b[^>]*>\s*(.*?)\s*</p>", re.I | re.S)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*", re.S)
MAJOR_RESEARCH_REVIEW_TERMS = (
    "重大",
    "公告",
    "發布",
    "修正",
    "修法",
    "生效",
    "施行",
    "上路",
    "費率",
    "徵收",
    "裁罰",
    "罰鍰",
    "標準",
    "管制",
    "制度",
    "辦法",
    "草案",
    "預告",
    "核定",
    "計畫",
    "目標",
    "規範",
)


@dataclass(frozen=True)
class KeywordProfile:
    slug: str
    title: str
    group: str
    description: str
    aliases: tuple[str, ...]
    public: bool = True


KEYWORD_PROFILES: tuple[KeywordProfile, ...] = (
    KeywordProfile(
        slug="carbon_fee",
        title="碳費徵收",
        group="氣候與碳定價",
        description="碳費申報、費率、徵收、收費制度與企業因應。",
        aliases=("碳費", "碳費率", "碳費徵收", "碳費申報"),
    ),
    KeywordProfile(
        slug="voluntary_reduction",
        title="自主減量計畫",
        group="氣候與碳定價",
        description="自主減量、指定削減率、減量計畫與優惠費率。",
        aliases=("自主減量", "自主減量計畫", "減量計畫", "指定削減率", "優惠費率"),
    ),
    KeywordProfile(
        slug="carbon_pricing_ets",
        title="碳定價與ETS",
        group="氣候與碳定價",
        description="碳定價、排放交易、碳市場、碳權與國際接軌。",
        aliases=("碳定價", "排放交易", "ETS", "碳交易", "碳市場", "碳權"),
    ),
    KeywordProfile(
        slug="ghg_inventory",
        title="溫室氣體盤查登錄",
        group="氣候與碳定價",
        description="溫室氣體盤查、登錄、排放清冊與範疇三係數。",
        aliases=("溫室氣體", "盤查", "登錄", "排放清冊", "範疇三", "GHG"),
    ),
    KeywordProfile(
        slug="net_zero_transition",
        title="淨零轉型",
        group="氣候與碳定價",
        description="2050 淨零、減碳路徑、綠色轉型與企業競爭力。",
        aliases=("淨零", "2050", "淨零排放", "淨零轉型", "減碳", "低碳"),
    ),
    KeywordProfile(
        slug="climate_adaptation",
        title="氣候變遷與調適",
        group="氣候與碳定價",
        description="氣候變遷、高溫、熱浪、韌性城市與調適政策。",
        aliases=("氣候變遷", "氣候調適", "調適", "高溫", "熱浪", "韌性", "國土綠蔭"),
    ),
    KeywordProfile(
        slug="resource_circulation",
        title="資源循環",
        group="資源循環與廢棄物",
        description="資源循環、資源回收、再利用與循環經濟政策。",
        aliases=("資源循環", "資源回收", "再利用", "循環經濟", "循環標誌", "廢棄物再利用"),
    ),
    KeywordProfile(
        slug="plastic_reduction",
        title="減塑與一次用產品",
        group="資源循環與廢棄物",
        description="減塑、一次用產品、塑膠袋、免洗餐具與循環容器。",
        aliases=("減塑", "一次用", "塑膠袋", "免洗餐具", "循環杯", "袋袋箱傳", "包裝減量"),
    ),
    KeywordProfile(
        slug="waste_crime",
        title="廢棄物與環保犯罪",
        group="資源循環與廢棄物",
        description="廢棄物清理、非法棄置、掩埋、清運與環保犯罪查緝。",
        aliases=("廢棄物", "非法棄置", "非法掩埋", "清運", "環保犯罪", "事業廢棄物", "有害廢棄物"),
    ),
    KeywordProfile(
        slug="air_quality",
        title="空氣品質",
        group="污染防制",
        description="空污、PM2.5、臭氧、空污費、移動污染源與空氣品質管理。",
        aliases=("空氣品質", "空污", "空氣污染", "PM2.5", "細懸浮微粒", "臭氧", "空污費", "移動污染源"),
    ),
    KeywordProfile(
        slug="water_quality",
        title="水質保護",
        group="污染防制",
        description="水污染防治、河川污染、飲用水、放流水與水質監測。",
        aliases=("水質", "水污染", "放流水", "河川污染", "飲用水", "地下水", "污水"),
    ),
    KeywordProfile(
        slug="soil_groundwater",
        title="土壤及地下水",
        group="污染防制",
        description="土壤污染、地下水污染、農地污染與場址整治。",
        aliases=("土壤污染", "地下水污染", "土壤及地下水", "土污", "農地污染", "污染場址"),
    ),
    KeywordProfile(
        slug="eia",
        title="環評制度",
        group="治理與制度",
        description="環境影響評估、開發行為、環評審查與環評監督。",
        aliases=("環評", "環境影響評估", "環評審查", "開發行為", "環評監督"),
    ),
    KeywordProfile(
        slug="chemical_management",
        title="化學物質與毒化物",
        group="污染防制",
        description="毒性化學物質、關注化學物質、毒化災、汞、石綿與化學品管理。",
        aliases=("化學物質", "毒性化學物質", "關注化學物質", "毒化物", "毒化災", "汞", "石綿", "PFAS"),
    ),
    KeywordProfile(
        slug="environmental_education",
        title="環境教育與綠領人才",
        group="社會溝通與人才",
        description="環境教育、環教場所、綠領人才、證照與人才培育。",
        aliases=("環境教育", "環教", "綠領", "人才培育", "環境教育人員", "證照"),
    ),
    KeywordProfile(
        slug="green_consumption",
        title="綠色消費與標章",
        group="社會溝通與人才",
        description="環保標章、綠色採購、綠色消費、環保旅宿與永續生活。",
        aliases=("環保標章", "綠色消費", "綠色採購", "環保旅宿", "淨零綠生活", "友善食力"),
    ),
    KeywordProfile(
        slug="international_cooperation",
        title="國際環境合作",
        group="治理與制度",
        description="國際合作、COP、UNFCCC、巴黎協定、歐盟與跨國交流。",
        aliases=("國際合作", "國際交流", "COP", "UNFCCC", "巴黎協定", "歐盟", "日本", "國際研討會"),
    ),
    KeywordProfile(
        slug="enforcement",
        title="環境執法與稽查",
        group="治理與制度",
        description="稽查、督察、裁罰、罰鍰、違規與檢警環合作。",
        aliases=("稽查", "督察", "裁罰", "罰鍰", "違規", "檢警環", "移送法辦"),
    ),
    KeywordProfile(
        slug="esg_finance",
        title="ESG與永續金融",
        group="治理與制度",
        description="ESG、永續金融、企業永續、綠色金融與投資資源。",
        aliases=("ESG", "永續金融", "企業永續", "綠色金融", "金融資源", "永續長"),
    ),
    KeywordProfile(
        slug="bioenergy",
        title="生質能與再生能源",
        group="資源循環與廢棄物",
        description="沼氣、生質能、綠能、廚餘能源化與廢棄物發電。",
        aliases=("沼氣", "生質能", "綠能", "再生能源", "發電", "廚餘", "能源化"),
    ),
)


@dataclass
class NewsItem:
    news_id: str
    title: str
    roc_date: str
    date: str
    category: str
    unit: str
    views: int | None
    summary: str
    source_url: str
    image_url: str
    site_topics: list[str] = field(default_factory=list)
    note_path: str = ""
    body: str = ""
    attach_url: str = ""
    ai_tags: list[str] = field(default_factory=list)
    ai_policy_keywords: list[str] = field(default_factory=list)
    source_url_status: str = ""


@dataclass
class KeywordMatch:
    profile: KeywordProfile
    aliases: list[str]
    score: int


@dataclass
class KeywordStats:
    profile: KeywordProfile
    items: list[NewsItem]
    years: dict[str, int]


@dataclass
class ResearchReport:
    path: str
    topic: str
    keywords: list[str]
    aliases: list[str]
    status: str
    coverage_end: str


@dataclass
class ResearchReviewEntry:
    level: str
    update_action: str
    report_topic: str
    report_path: str
    coverage_end: str
    news_id: str
    news_date: str
    news_title: str
    category: str
    unit: str
    note_path: str
    source_url: str
    matched_terms: list[str]
    matched_keywords: list[str]
    reasons: list[str]


def fetch_url(url: str, retries: int = 3, timeout: int = 30, use_curl: bool = False) -> str:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if use_curl:
                return fetch_url_with_curl(url, timeout)
            return fetch_url_with_urllib(url, timeout)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if use_curl:
                try:
                    return fetch_url_with_urllib(url, timeout)
                except Exception as urllib_exc:  # noqa: BLE001
                    last_error = urllib_exc
            elif isinstance(exc, URLError):
                try:
                    return fetch_url_with_curl(url, timeout)
                except Exception as curl_exc:  # noqa: BLE001
                    last_error = curl_exc
            if attempt < retries:
                time.sleep(min(2 * attempt, 8))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error


def fetch_url_with_urllib(url: str, timeout: int) -> str:
    request = Request(url, headers=BROWSER_HEADERS)
    context = ssl.create_default_context()
    with urlopen(request, timeout=timeout, context=context) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def fetch_url_with_curl(url: str, timeout: int) -> str:
    executable = "curl.exe" if sys.platform.startswith("win") else "curl"
    result = subprocess.run(
        [executable, "-L", "-sS", "--max-time", str(timeout), url],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def clean_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n\s+", "\n", value)
    return value.strip()


def clean_html_to_markdown(value: str) -> str:
    value = re.sub(r"<script\b.*?</script>", "", value, flags=re.I | re.S)
    value = re.sub(r"<style\b.*?</style>", "", value, flags=re.I | re.S)
    value = re.sub(r"</p\s*>", "\n\n", value, flags=re.I)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<strong>(.*?)</strong>", r"**\1**", value, flags=re.I | re.S)
    value = re.sub(r"<b>(.*?)</b>", r"**\1**", value, flags=re.I | re.S)
    value = re.sub(r"<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"[\2](\1)", value, flags=re.I | re.S)
    value = clean_text(value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value


def first_match(pattern: re.Pattern[str], value: str) -> str:
    match = pattern.search(value)
    return clean_text(match.group(1)) if match else ""


def roc_to_iso(roc_date: str) -> str:
    match = re.match(r"^\s*(\d{2,3})-(\d{2})-(\d{2})\s*$", roc_date)
    if not match:
        return ""
    year = int(match.group(1)) + 1911
    return f"{year:04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def parse_int(value: str) -> int | None:
    value = value.replace(",", "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_total(html: str) -> int | None:
    match = TOTAL_RE.search(html)
    return parse_int(match.group(1)) if match else None


def parse_list_page(html: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    for match in ITEM_RE.finditer(html):
        href = unescape(match.group("href"))
        body = match.group("body")
        source_url = urljoin(BASE_URL, href)
        news_id = source_url.rstrip("/").split("/")[-1]
        title = first_match(TITLE_RE, body) or clean_text(match.group("title"))
        roc_date = first_match(DATE_RE, body)
        item = NewsItem(
            news_id=news_id,
            title=title,
            roc_date=roc_date,
            date=roc_to_iso(roc_date),
            category=first_match(CLASSIFY_RE, body),
            unit=first_match(UNIT_RE, body).strip("[]"),
            views=parse_int(first_match(VIEWS_RE, body)),
            summary=first_match(SUMMARY_RE, body),
            source_url=source_url,
            image_url=urljoin(BASE_URL, first_match(IMG_RE, body)),
        )
        items.append(item)
    if items:
        return items

    for match in NEW_ITEM_RE.finditer(html):
        href = unescape(match.group("href"))
        body = match.group("body")
        source_url = urljoin(BASE_URL, href)
        news_id = source_url.rstrip("/").split("/")[-1]
        roc_date = first_match(NEW_DATE_RE, body)
        site_topics = extract_new_site_topics(body)
        item = NewsItem(
            news_id=news_id,
            title=first_match(NEW_TITLE_RE, body),
            roc_date=roc_date,
            date=roc_to_iso(roc_date),
            category=site_topics[0] if site_topics else "未標示",
            unit=first_match(NEW_UNIT_RE, body) or "未標示",
            views=None,
            summary="",
            source_url=source_url,
            image_url=urljoin(BASE_URL, first_match(NEW_IMG_RE, body)),
            site_topics=site_topics,
        )
        items.append(item)
    return items


def is_new_list_page(html: str) -> bool:
    return not bool(ITEM_RE.search(html)) and bool(NEW_ITEM_RE.search(html))


def extract_new_site_topics(body: str) -> list[str]:
    topics: list[str] = []
    for match in NEW_CATEGORY_RE.finditer(body):
        topic = clean_text(unescape(match.group(1)))
        if topic and topic not in topics:
            topics.append(topic)
    return topics


def news_identity_key(date: str, title: str) -> tuple[str, str]:
    normalized_title = unicodedata.normalize("NFKC", clean_text(title)).casefold()
    return date[:10], normalized_title


def news_date_unit_key(date: str, unit: str) -> tuple[str, str]:
    normalized_unit = unicodedata.normalize("NFKC", clean_text(unit)).casefold()
    return date[:10], f"\0unit:{normalized_unit}"


def item_identity_key(item: NewsItem) -> tuple[str, str]:
    return news_identity_key(item.date, item.title)


def merge_list_metadata(existing: NewsItem, current: NewsItem) -> bool:
    """Apply changed list metadata and report whether the stored item changed."""
    changed = any(
        (
            existing.category != current.category,
            existing.unit != current.unit,
            existing.source_url != current.source_url,
            existing.image_url != current.image_url,
            existing.site_topics != current.site_topics,
        )
    )
    existing.category = current.category
    existing.unit = current.unit
    existing.source_url = current.source_url
    existing.image_url = current.image_url
    existing.site_topics = current.site_topics
    return changed


def reconcile_full_crawl_items(crawled_items: list[NewsItem], existing_items: list[NewsItem]) -> list[NewsItem]:
    """Keep previously fetched detail fields when the list API omits them."""
    existing_by_id = {item.news_id: item for item in existing_items}
    existing_by_identity = {item_identity_key(item): item for item in existing_items}
    for item in crawled_items:
        existing = existing_by_id.get(item.news_id) or existing_by_identity.get(item_identity_key(item))
        if not existing:
            continue
        if not item.summary:
            item.summary = existing.summary
        if not item.body:
            item.body = existing.body
    return crawled_items


def parse_detail_body(html: str) -> str:
    match = DETAIL_BODY_RE.search(html) or NEW_DETAIL_BODY_RE.search(html)
    if not match:
        return ""
    return clean_html_to_markdown(match.group("body"))


def truncate_text(value: str, max_chars: int) -> str:
    value = clean_text(value)
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "..."


def parse_detail_summary(html: str, max_chars: int = 500) -> str:
    match = DETAIL_BODY_RE.search(html) or NEW_DETAIL_BODY_RE.search(html)
    if not match:
        return ""
    body = match.group("body")
    for paragraph_match in PARAGRAPH_RE.finditer(body):
        paragraph = clean_html_to_markdown(paragraph_match.group(1))
        if paragraph:
            return truncate_text(paragraph, max_chars)
    return truncate_text(clean_html_to_markdown(body).split("\n\n", 1)[0], max_chars)


def parse_open_data_summary_map(payload: str, max_chars: int = 500) -> dict[tuple[str, str], str]:
    records = json.loads(payload)
    if not isinstance(records, list):
        raise ValueError("MOENV open-data news response is not a list.")
    summaries: dict[tuple[str, str], str] = {}
    candidates: list[tuple[tuple[str, str], tuple[str, str], str]] = []
    unit_key_counts: dict[tuple[str, str], int] = {}
    for record in records:
        if not isinstance(record, dict) or str(record.get("deletemark", "0")) == "1":
            continue
        title = str(record.get("newstitle", ""))
        date = str(record.get("newsdate", ""))[:10]
        content = str(record.get("newscontent", ""))
        if not title or not date or not content:
            continue
        summary = ""
        for paragraph_match in PARAGRAPH_RE.finditer(content):
            paragraph = clean_html_to_markdown(paragraph_match.group(1))
            if paragraph:
                summary = truncate_text(paragraph, max_chars)
                break
        if not summary:
            summary = truncate_text(clean_html_to_markdown(content).split("\n\n", 1)[0], max_chars)
        if summary:
            title_key = news_identity_key(date, title)
            unit_key = news_date_unit_key(date, str(record.get("newssource", "")))
            candidates.append((title_key, unit_key, summary))
            unit_key_counts[unit_key] = unit_key_counts.get(unit_key, 0) + 1
    for title_key, unit_key, summary in candidates:
        summaries[title_key] = summary
        if unit_key_counts[unit_key] == 1:
            summaries[unit_key] = summary
    return summaries


def summary_for_item(
    item: NewsItem,
    summaries: dict[tuple[str, str], str],
) -> str:
    return summaries.get(item_identity_key(item), "") or summaries.get(
        news_date_unit_key(item.date, item.unit),
        "",
    )


def build_open_data_news_api_url(api_key: str | None = None) -> str:
    override = os.environ.get("MOENV_OPEN_DATA_NEWS_API_URL", "").strip()
    if override:
        return override
    key = (api_key if api_key is not None else os.environ.get("MOENV_API_KEY", "")).strip()
    params = {
        "format": "JSON",
        "limit": "1000",
        "sort": "NewsDate desc",
    }
    if key:
        params["api_key"] = key
    return f"{OPEN_DATA_NEWS_API_BASE}?{urlencode(params)}"


def fetch_open_data_summary_map(args: argparse.Namespace) -> dict[tuple[str, str], str]:
    url = build_open_data_news_api_url()
    payload = fetch_url(
        url,
        retries=args.retries,
        timeout=args.timeout,
        use_curl=args.use_curl,
    )
    return parse_open_data_summary_map(payload, args.summary_chars)


def item_from_mapping(data: dict[str, object]) -> NewsItem:
    fields = NewsItem.__dataclass_fields__
    values: dict[str, object] = {}
    for name in fields:
        value = data.get(name, "")
        if value is None:
            value = ""
        values[name] = value

    for list_field in ("site_topics", "ai_tags", "ai_policy_keywords"):
        raw_list = values.get(list_field)
        if isinstance(raw_list, str):
            values[list_field] = [entry.strip() for entry in raw_list.split(";") if entry.strip()]
        elif isinstance(raw_list, list):
            values[list_field] = [str(entry).strip() for entry in raw_list if str(entry).strip()]
        else:
            values[list_field] = []

    views = values.get("views")
    if isinstance(views, str):
        values["views"] = parse_int(views) if views.strip().lower() not in {"", "none", "null"} else None
    elif views is not None:
        try:
            values["views"] = int(views)
        except (TypeError, ValueError):
            values["views"] = None

    item = NewsItem(**values)  # type: ignore[arg-type]
    normalize_item(item)
    return item


def sanitize_filename(value: str, max_length: int = 60) -> str:
    value = unicodedata.normalize("NFKC", clean_text(value))
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    if len(value) > max_length:
        value = value[:max_length].rstrip(" .")
    return value or "untitled"


def yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def slug_for_tag(value: str) -> str:
    value = unicodedata.normalize("NFKC", clean_text(value))
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[#,\\[\\]{}]", "", value)
    return value or "未分類"


def remove_stale_markdown(root: Path, desired_paths: set[Path]) -> None:
    if not root.exists():
        return
    desired = {path.resolve() for path in desired_paths}
    for path in root.rglob("*.md"):
        resolved = path.resolve()
        if resolved not in desired:
            try:
                path.unlink()
            except PermissionError:
                try:
                    os.chmod(path, 0o666)
                    path.unlink()
                except OSError as exc:
                    print(f"Warning: could not remove stale generated note {path}: {exc}", file=sys.stderr)
            except OSError as exc:
                print(f"Warning: could not remove stale generated note {path}: {exc}", file=sys.stderr)


def note_relative_path(item: NewsItem) -> Path:
    year = item.date[:4] if item.date else "unknown"
    month = item.date[5:7] if item.date else "unknown"
    short_id = item.news_id.split("-")[0]
    filename = f"{item.date or item.roc_date}_{short_id}_{sanitize_filename(item.title)}.md"
    return NOTE_ROOT / year / month / filename


def markdown_link(from_path: str | Path, target_path: str | Path, title: str) -> str:
    current_dir = Path(from_path).parent.as_posix()
    if current_dir == ".":
        current_dir = "."
    target = Path(target_path).as_posix()
    href = posixpath.relpath(target, start=current_dir)
    label = title.replace("[", "［").replace("]", "］")
    href = href.replace(">", "%3E")
    return f"[{label}](<{href}>)"


def obsidian_short_link(target_path: str | Path, title: str) -> str:
    target = Path(target_path).stem
    target = target.replace("|", "｜").replace("[", "［").replace("]", "］")
    label = title.replace("|", "｜").replace("[", "［").replace("]", "］")
    return f"[[{target}|{label}]]"


def obsidian_uri_link(target_path: str | Path, title: str) -> str:
    target = Path(target_path).with_suffix("").as_posix()
    href = (
        "obsidian://open?"
        f"vault={quote(OBSIDIAN_VAULT_NAME, safe='')}"
        f"&file={quote(target, safe='')}"
    )
    label = title.replace("[", "［").replace("]", "］")
    return f"[{label}](<{href}>)"


def obsidian_wiki_link(target_path: str | Path, title: str) -> str:
    target = Path(target_path).with_suffix("").as_posix()
    target = target.replace("|", "｜").replace("[", "［").replace("]", "］")
    label = title.replace("|", "｜").replace("[", "［").replace("]", "］")
    return f"[[{target}|{label}]]"


def item_sort_key(item: NewsItem) -> tuple[str, str]:
    return (item.date or "0000-00-00", item.news_id)


def item_year(item: NewsItem) -> str:
    return item.date[:4] if item.date else "unknown"


def item_search_text(item: NewsItem) -> str:
    parts = [item.title, item.category, item.unit, item.summary, item.body]
    return clean_text(" ".join(part for part in parts if part))


def count_alias(text: str, alias: str) -> int:
    alias = alias.strip()
    if not alias:
        return 0
    if re.search(r"[A-Za-z0-9]", alias):
        return text.lower().count(alias.lower())
    return text.count(alias)


def keyword_matches_for_item(item: NewsItem) -> list[KeywordMatch]:
    text = item_search_text(item)
    matches: list[KeywordMatch] = []
    ai_titles = {title.strip() for title in item.ai_policy_keywords if title and title.strip()}
    for profile in KEYWORD_PROFILES:
        aliases: list[str] = []
        score = 0
        for alias in profile.aliases:
            count = count_alias(text, alias)
            if count:
                aliases.append(alias)
                score += count
        if aliases:
            matches.append(KeywordMatch(profile=profile, aliases=aliases, score=score))
        elif profile.title in ai_titles:
            matches.append(KeywordMatch(profile=profile, aliases=["[AI]"], score=1))
    return matches


def build_keyword_matches(items: list[NewsItem]) -> dict[str, list[KeywordMatch]]:
    return {item.news_id: keyword_matches_for_item(item) for item in items}


def strip_yaml_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def parse_frontmatter(text: str) -> dict[str, object]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data: dict[str, object] = {}
    current_key = ""
    for raw_line in match.group("body").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if current_key:
                values = data.setdefault(current_key, [])
                if isinstance(values, list):
                    values.append(strip_yaml_value(line.split("- ", 1)[1]))
            continue
        if ":" not in line:
            current_key = ""
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        value = strip_yaml_value(value)
        data[current_key] = value if value else []
    return data


def frontmatter_list(data: dict[str, object], key: str) -> list[str]:
    value = data.get(key, [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def load_research_reports(vault: Path) -> list[ResearchReport]:
    root = vault / RESEARCH_REPORT_ROOT
    if not root.exists():
        return []
    reports: list[ResearchReport] = []
    for path in sorted(root.glob("*.md")):
        try:
            data = parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"Warning: could not read research report {path}: {exc}", file=sys.stderr)
            continue
        if data.get("type") != "policy-research":
            continue
        status = str(data.get("status", "")).strip()
        if status in {"archived", "retired"}:
            continue
        try:
            rel_path = path.relative_to(vault).as_posix()
        except ValueError:
            rel_path = path.as_posix()
        topic = str(data.get("topic", "")).strip() or path.stem
        reports.append(
            ResearchReport(
                path=rel_path,
                topic=topic,
                keywords=frontmatter_list(data, "keywords"),
                aliases=frontmatter_list(data, "aliases"),
                status=status,
                coverage_end=str(data.get("coverage_end", "")).strip(),
            )
        )
    return reports


def unique_preserving_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = value.strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def research_report_terms(report: ResearchReport) -> list[str]:
    terms: list[str] = [report.topic, *report.keywords, *report.aliases]
    profile_by_slug = {profile.slug: profile for profile in KEYWORD_PROFILES}
    for keyword in report.keywords:
        profile = profile_by_slug.get(keyword)
        if profile:
            terms.extend([profile.slug, profile.title, *profile.aliases])
    return unique_preserving_order(terms)


def research_match_for_item(
    report: ResearchReport,
    item: NewsItem,
    keyword_matches: list[KeywordMatch],
) -> ResearchReviewEntry | None:
    text = item_search_text(item)
    item_slugs = {match.profile.slug for match in keyword_matches}
    item_keyword_titles = {match.profile.title for match in keyword_matches}
    item_aliases = {alias for match in keyword_matches for alias in match.aliases}

    matched_terms: list[str] = []
    for term in research_report_terms(report):
        if term in item_slugs or term in item_keyword_titles or term in item_aliases or count_alias(text, term):
            matched_terms.append(term)
    matched_terms = unique_preserving_order(matched_terms)
    if not matched_terms:
        return None

    major_terms = [term for term in MAJOR_RESEARCH_REVIEW_TERMS if count_alias(text, term)]
    level = "A" if major_terms else "B"
    reasons = [
        "命中研究關鍵字：" + "、".join(matched_terms[:8]),
    ]
    if major_terms:
        reasons.append("重大詞：" + "、".join(major_terms[:8]))

    return ResearchReviewEntry(
        level=level,
        update_action="大改版或當日小修" if level == "A" else "週檢補充證據",
        report_topic=report.topic,
        report_path=report.path,
        coverage_end=report.coverage_end,
        news_id=item.news_id,
        news_date=item.date or item.roc_date,
        news_title=item.title,
        category=item.category or "未分類",
        unit=item.unit or "未標示",
        note_path=item.note_path,
        source_url=item.source_url,
        matched_terms=matched_terms,
        matched_keywords=sorted(item_slugs),
        reasons=reasons,
    )


def build_research_review_entries(vault: Path, new_items: list[NewsItem]) -> list[ResearchReviewEntry]:
    reports = load_research_reports(vault)
    if not reports or not new_items:
        return []
    matches_by_id = build_keyword_matches(new_items)
    entries: list[ResearchReviewEntry] = []
    for item in sorted(new_items, key=item_sort_key, reverse=True):
        for report in reports:
            entry = research_match_for_item(report, item, matches_by_id.get(item.news_id, []))
            if entry:
                entries.append(entry)
    return sorted(entries, key=lambda entry: (0 if entry.level == "A" else 1, entry.report_topic, entry.news_date), reverse=False)


def build_keyword_stats(
    items: list[NewsItem],
    matches_by_id: dict[str, list[KeywordMatch]],
) -> dict[str, KeywordStats]:
    stats = {
        profile.slug: KeywordStats(profile=profile, items=[], years={})
        for profile in KEYWORD_PROFILES
    }
    for item in items:
        year = item_year(item)
        for match in matches_by_id.get(item.news_id, []):
            stat = stats[match.profile.slug]
            stat.items.append(item)
            stat.years[year] = stat.years.get(year, 0) + 1
    return stats


def build_keyword_cooccurrence(
    matches_by_id: dict[str, list[KeywordMatch]],
) -> dict[str, dict[str, int]]:
    cooccurrence: dict[str, dict[str, int]] = {profile.slug: {} for profile in KEYWORD_PROFILES}
    for matches in matches_by_id.values():
        slugs = sorted({match.profile.slug for match in matches})
        for index, left in enumerate(slugs):
            for right in slugs[index + 1 :]:
                cooccurrence[left][right] = cooccurrence[left].get(right, 0) + 1
                cooccurrence[right][left] = cooccurrence[right].get(left, 0) + 1
    return cooccurrence


def keyword_rank(stats: dict[str, KeywordStats]) -> list[KeywordStats]:
    return sorted(stats.values(), key=lambda stat: (-len(stat.items), stat.profile.group, stat.profile.title))


def keyword_count_since(stat: KeywordStats, first_year: int) -> int:
    total = 0
    for year, count in stat.years.items():
        if year.isdigit() and int(year) >= first_year:
            total += count
    return total


def date_range(items: Iterable[NewsItem]) -> tuple[str, str]:
    dates = sorted(item.date for item in items if item.date)
    if not dates:
        return "", ""
    return dates[0], dates[-1]


def year_sequence(items: Iterable[NewsItem]) -> list[str]:
    years = sorted({item_year(item) for item in items if item_year(item).isdigit()})
    return years


def profile_by_slug(slug: str) -> KeywordProfile:
    for profile in KEYWORD_PROFILES:
        if profile.slug == slug:
            return profile
    raise KeyError(slug)


def render_year_sparkline(years: dict[str, int], max_years: int = 8) -> str:
    pairs = sorted((year, count) for year, count in years.items() if year.isdigit())
    if max_years:
        pairs = pairs[-max_years:]
    return "｜".join(f"{year}:{count}" for year, count in pairs) or "無"


def render_note(item: NewsItem, keyword_matches: list[KeywordMatch] | None = None) -> str:
    keyword_matches = keyword_matches if keyword_matches is not None else keyword_matches_for_item(item)
    tags = [
        "moenv/news",
        f"moenv/category/{slug_for_tag(item.category)}",
        f"moenv/unit/{slug_for_tag(item.unit)}",
    ]
    tags.extend(f"moenv/site-topic/{slug_for_tag(topic)}" for topic in item.site_topics)
    tags.extend(f"moenv/topic/{match.profile.slug}" for match in keyword_matches)
    frontmatter = [
        "---",
        f"title: {yaml_scalar(item.title)}",
        f"source: {yaml_scalar(SOURCE_NAME)}",
        f"source_url: {yaml_scalar(item.source_url)}",
        f"news_id: {yaml_scalar(item.news_id)}",
        f"roc_date: {yaml_scalar(item.roc_date)}",
        f"date: {item.date or 'null'}",
        f"category: {yaml_scalar(item.category)}",
        f"unit: {yaml_scalar(item.unit)}",
        f"views: {item.views if item.views is not None else 'null'}",
        f"image_url: {yaml_scalar(item.image_url)}",
        "site_topics:",
        "tags:",
    ]
    if item.site_topics:
        frontmatter.extend(f"  - {yaml_scalar(topic)}" for topic in item.site_topics)
    else:
        frontmatter[-1] = "site_topics: []"
    frontmatter.extend([f"  - {yaml_scalar(tag)}" for tag in tags])
    if keyword_matches:
        frontmatter.append("policy_keywords:")
        frontmatter.extend(f"  - {yaml_scalar(match.profile.title)}" for match in keyword_matches)
    else:
        frontmatter.append("policy_keywords: []")
    if item.ai_tags:
        frontmatter.append("ai_tags:")
        frontmatter.extend(f"  - {yaml_scalar(tag)}" for tag in item.ai_tags)
    frontmatter.append("---")

    lines = [
        *frontmatter,
        "",
        f"# {item.title}",
        "",
        f"- 發布日期：{item.date or item.roc_date}（民國 {item.roc_date}）",
        f"- 類別：{item.category or '未分類'}",
        f"- 發布單位：{item.unit or '未標示'}",
        (
            f"- 原始連結：[{SOURCE_NAME}]({item.source_url})"
            if item.source_url
            else "- 原始連結：官網單篇連結同步中（來源：環境部 MNEWS_P_01）"
        ),
    ]
    if item.attach_url:
        lines.append(f"- 附件：{item.attach_url}")
    if item.views is not None:
        lines.append(f"- 點擊數：{item.views}")
    if item.image_url:
        lines.append(f"- 圖片：{item.image_url}")
    graph_links = [
        obsidian_wiki_link(Path("索引") / "分類" / f"{sanitize_filename(item.category or '未分類')}.md", item.category or "未分類"),
        obsidian_wiki_link(Path("索引") / "發布單位" / f"{sanitize_filename(item.unit or '未標示')}.md", item.unit or "未標示"),
        obsidian_wiki_link(Path("索引") / "年份" / f"{item_year(item)}.md", item_year(item)),
    ]
    graph_links.extend(obsidian_wiki_link(policy_topic_path(match.profile), match.profile.title) for match in keyword_matches)
    if graph_links:
        lines.extend(["", "## 圖譜關聯", "", "、".join(dict.fromkeys(graph_links))])
    if item.summary:
        lines.extend(["", "## 摘要", "", item.summary])
    if item.body:
        lines.extend(["", "## 內文", "", item.body])
    lines.append("")
    return "\n".join(lines)


def render_master_index(
    items: list[NewsItem],
    generated_at: str,
    total_from_site: int | None,
    keyword_stats: dict[str, KeywordStats],
) -> str:
    current_path = Path("環境部新聞索引.md")
    by_category = count_by(items, lambda item: item.category or "未分類")
    by_unit = count_by(items, lambda item: item.unit or "未標示")
    recent = sorted(items, key=item_sort_key, reverse=True)[:30]
    first_date, last_date = date_range(items)
    ranked_keywords = keyword_rank(keyword_stats)
    latest_year = max((int(year) for year in year_sequence(items)), default=0)
    recent_from_year = max(latest_year - 2, 0)
    recent_keywords = sorted(
        ranked_keywords,
        key=lambda stat: (-keyword_count_since(stat, recent_from_year), stat.profile.title),
    )
    lines = [
        "# 環境部新聞索引",
        "",
        f"- 來源：[{SOURCE_NAME}]({BASE_URL}{LIST_PATH})",
        f"- 產生時間：{generated_at}",
        f"- 索引筆數：{len(items):,}",
    ]
    if first_date and last_date:
        lines.append(f"- 收錄期間：{first_date} 至 {last_date}")
    if total_from_site is not None:
        lines.append(f"- 網站顯示總筆數：{total_from_site:,}")
    lines.extend(
        [
            "",
            "## 快速入口",
            "",
            f"- {obsidian_uri_link(Path('00_公開入口') / '首頁.md', '公開首頁')}",
            f"- {obsidian_uri_link(Path('01_政策議題') / '政策議題總覽.md', '政策議題總覽')}",
            f"- {obsidian_uri_link(Path('02_環境部新聞_可公開') / '最近新聞.md', '可公開新聞清單')}",
            f"- {obsidian_uri_link(Path('02_環境部新聞_可公開') / '最近30天政策趨勢.md', '最近30天政策趨勢')}",
            f"- {obsidian_uri_link(Path('索引') / '趨勢.md', '趨勢總覽')}",
            f"- {obsidian_uri_link(Path('索引') / '分類.md', '分類索引')}",
            f"- {obsidian_uri_link(Path('索引') / '發布單位.md', '發布單位索引')}",
            f"- {obsidian_uri_link(Path('索引') / '年份.md', '年份索引')}",
            f"- {markdown_link(current_path, Path('資料') / 'moenv_news_index.csv', 'CSV 索引資料')}",
            f"- {markdown_link(current_path, Path('資料') / 'moenv_news_index.jsonl', 'JSONL 索引資料')}",
            f"- {markdown_link(current_path, Path('資料') / 'moenv_keyword_database.json', '關鍵字資料庫')}",
            "",
            "## 政策趨勢快速看",
            "",
            "| 關鍵字 | 總筆數 | 近三年 | 近年走勢 |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for stat in ranked_keywords[:12]:
        target = Path("索引") / "關鍵字" / f"{sanitize_filename(stat.profile.title)}.md"
        recent_count = keyword_count_since(stat, recent_from_year) if recent_from_year else len(stat.items)
        lines.append(
            f"| {obsidian_uri_link(target, stat.profile.title)} | {len(stat.items):,} | "
            f"{recent_count:,} | {render_year_sparkline(stat.years)} |"
        )
    lines.extend(
        [
            "",
            f"## 近三年升溫議題（{recent_from_year}-{latest_year}）",
            "",
        ]
    )
    for stat in recent_keywords[:10]:
        recent_count = keyword_count_since(stat, recent_from_year) if recent_from_year else len(stat.items)
        target = Path("索引") / "關鍵字" / f"{sanitize_filename(stat.profile.title)}.md"
        lines.append(f"- {obsidian_uri_link(target, stat.profile.title)}：{recent_count:,}")
    lines.extend(
        [
            "",
            "## 最近新聞",
            "",
        ]
    )
    for item in recent:
        lines.append(
            f"- {item.date or item.roc_date}｜{item.category or '未分類'}｜"
            f"{obsidian_uri_link(item.note_path, item.title)}"
        )
    lines.extend(
        [
            "",
            "## 類別排行",
            "",
        ]
    )
    for name, count in by_category[:20]:
        target = Path("索引") / "分類" / f"{sanitize_filename(name)}.md"
        lines.append(f"- {obsidian_uri_link(target, name)}：{count:,}")
    lines.extend(["", "## 發布單位排行", ""])
    for name, count in by_unit[:20]:
        target = Path("索引") / "發布單位" / f"{sanitize_filename(name)}.md"
        lines.append(f"- {obsidian_uri_link(target, name)}：{count:,}")
    lines.append("")
    return "\n".join(lines)


def count_by(items: Iterable[NewsItem], key_func) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for item in items:
        key = key_func(item)
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))


def render_group_index(title: str, current_path: Path, group_dir: str, groups: list[tuple[str, list[NewsItem]]]) -> str:
    lines = [f"# {title}", ""]
    for name, group_items in groups:
        target = Path("索引") / group_dir / f"{sanitize_filename(name)}.md"
        lines.append(f"- {obsidian_uri_link(target, name)}：{len(group_items):,}")
    lines.append("")
    return "\n".join(lines)


def render_group_page(title: str, current_path: Path, items: list[NewsItem]) -> str:
    lines = [f"共 {len(items):,} 筆。", ""]
    for item in sorted(items, key=item_sort_key, reverse=True):
        lines.append(
            f"- {item.date or item.roc_date}｜{item.category or '未分類'}｜"
            f"{item.unit or '未標示'}｜{obsidian_uri_link(item.note_path, item.title)}"
        )
    lines.append("")
    return "\n".join(lines)


def group_items(items: list[NewsItem], key_func) -> list[tuple[str, list[NewsItem]]]:
    groups: dict[str, list[NewsItem]] = {}
    for item in items:
        key = key_func(item)
        groups.setdefault(key, []).append(item)
    return sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0]))


def keyword_page_path(profile: KeywordProfile) -> Path:
    return Path("索引") / "關鍵字" / f"{sanitize_filename(profile.title)}.md"


def policy_topic_path(profile: KeywordProfile) -> Path:
    return Path("01_政策議題") / f"{sanitize_filename(profile.title)}.md"


def public_news_path(name: str) -> Path:
    return Path("02_環境部新聞_可公開") / f"{sanitize_filename(name)}.md"


def match_for_item(
    matches_by_id: dict[str, list[KeywordMatch]],
    item: NewsItem,
    slug: str,
) -> KeywordMatch | None:
    for match in matches_by_id.get(item.news_id, []):
        if match.profile.slug == slug:
            return match
    return None


def render_related_keywords(
    slug: str,
    cooccurrence: dict[str, dict[str, int]],
    limit: int = 8,
) -> list[str]:
    pairs = sorted(
        cooccurrence.get(slug, {}).items(),
        key=lambda pair: (-pair[1], profile_by_slug(pair[0]).title),
    )
    lines: list[str] = []
    for related_slug, count in pairs[:limit]:
        profile = profile_by_slug(related_slug)
        lines.append(f"- {obsidian_wiki_link(policy_topic_path(profile), profile.title)}：共同出現 {count:,} 筆")
    return lines or ["- 暫無明顯共現議題"]


def render_keyword_index(
    stats: dict[str, KeywordStats],
    generated_at: str,
) -> str:
    ranked = keyword_rank(stats)
    by_group: dict[str, list[KeywordStats]] = {}
    for stat in ranked:
        by_group.setdefault(stat.profile.group, []).append(stat)

    lines = [
        "# 關鍵字索引",
        "",
        f"- 產生時間：{generated_at}",
        f"- 關鍵字組數：{len(KEYWORD_PROFILES):,}",
        "",
        "## 總排行",
        "",
        "| 關鍵字 | 群組 | 筆數 | 近年走勢 |",
        "| --- | --- | ---: | --- |",
    ]
    for stat in ranked:
        lines.append(
            f"| {obsidian_uri_link(keyword_page_path(stat.profile), stat.profile.title)} | "
            f"{stat.profile.group} | {len(stat.items):,} | {render_year_sparkline(stat.years)} |"
        )

    for group in sorted(by_group):
        lines.extend(["", f"## {group}", ""])
        for stat in by_group[group]:
            lines.append(f"- {obsidian_uri_link(keyword_page_path(stat.profile), stat.profile.title)}：{len(stat.items):,}")
    lines.append("")
    return "\n".join(lines)


def render_keyword_page(
    stat: KeywordStats,
    cooccurrence: dict[str, dict[str, int]],
    matches_by_id: dict[str, list[KeywordMatch]],
    public_variant: bool = False,
) -> str:
    profile = stat.profile
    items = sorted(stat.items, key=item_sort_key, reverse=True)
    first_date, last_date = date_range(items)
    title = profile.title
    lines = [
        f"# {title}",
        "",
        f"- 議題群組：{profile.group}",
        f"- 總筆數：{len(items):,}",
        f"- 收錄期間：{first_date or '無'} 至 {last_date or '無'}",
        f"- 詞彙：{', '.join(profile.aliases)}",
        "",
        profile.description,
        "",
        "## 年度趨勢",
        "",
        "| 年份 | 筆數 |",
        "| --- | ---: |",
    ]
    for year, count in sorted(stat.years.items()):
        lines.append(f"| {year} | {count:,} |")

    peak_years = sorted(stat.years.items(), key=lambda pair: (-pair[1], pair[0]))[:8]
    lines.extend(["", "## 高峰年份", ""])
    for year, count in peak_years:
        lines.append(f"- {year}：{count:,}")

    lines.extend(["", "## 關聯議題", ""])
    lines.extend(render_related_keywords(profile.slug, cooccurrence))

    lines.extend(["", "## 最近新聞", ""])
    recent_limit = 80 if public_variant else 160
    for item in items[:recent_limit]:
        match = match_for_item(matches_by_id, item, profile.slug)
        aliases = f"｜命中：{'、'.join(match.aliases)}" if match else ""
        lines.append(
            f"- {item.date or item.roc_date}｜{item.category or '未分類'}｜"
            f"{obsidian_uri_link(item.note_path, item.title)}{aliases}"
        )
    if len(items) > recent_limit:
        lines.append(f"- 其餘 {len(items) - recent_limit:,} 筆請用 Obsidian 全域搜尋或資料檔查詢。")
    lines.append("")
    return "\n".join(lines)


def render_trend_index(
    items: list[NewsItem],
    stats: dict[str, KeywordStats],
    generated_at: str,
) -> str:
    years = year_sequence(items)
    display_years = years[-10:]
    ranked = keyword_rank(stats)[:15]
    by_year = count_by(items, item_year)
    lines = [
        "# 趨勢總覽",
        "",
        f"- 產生時間：{generated_at}",
        f"- 收錄新聞：{len(items):,}",
        "",
        "## 年度新聞量",
        "",
        "| 年份 | 新聞筆數 |",
        "| --- | ---: |",
    ]
    for year, count in sorted(by_year):
        lines.append(f"| {year} | {count:,} |")

    lines.extend(["", "## 近十年主要議題", ""])
    header = "| 關鍵字 | 總筆數 | " + " | ".join(display_years) + " |"
    align = "| --- | ---: | " + " | ".join("---:" for _ in display_years) + " |"
    lines.extend([header, align])
    for stat in ranked:
        counts = " | ".join(f"{stat.years.get(year, 0):,}" for year in display_years)
        lines.append(
            f"| {obsidian_uri_link(keyword_page_path(stat.profile), stat.profile.title)} | "
            f"{len(stat.items):,} | {counts} |"
        )

    lines.extend(["", "## 年度主題排行", ""])
    for year in reversed(display_years):
        year_stats = sorted(
            stats.values(),
            key=lambda stat: (-stat.years.get(year, 0), stat.profile.title),
        )
        top = [stat for stat in year_stats if stat.years.get(year, 0)][:5]
        lines.append(f"### {year}")
        if not top:
            lines.append("")
            continue
        for stat in top:
            lines.append(
                f"- {obsidian_uri_link(keyword_page_path(stat.profile), stat.profile.title)}："
                f"{stat.years.get(year, 0):,}"
            )
        lines.append("")
    return "\n".join(lines)


def recent_trend_items(items: Iterable[NewsItem]) -> list[tuple[NewsItem, datetime]]:
    result: list[tuple[NewsItem, datetime]] = []
    for item in items:
        if not item.date:
            continue
        try:
            result.append((item, datetime.strptime(item.date, "%Y-%m-%d")))
        except ValueError:
            continue
    return result


def recent_trend_label(current_count: int, previous_count: int) -> str:
    if current_count and not previous_count:
        return "新增"
    if current_count > previous_count:
        return "上升"
    if current_count < previous_count:
        return "下降"
    return "持平"


def render_recent_policy_trend(
    items: list[NewsItem],
    stats: dict[str, KeywordStats],
    generated_at: str,
) -> str:
    dated_items = recent_trend_items(items)
    lines = ["# 最近30天政策趨勢", "", f"- 產生時間：{generated_at}"]
    if not dated_items:
        return "\n".join([*lines, "", "目前沒有可用日期的新聞資料。", ""])

    latest_date = max(date for _item, date in dated_items)
    current_start = latest_date - timedelta(days=29)
    previous_start = latest_date - timedelta(days=59)
    previous_end = latest_date - timedelta(days=30)
    current_items = [item for item, date in dated_items if current_start <= date <= latest_date]
    previous_items = [item for item, date in dated_items if previous_start <= date <= previous_end]
    lines.extend(
        [
            f"- 本期：{current_start:%Y-%m-%d} 至 {latest_date:%Y-%m-%d}",
            f"- 前 30 天：{previous_start:%Y-%m-%d} 至 {previous_end:%Y-%m-%d}",
            "",
            "## 新聞量",
            "",
            "| 期間 | 新聞筆數 |",
            "| --- | ---: |",
            f"| 最近 30 天 | {len(current_items):,} |",
            f"| 前 30 天 | {len(previous_items):,} |",
            "",
            "## 每週變化",
            "",
            "| 區間 | 新聞筆數 |",
            "| --- | ---: |",
        ]
    )
    for offset in range(0, 30, 7):
        week_start = current_start + timedelta(days=offset)
        week_end = min(week_start + timedelta(days=6), latest_date)
        count = sum(week_start <= date <= week_end for _item, date in dated_items)
        lines.append(f"| {week_start:%m-%d} 至 {week_end:%m-%d} | {count:,} |")

    ranked: list[tuple[KeywordStats, int, int]] = []
    for stat in stats.values():
        stat_dates = [datetime.strptime(item.date, "%Y-%m-%d") for item in stat.items if item.date]
        current_count = sum(current_start <= date <= latest_date for date in stat_dates)
        previous_count = sum(previous_start <= date <= previous_end for date in stat_dates)
        if current_count:
            ranked.append((stat, current_count, previous_count))
    ranked.sort(key=lambda row: (-row[1], row[0].profile.title))
    lines.extend(["", "## 政策議題動能", "", "| 議題 | 最近 30 天 | 前 30 天 | 走向 |", "| --- | ---: | ---: | --- |"])
    for stat, current_count, previous_count in ranked[:12]:
        lines.append(
            f"| {obsidian_uri_link(policy_topic_path(stat.profile), stat.profile.title)} | "
            f"{current_count:,} | {previous_count:,} | {recent_trend_label(current_count, previous_count)} |"
        )
    if not ranked:
        lines.append("| 無命中政策關鍵字 | 0 | 0 | 持平 |")

    lines.extend(["", "## 代表新聞", ""])
    for stat, _current_count, _previous_count in ranked[:8]:
        representative_items = sorted(
            [
                item for item in stat.items
                if item.date and current_start <= datetime.strptime(item.date, "%Y-%m-%d") <= latest_date
            ],
            key=item_sort_key,
            reverse=True,
        )[:3]
        lines.append(f"### {stat.profile.title}")
        for item in representative_items:
            lines.append(f"- {item.date}｜{obsidian_uri_link(item.note_path, item.title)}")
        lines.append("")
    return "\n".join(lines)


def render_policy_topic_overview(stats: dict[str, KeywordStats], generated_at: str) -> str:
    lines = [
        "# 政策議題總覽",
        "",
        f"- 產生時間：{generated_at}",
        f"- 議題數：{len(stats):,}",
        "",
        "| 政策議題 | 群組 | 新聞筆數 | 說明 |",
        "| --- | --- | ---: | --- |",
    ]
    for stat in keyword_rank(stats):
        lines.append(
            f"| {obsidian_uri_link(policy_topic_path(stat.profile), stat.profile.title)} | "
            f"{stat.profile.group} | {len(stat.items):,} | {stat.profile.description} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_public_home(
    items: list[NewsItem],
    stats: dict[str, KeywordStats],
    generated_at: str,
    total_from_site: int | None,
) -> str:
    first_date, last_date = date_range(items)
    ranked = keyword_rank(stats)
    lines = [
        "# 環境部新聞政策趨勢首頁",
        "",
        f"- 更新時間：{generated_at}",
        f"- 收錄期間：{first_date} 至 {last_date}",
        f"- 收錄新聞：{len(items):,}",
    ]
    if total_from_site is not None:
        lines.append(f"- 網站總筆數：{total_from_site:,}")
    lines.extend(
        [
            "",
            "## 入口",
            "",
            f"- {obsidian_uri_link(Path('環境部新聞索引.md'), '完整索引')}",
            f"- {obsidian_uri_link(Path('索引') / '趨勢.md', '趨勢總覽')}",
            f"- {obsidian_uri_link(Path('01_政策議題') / '政策議題總覽.md', '政策議題總覽')}",
            f"- {obsidian_uri_link(public_news_path('最近新聞'), '最近新聞')}",
            f"- {obsidian_uri_link(public_news_path('最近30天政策趨勢'), '最近30天政策趨勢')}",
            f"- {obsidian_uri_link(public_news_path('年度趨勢'), '年度趨勢')}",
            "",
            "## 主要政策議題",
            "",
        ]
    )
    for stat in ranked[:12]:
        lines.append(f"- {obsidian_uri_link(policy_topic_path(stat.profile), stat.profile.title)}：{len(stat.items):,}")
    lines.extend(["", "## 最近新聞", ""])
    for item in sorted(items, key=item_sort_key, reverse=True)[:20]:
        lines.append(
            f"- {item.date or item.roc_date}｜{item.category or '未分類'}｜"
            f"{obsidian_uri_link(item.note_path, item.title)}"
        )
    lines.append("")
    return "\n".join(lines)


def render_public_recent(items: list[NewsItem]) -> str:
    lines = [
        "# 最近新聞",
        "",
        f"- {obsidian_uri_link(public_news_path('最近30天政策趨勢'), '查看最近30天政策趨勢')}",
        "",
        "## 最新 120 筆",
        "",
    ]
    for item in sorted(items, key=item_sort_key, reverse=True)[:120]:
        lines.append(
            f"- {item.date or item.roc_date}｜{item.category or '未分類'}｜"
            f"{item.unit or '未標示'}｜{obsidian_uri_link(item.note_path, item.title)}"
        )
    lines.append("")
    return "\n".join(lines)


def render_public_keyword_table(stats: dict[str, KeywordStats]) -> str:
    lines = [
        "# 關鍵字總表",
        "",
        "| 關鍵字 | 群組 | 筆數 | 同義詞 |",
        "| --- | --- | ---: | --- |",
    ]
    for stat in keyword_rank(stats):
        lines.append(
            f"| {obsidian_uri_link(policy_topic_path(stat.profile), stat.profile.title)} | "
            f"{stat.profile.group} | {len(stat.items):,} | {', '.join(stat.profile.aliases)} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_public_year_trends(items: list[NewsItem], stats: dict[str, KeywordStats]) -> str:
    years = year_sequence(items)
    lines = ["# 年度趨勢", ""]
    for year in reversed(years):
        year_items = [item for item in items if item_year(item) == year]
        year_stats = sorted(
            stats.values(),
            key=lambda stat: (-stat.years.get(year, 0), stat.profile.title),
        )
        lines.extend([f"## {year}", "", f"- 新聞筆數：{len(year_items):,}", ""])
        for stat in [stat for stat in year_stats if stat.years.get(year, 0)][:8]:
            lines.append(f"- {stat.profile.title}：{stat.years.get(year, 0):,}")
        lines.append("")
    return "\n".join(lines)


def write_keyword_data_files(
    vault: Path,
    items: list[NewsItem],
    matches_by_id: dict[str, list[KeywordMatch]],
    stats: dict[str, KeywordStats],
    generated_at: str,
) -> None:
    data_dir = vault / "資料"
    data_dir.mkdir(parents=True, exist_ok=True)

    keyword_database = {
        "generated_at": generated_at,
        "source": SOURCE_NAME,
        "source_url": f"{BASE_URL}{LIST_PATH}",
        "note_root": NOTE_ROOT_QUERY,
        "profiles": [
            {
                "slug": stat.profile.slug,
                "title": stat.profile.title,
                "group": stat.profile.group,
                "description": stat.profile.description,
                "aliases": list(stat.profile.aliases),
                "total": len(stat.items),
                "year_counts": dict(sorted(stat.years.items())),
            }
            for stat in keyword_rank(stats)
        ],
    }
    write_text(data_dir / "moenv_keyword_database.json", json.dumps(keyword_database, ensure_ascii=False, indent=2))

    with (data_dir / "moenv_keyword_years.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["keyword_slug", "keyword", "group", "year", "count"])
        writer.writeheader()
        for stat in keyword_rank(stats):
            for year, count in sorted(stat.years.items()):
                writer.writerow(
                    {
                        "keyword_slug": stat.profile.slug,
                        "keyword": stat.profile.title,
                        "group": stat.profile.group,
                        "year": year,
                        "count": count,
                    }
                )

    news_keyword_rows: list[dict[str, str]] = []
    for item in sorted(items, key=item_sort_key, reverse=True):
        matches = matches_by_id.get(item.news_id, [])
        news_keyword_rows.append(
            {
                "news_id": item.news_id,
                "date": item.date,
                "title": item.title,
                "category": item.category,
                "unit": item.unit,
                "keyword_slugs": ";".join(match.profile.slug for match in matches),
                "keywords": ";".join(match.profile.title for match in matches),
                "matched_aliases": ";".join(
                    f"{match.profile.slug}:{','.join(match.aliases)}" for match in matches
                ),
                "note_path": item.note_path,
                "source_url": item.source_url,
            }
        )

    with (data_dir / "moenv_news_keywords.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(news_keyword_rows[0].keys()) if news_keyword_rows else [])
        if news_keyword_rows:
            writer.writeheader()
            writer.writerows(news_keyword_rows)

    with (data_dir / "moenv_news_keywords.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in news_keyword_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def render_daily_report(items: list[NewsItem], new_ids: set[str], generated_at: str) -> tuple[str, str, str]:
    new_items = sorted(
        [item for item in items if item.news_id in new_ids],
        key=item_sort_key,
        reverse=True,
    )
    report_date = new_items[0].date if new_items and new_items[0].date else generated_at[:10]
    lines = [
        f"{report_date}，更新{len(new_items)}筆",
        "清單如下",
    ]
    if new_items:
        for item in new_items:
            lines.append(
                f"{item.date or item.roc_date}｜{item.category or '未分類'}｜"
                f"{obsidian_uri_link(item.note_path, item.title)}"
            )
    else:
        lines.append("無新增新聞")
    subject = f"環境部新聞更新：{report_date}，更新{len(new_items)}筆"
    return report_date, subject, "\n".join(lines) + "\n"


def render_research_review_queue(entries: list[ResearchReviewEntry], generated_at: str) -> str:
    a_count = sum(entry.level == "A" for entry in entries)
    b_count = sum(entry.level == "B" for entry in entries)
    lines = [
        "# 研究報告更新佇列",
        "",
        f"產生時間：{generated_at}",
        "",
        "## 摘要",
        f"- A 級：{a_count} 筆",
        f"- B 級：{b_count} 筆",
    ]
    if not entries:
        lines.extend(["", "目前沒有待審項目。"])
        return "\n".join(lines) + "\n"

    lines.extend(["", "## 待審項目"])
    for entry in entries:
        lines.extend(
            [
                "",
                f"### {entry.level} 級｜{entry.news_date}｜{entry.report_topic}",
                f"- 建議：{entry.update_action}",
                f"- 研究報告：{obsidian_uri_link(entry.report_path, entry.report_topic)}",
                f"- 新聞：{obsidian_uri_link(entry.note_path, entry.news_title)}",
                f"- 命中：{'、'.join(entry.matched_terms)}",
                f"- 原因：{'；'.join(entry.reasons)}",
                f"- 原始來源：{entry.source_url}",
            ]
        )
    return "\n".join(lines) + "\n"


def write_daily_report(vault: Path, items: list[NewsItem], new_ids: set[str], generated_at: str) -> None:
    report_date, subject, body = render_daily_report(items, new_ids, generated_at)
    report_dir = vault / "資料" / "daily_update_reports"
    write_text(report_dir / "latest.md", body)
    write_text(report_dir / f"{report_date}.md", body)
    payload = {
        "generated_at": generated_at,
        "report_date": report_date,
        "subject": subject,
        "body_file": (Path("資料") / "daily_update_reports" / "latest.md").as_posix(),
        "count": len(new_ids),
    }
    write_text(report_dir / "latest.json", json.dumps(payload, ensure_ascii=False, indent=2))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    retry_delays = (0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0)
    last_error: PermissionError | None = None
    for attempt, delay in enumerate(retry_delays, start=1):
        if delay:
            time.sleep(delay)
        try:
            path.write_text(text, encoding="utf-8", newline="\n")
            return
        except PermissionError as exc:
            last_error = exc

        temp_path = path.with_name(f".{path.name}.{os.getpid()}.{attempt}.tmp")
        try:
            temp_path.write_text(text, encoding="utf-8", newline="\n")
            temp_path.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
    if last_error:
        raise last_error


def normalize_item(item: NewsItem) -> None:
    item.category = item.category.strip()
    item.unit = item.unit.strip()
    if not item.category:
        item.category = "未分類"
    if not item.unit:
        item.unit = "未標示"


def load_existing_items(vault: Path) -> list[NewsItem]:
    jsonl_path = vault / "資料" / "moenv_news_index.jsonl"
    csv_path = vault / "資料" / "moenv_news_index.csv"
    items: list[NewsItem] = []

    if jsonl_path.exists():
        with jsonl_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    items.append(item_from_mapping(json.loads(line)))
        return items

    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                items.append(item_from_mapping(row))
    return items


def write_outputs(
    vault: Path,
    items: list[NewsItem],
    generated_at: str,
    total_from_site: int | None,
    mode: str,
    new_count: int,
    note_ids_to_write: set[str] | None = None,
) -> None:
    items = sorted(items, key=item_sort_key, reverse=True)
    for item in items:
        normalize_item(item)
        rel_path = note_relative_path(item)
        item.note_path = rel_path.as_posix()

    remove_stale_markdown(vault / NOTE_ROOT, {vault / item.note_path for item in items})

    matches_by_id = build_keyword_matches(items)
    keyword_stats = build_keyword_stats(items, matches_by_id)
    keyword_cooccurrence = build_keyword_cooccurrence(matches_by_id)

    for item in items:
        if note_ids_to_write is None or item.news_id in note_ids_to_write:
            write_text(vault / item.note_path, render_note(item, matches_by_id.get(item.news_id, [])))

    write_text(vault / "環境部新聞索引.md", render_master_index(items, generated_at, total_from_site, keyword_stats))

    category_groups = group_items(items, lambda item: item.category or "未分類")
    unit_groups = group_items(items, lambda item: item.unit or "未標示")
    year_groups = group_items(items, lambda item: (item.date[:4] if item.date else "unknown"))

    write_text(
        vault / "索引" / "分類.md",
        render_group_index("分類索引", Path("索引") / "分類.md", "分類", category_groups),
    )
    for name, group in category_groups:
        current_path = Path("索引") / "分類" / f"{sanitize_filename(name)}.md"
        write_text(vault / current_path, render_group_page(name, current_path, group))

    write_text(
        vault / "索引" / "發布單位.md",
        render_group_index("發布單位索引", Path("索引") / "發布單位.md", "發布單位", unit_groups),
    )
    for name, group in unit_groups:
        current_path = Path("索引") / "發布單位" / f"{sanitize_filename(name)}.md"
        write_text(vault / current_path, render_group_page(name, current_path, group))

    write_text(
        vault / "索引" / "年份.md",
        render_group_index("年份索引", Path("索引") / "年份.md", "年份", year_groups),
    )
    for name, group in year_groups:
        current_path = Path("索引") / "年份" / f"{sanitize_filename(name)}.md"
        write_text(vault / current_path, render_group_page(name, current_path, group))

    remove_stale_markdown(vault / "索引" / "關鍵字", set())
    (vault / "索引" / "關鍵字.md").unlink(missing_ok=True)
    write_text(vault / "索引" / "趨勢.md", render_trend_index(items, keyword_stats, generated_at))

    write_text(
        vault / "00_公開入口" / "首頁.md",
        render_public_home(items, keyword_stats, generated_at, total_from_site),
    )
    for stat in keyword_rank(keyword_stats):
        if stat.profile.public:
            write_text(
                vault / policy_topic_path(stat.profile),
                render_keyword_page(stat, keyword_cooccurrence, matches_by_id, public_variant=True),
            )
    write_text(
        vault / "01_政策議題" / "政策議題總覽.md",
        render_policy_topic_overview(keyword_stats, generated_at),
    )
    write_text(vault / public_news_path("最近新聞"), render_public_recent(items))
    write_text(
        vault / public_news_path("最近30天政策趨勢"),
        render_recent_policy_trend(items, keyword_stats, generated_at),
    )
    write_text(vault / public_news_path("關鍵字總表"), render_public_keyword_table(keyword_stats))
    write_text(vault / public_news_path("年度趨勢"), render_public_year_trends(items, keyword_stats))
    write_keyword_data_files(vault, items, matches_by_id, keyword_stats, generated_at)

    data_dir = vault / "資料"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "moenv_news_index.csv"
    fieldnames = list(asdict(items[0]).keys()) if items else list(NewsItem.__dataclass_fields__.keys())
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))

    jsonl_path = data_dir / "moenv_news_index.jsonl"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    manifest = {
        "source": SOURCE_NAME,
        "source_url": f"{BASE_URL}{LIST_PATH}",
        "generated_at": generated_at,
        "mode": mode,
        "new_count": new_count,
        "indexed_count": len(items),
        "site_total": total_from_site,
        "note_root": NOTE_ROOT_QUERY,
        "keyword_profiles": len(KEYWORD_PROFILES),
    }
    write_text(data_dir / "moenv_news_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))


def list_url(page: int) -> str:
    return f"{BASE_URL}{LIST_PATH}?M=L&page={page}"


def fetch_new_list_page(page: int, retries: int, timeout: int) -> str:
    payload = urlencode({"Key": "11", "Lang": "zh-tw", "P": page, "DC": "20", "cl": "0"}).encode()
    request = Request(
        f"{BASE_URL}/WebAPI/WebsiteList/NewsList",
        data=payload,
        headers={
            **BROWSER_HEADERS,
            "Origin": BASE_URL,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "text/html, */*; q=0.01",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            context = ssl.create_default_context()
            with urlopen(request, timeout=timeout, context=context) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 * attempt, 8))
    raise RuntimeError(f"Failed to fetch new-format news list page {page}: {last_error}") from last_error


def fetch_first_list_page(args: argparse.Namespace) -> tuple[str, list[NewsItem], bool, int | None]:
    legacy_error: Exception | None = None
    try:
        html = fetch_url(list_url(1), retries=args.retries, timeout=args.timeout, use_curl=args.use_curl)
        items = parse_list_page(html)
        if items:
            return html, items, is_new_list_page(html), parse_total(html)
    except Exception as exc:  # noqa: BLE001
        legacy_error = exc

    html = fetch_new_list_page(1, retries=args.retries, timeout=args.timeout)
    items = parse_list_page(html)
    if items:
        return html, items, True, parse_total(html)
    if legacy_error:
        raise RuntimeError(
            "No news items found using the legacy list page or the new list API."
        ) from legacy_error
    raise RuntimeError("No news items found on the first page; the page structure may have changed.")


def fetch_detail_pages(items: list[NewsItem], args: argparse.Namespace) -> None:
    open_data_summaries: dict[tuple[str, str], str] = {}
    if args.summary_from_detail:
        try:
            open_data_summaries = fetch_open_data_summary_map(args)
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: failed to fetch official open-data summaries: {exc}")
    for index, item in enumerate(items, start=1):
        summary = summary_for_item(item, open_data_summaries)
        detail_html = ""
        if args.include_detail or (args.summary_from_detail and not summary):
            try:
                detail_html = fetch_url(item.source_url, retries=args.retries, timeout=args.timeout, use_curl=args.use_curl)
            except Exception as exc:  # noqa: BLE001
                print(f"Warning: failed to fetch detail for {item.news_id}: {exc}")
        if args.summary_from_detail:
            summary = summary or parse_detail_summary(detail_html, args.summary_chars)
            if summary:
                item.summary = summary
        if args.include_detail:
            item.body = parse_detail_body(detail_html)
        if index % args.progress_every == 0 or index == len(items):
            print(f"Detail {index}/{len(items)}")
        if args.delay:
            time.sleep(args.delay)


def crawl(args: argparse.Namespace) -> tuple[list[NewsItem], int | None]:
    _first_html, first_items, uses_new_list_api, total = fetch_first_list_page(args)

    page_size = len(first_items)
    page_limit = math.ceil(total / page_size) if total else None
    if args.max_pages:
        page_limit = min(page_limit, args.max_pages) if page_limit else args.max_pages
    page_label = str(page_limit) if page_limit else "?"

    seen: dict[str, NewsItem] = {item.news_id: item for item in first_items}
    print(f"Page 1/{page_label}: {len(first_items)} items, total so far {len(seen)}")

    page = 2
    while page_limit is None or page <= page_limit:
        html = (
            fetch_new_list_page(page, retries=args.retries, timeout=args.timeout)
            if uses_new_list_api
            else fetch_url(list_url(page), retries=args.retries, timeout=args.timeout, use_curl=args.use_curl)
        )
        page_items = parse_list_page(html)
        if not page_items:
            print(f"Page {page}/{page_label}: no items; stopping.")
            break
        for item in page_items:
            seen.setdefault(item.news_id, item)
        if page % args.progress_every == 0 or page == page_limit:
            print(f"Page {page}/{page_label}: {len(page_items)} items, total so far {len(seen)}")
        if args.delay:
            time.sleep(args.delay)
        page += 1

    items = sorted(seen.values(), key=item_sort_key, reverse=True)
    if args.limit:
        items = items[: args.limit]

    if args.include_detail or args.summary_from_detail:
        fetch_detail_pages(items, args)

    return items, total


def crawl_incremental(args: argparse.Namespace, existing_items: list[NewsItem]) -> tuple[list[NewsItem], int | None, set[str] | None, set[str] | None]:
    existing_by_id = {item.news_id: item for item in existing_items}
    existing_by_identity = {item_identity_key(item): item for item in existing_items}
    if not existing_by_id:
        print("No existing index found; running a full crawl.")
        items, total = crawl(args)
        return items, total, None, None

    if not args.summary_from_detail:
        args.summary_from_detail = True
        print("Incremental mode: new items will use first-paragraph detail summaries.")

    if args.limit:
        print("Warning: --limit is ignored in incremental mode to avoid dropping existing items.")

    _first_html, first_items, uses_new_list_api, total = fetch_first_list_page(args)

    page_size = len(first_items)
    page_limit = math.ceil(total / page_size) if total else None
    if args.max_pages:
        page_limit = min(page_limit, args.max_pages) if page_limit else args.max_pages
    page_label = str(page_limit) if page_limit else "?"

    new_by_id: dict[str, NewsItem] = {}
    metadata_updated_ids: set[str] = set()
    hit_existing = False
    page_limit_description = f"{page_limit} page(s)" if page_limit else "the first existing item"
    print(f"Incremental update: {len(existing_by_id)} existing items. Checking up to {page_limit_description}.")

    def collect(page_items: list[NewsItem]) -> int:
        nonlocal hit_existing
        before = len(new_by_id)
        for item in page_items:
            existing = existing_by_id.get(item.news_id) or existing_by_identity.get(item_identity_key(item))
            if existing:
                if merge_list_metadata(existing, item):
                    metadata_updated_ids.add(existing.news_id)
                hit_existing = True
            else:
                new_by_id.setdefault(item.news_id, item)
        return len(new_by_id) - before

    page_new = collect(first_items)
    print(f"Page 1/{page_label}: {page_new} new, total new {len(new_by_id)}")

    page = 2
    while page_limit is None or page <= page_limit:
        if hit_existing:
            break
        if args.delay:
            time.sleep(args.delay)
        html = (
            fetch_new_list_page(page, retries=args.retries, timeout=args.timeout)
            if uses_new_list_api
            else fetch_url(list_url(page), retries=args.retries, timeout=args.timeout, use_curl=args.use_curl)
        )
        page_items = parse_list_page(html)
        if not page_items:
            print(f"Page {page}/{page_label}: no items; stopping.")
            break
        page_new = collect(page_items)
        if page % args.progress_every == 0 or hit_existing or page == page_limit:
            print(f"Page {page}/{page_label}: {page_new} new, total new {len(new_by_id)}")
        page += 1

    new_items = sorted(new_by_id.values(), key=item_sort_key, reverse=True)
    if (args.include_detail or args.summary_from_detail) and new_items:
        fetch_detail_pages(new_items, args)

    merged = dict(existing_by_id)
    merged.update(new_by_id)
    if new_by_id:
        print(f"Added {len(new_by_id)} new item(s).")
    else:
        print("No new items found.")
    note_ids_to_write = set(new_by_id) | metadata_updated_ids
    return sorted(merged.values(), key=item_sort_key, reverse=True), total, set(new_by_id), note_ids_to_write


def load_site_total_from_manifest(vault: Path) -> int | None:
    manifest_path = vault / "資料" / "moenv_news_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return parse_int(str(manifest.get("site_total", "")))


def summary_cache_path(vault: Path) -> Path:
    return vault / "資料" / "moenv_detail_summaries.jsonl"


def load_summary_cache(vault: Path) -> dict[str, str]:
    path = summary_cache_path(vault)
    summaries: dict[str, str] = {}
    if not path.exists():
        return summaries
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            news_id = str(record.get("news_id", ""))
            summary = str(record.get("summary", ""))
            if news_id and summary:
                summaries[news_id] = summary
    return summaries


def append_summary_cache(vault: Path, item: NewsItem, summary: str) -> None:
    path = summary_cache_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "news_id": item.news_id,
        "source_url": item.source_url,
        "summary": summary,
        "cached_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def refresh_summaries(args: argparse.Namespace, existing_items: list[NewsItem]) -> tuple[list[NewsItem], int | None, set[str]]:
    if not existing_items:
        raise RuntimeError("No existing index found. Run a full crawl first.")
    if not args.summary_from_detail:
        args.summary_from_detail = True
    vault = args.vault.resolve()
    cached_summaries = load_summary_cache(vault)
    updated_ids = set()
    for item in existing_items:
        summary = cached_summaries.get(item.news_id)
        if summary and item.summary != summary:
            item.summary = summary
            updated_ids.add(item.news_id)

    remaining = [
        item for item in existing_items
        if item.news_id not in cached_summaries and not item.summary
    ]
    if args.max_detail_items:
        remaining = remaining[: args.max_detail_items]

    print(
        f"Refreshing detail summaries: {len(cached_summaries)} cached, "
        f"{len(remaining)} to fetch this run, {len(existing_items)} total."
    )
    open_data_summaries: dict[tuple[str, str], str] = {}
    if remaining:
        try:
            open_data_summaries = fetch_open_data_summary_map(args)
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: failed to fetch official open-data summaries: {exc}")
    for index, item in enumerate(remaining, start=1):
        summary = summary_for_item(item, open_data_summaries)
        if not summary:
            try:
                detail_html = fetch_url(
                    item.source_url,
                    retries=args.retries,
                    timeout=args.timeout,
                    use_curl=args.use_curl,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"Warning: failed to fetch detail for {item.news_id}: {exc}")
                detail_html = ""
            summary = parse_detail_summary(detail_html, args.summary_chars)
        if summary:
            item.summary = summary
            append_summary_cache(vault, item, summary)
            updated_ids.add(item.news_id)
        if index % args.progress_every == 0 or index == len(remaining):
            print(f"Detail summary {index}/{len(remaining)}")
        if args.delay:
            time.sleep(args.delay)

    return sorted(existing_items, key=item_sort_key, reverse=True), load_site_total_from_manifest(vault), updated_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an Obsidian index for MOENV news.")
    parser.add_argument("--vault", type=Path, default=Path("."), help="Obsidian vault/output folder.")
    parser.add_argument("--max-pages", type=int, default=0, help="Only crawl the first N list pages.")
    parser.add_argument("--limit", type=int, default=0, help="Only write the newest N items after crawling.")
    parser.add_argument("--delay", type=float, default=0.08, help="Delay between requests in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Retries per request.")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds.")
    parser.add_argument("--progress-every", type=int, default=25, help="Print progress every N pages/items.")
    parser.add_argument("--include-detail", action="store_true", help="Also fetch each detail page body.")
    parser.add_argument("--summary-from-detail", action="store_true", help="Use the first paragraph from each detail page as the summary.")
    parser.add_argument("--summary-chars", type=int, default=500, help="Maximum characters for detail-page summaries; 0 means no limit.")
    parser.add_argument("--refresh-summaries", action="store_true", help="Refresh summaries for existing indexed items without recrawling all list pages.")
    parser.add_argument("--max-detail-items", type=int, default=0, help="Limit detail pages fetched in this run; useful for resumable summary refreshes.")
    parser.add_argument("--rebuild-indexes", action="store_true", help="Rebuild notes, keyword data, and indexes from existing local CSV/JSONL without network access.")
    parser.add_argument("--index-pages-only", action="store_true", help="With --rebuild-indexes, rebuild index and public pages without rewriting news notes.")
    parser.add_argument("--daily-report", action="store_true", help="After an incremental update, write the daily email report to data/daily_update_reports.")
    parser.add_argument("--use-curl", action="store_true", help="Use curl instead of Python urllib.")
    parser.add_argument("--incremental", action="store_true", help="Only fetch pages until existing news IDs are found.")
    parser.add_argument("--full", action="store_true", help="Force a full crawl; useful when wrappers default to incremental.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    vault = args.vault.resolve()
    if args.full:
        args.incremental = False

    if args.rebuild_indexes:
        existing_items = load_existing_items(vault)
        if not existing_items:
            raise RuntimeError("No existing index found. Run a full crawl first.")
        total = load_site_total_from_manifest(vault)
        items = sorted(existing_items, key=item_sort_key, reverse=True)
        note_ids_to_write = set() if args.index_pages_only else None
        write_outputs(
            vault,
            items,
            generated_at,
            total,
            mode="rebuild-indexes",
            new_count=0,
            note_ids_to_write=note_ids_to_write,
        )
    elif args.refresh_summaries:
        existing_items = load_existing_items(vault)
        items, total, updated_ids = refresh_summaries(args, existing_items)
        write_outputs(
            vault,
            items,
            generated_at,
            total,
            mode="refresh-summaries",
            new_count=0,
            note_ids_to_write=updated_ids,
        )
    elif args.incremental:
        existing_items = load_existing_items(vault)
        items, total, new_ids, note_ids_to_write = crawl_incremental(args, existing_items)
        mode = "incremental"
        new_count = len(new_ids) if new_ids is not None else len(items)
        has_changes = new_ids is None or bool(new_ids) or bool(note_ids_to_write)
        if has_changes:
            write_outputs(
                vault,
                items,
                generated_at,
                total,
                mode=mode,
                new_count=new_count,
                note_ids_to_write=note_ids_to_write,
            )
        else:
            print("No changes detected; generated files left untouched.")
        if args.daily_report:
            report_ids = new_ids if new_ids is not None else {item.news_id for item in items}
            write_daily_report(vault, items, report_ids, generated_at)
    else:
        items, total = crawl(args)
        items = reconcile_full_crawl_items(items, load_existing_items(vault))
        mode = "full"
        new_count = len(items)
        write_outputs(vault, items, generated_at, total, mode=mode, new_count=new_count)

    print(f"Done. Indexed {len(items)} news notes into {vault}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

