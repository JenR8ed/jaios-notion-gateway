/*
 * JAIOS Compliance Notes
 * Deployment Location: Vercel → jaios-notion-gateway project
 * Governance Impact: Ingests Notion events → triggers deploy-kit + logs to Deploys DB
 * Sanitization Requirement: Strip PII before Notion write
 * Secrets Handling: Doppler only
 */

import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import crypto from 'crypto';
import { Client } from '@notionhq/client';

const notion = new Client({ auth: process.env.NOTION_TOKEN! });
const DEPLOYS_DB_ID = process.env.NOTION_DEPLOYS_DB_ID!;

const NotionEventSchema = z.object({
  type: z.string(),
  entity: z.object({ id: z.string().uuid(), type: z.enum(['page', 'database', 'block']) }),
  authors: z.array(z.object({ id: z.string(), type: z.string() })).optional(),
  timestamp: z.string(),
  workspace_id: z.string(),
});

function verifySignature(body: string, signature: string, secret: string): boolean {
  const expected = crypto.createHmac('sha256', secret).update(body).digest('hex');
  return crypto.timingSafeEqual(Buffer.from(`sha256=${expected}`), Buffer.from(signature));
}

async function routeEvent(event: any): Promise<string> {
  if (event.type === 'page.updated' || event.type === 'page.created') return `routed:page_update → professionalizer_check`;
  if (event.type === 'database.updated') return `routed:db_update → schema_sync`;
  return `routed:unhandled:${event.type}`;
}

async function logToDeploysDB(event: any, routeResult: string) {
  await notion.pages.create({
    parent: { database_id: DEPLOYS_DB_ID },
    properties: {
      Name: { title: [{ text: { content: `Webhook: ${event.type} @ ${event.timestamp}` } }] },
      Status: { select: { name: 'success' } },
      'Triggered By': { select: { name: 'webhook' } },
      Environment: { select: { name: 'production' } },
      Notes: { rich_text: [{ text: { content: routeResult.substring(0, 2000) } }] },
    },
  });
}

export async function POST(req: NextRequest) {
  const rawBody = await req.text();
  const signature = req.headers.get('x-notion-signature') ?? '';
  const secret = process.env.NOTION_WEBHOOK_SECRET ?? '';

  if (!secret || !verifySignature(rawBody, signature, secret)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let body: unknown;
  try { body = JSON.parse(rawBody); } catch { return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 }); }

  const parsed = NotionEventSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: 'Schema validation failed' }, { status: 422 });

  const routeResult = await routeEvent(parsed.data);
  await logToDeploysDB(parsed.data, routeResult);
  return NextResponse.json({ ok: true, routed: routeResult });
}
