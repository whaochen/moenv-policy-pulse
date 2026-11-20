import fs from 'node:fs';
import path from 'node:path';
import { getCollection, type CollectionEntry } from 'astro:content';

export interface NewsRecord {
  news_id: string;
  date: string;
  roc_date: string;
  title: string;
  unit: string;
  summary: string;
  policy_keywords: string[];
  ai_tags: string[];
  source_url: string;
  attach_url: string;
}

export interface ManifestData {
  total_news: number;
  date_start: string;
  date_end: string;
  updated_at: string;
  topic_count: number;
  years: string[];
  last_30_days_count: number;
  prev_30_days_count: number;
  last_30_days_delta: number;
  last_30_days_pct: number;
  latest_news: NewsRecord[];
}

export interface TopicData {
  slug: string;
  title: string;
  group: string;
  description: string;
  aliases: string[];
  total_count: number;
  last_30_days_count: number;
  prev_30_days_count: number;
  yearly_counts: Record<string, number>;
  latest_news: NewsRecord[];
}

export interface TrendsData {
  updated_at: string;
  yearly_totals: { year: string; count: number }[];
  topic_yearly_matrix: {
    years: string[];
    topics: {
      slug: string;
      title: string;
      group: string;
      counts: number[];
    }[];
  };
  last_30_days: {
    window_start: string;
    window_end: string;
    prev_start: string;
    prev_end: string;
    current_total: number;
    previous_total: number;
    delta: number;
    pct_change: number;
    topics: {
      slug: string;
      title: string;
      group: string;
      current: number;
      previous: number;
      delta: number;
      pct_change: number;
    }[];
    weekly_counts: { week_start: string; week_end: string; count: number }[];
  };
  unit_ranking: {
    recent_1y: { unit: string; count: number }[];
    all_time: { unit: string; count: number }[];
  };
}

export interface ResearchReportItem {
  slug: string;
  filename: string;
  topic: string;
  issue_type: string;
  status: string;
  keywords: string[];
  aliases: string[];
  created: string;
  updated: string;
  coverage_start: string;
  coverage_end: string;
  summary: string;
  body_markdown: string;
}

export interface ResearchDatasetItem {
  filename: string;
  research_id: string;
  schema_version: string;
  topic: { slug?: string; name_zh?: string; description?: string };
  scope: { date_from?: string; date_to?: string; article_count?: number };
  statistics: {
    total_articles?: number;
    first_article_date?: string;
    latest_article_date?: string;
    peak_year?: { year?: number; count?: number };
  };
  trend_series: {
    series_id: string;
    label: string;
    unit: string;
    frequency: string;
    points: { period: string; value: number }[];
  }[];
  milestones?: unknown[];
}

export interface ResearchData {
  generated_at: string;
  report_count: number;
  dataset_count: number;
  reports: ResearchReportItem[];
  datasets: ResearchDatasetItem[];
}

const DATA_DIR = path.resolve(process.cwd(), 'public', 'data');

function readJson<T>(relativePath: string): T {
  const fullPath = path.join(DATA_DIR, relativePath);
  return JSON.parse(fs.readFileSync(fullPath, 'utf-8')) as T;
}

export function loadManifest(): ManifestData {
  return readJson<ManifestData>('manifest.json');
}

export function loadTopics(): TopicData[] {
  return readJson<TopicData[]>('topics.json');
}

export function loadTrends(): TrendsData {
  return readJson<TrendsData>('trends.json');
}

export function loadResearch(): ResearchData {
  return readJson<ResearchData>('research.json');
}

let cachedNewsById: Map<string, NewsRecord> | null = null;

export function lookupNewsByIds(ids: (string | number)[]): NewsRecord[] {
  if (!ids.length) return [];
  if (!cachedNewsById) {
    cachedNewsById = new Map();
    const newsDir = path.join(DATA_DIR, 'news');
    if (fs.existsSync(newsDir)) {
      for (const file of fs.readdirSync(newsDir)) {
        if (!file.endsWith('.json')) continue;
        const rows = JSON.parse(fs.readFileSync(path.join(newsDir, file), 'utf-8')) as NewsRecord[];
        for (const row of rows) {
          cachedNewsById.set(String(row.news_id), row);
        }
      }
    }
  }
  const results: NewsRecord[] = [];
  for (const rawId of ids) {
    const found = cachedNewsById.get(String(rawId).trim());
    if (found) results.push(found);
  }
  return results;
}

/**
 * Strict publish gate for《皓哥說》:
 * - Excludes any file whose basename starts with `_` (e.g. _template_draft.md)
 * - Includes ONLY entries with `status === 'published'`
 */
export async function getPublishedHaoTalks(): Promise<CollectionEntry<'haoTalks'>[]> {
  const entries = await getCollection('haoTalks', ({ id, data }) => {
    const base = id.split('/').pop() ?? id;
    if (base.startsWith('_')) return false;
    return data.status === 'published';
  });
  return entries.sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
}

export function formatIsoDate(d: Date | string): string {
  if (typeof d === 'string') return d.slice(0, 10);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function formatTaipeiTimestamp(iso: string): string {
  if (!iso) return '';
  return iso.replace('T', ' ').replace(/\+08:00$/, ' (UTC+8)');
}
