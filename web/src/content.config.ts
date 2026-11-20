import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const haoTalks = defineCollection({
  loader: glob({
    pattern: '**/*.md',
    base: '../04_皓哥說',
  }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    status: z.enum(['draft', 'published']).default('draft'),
    summary: z.string().default(''),
    topics: z.array(z.string()).default([]),
    related_news: z.array(z.union([z.string(), z.number()])).default([]),
    timeline_slug: z.string().optional().default(''),
  }),
});

export const collections = {
  haoTalks,
};
