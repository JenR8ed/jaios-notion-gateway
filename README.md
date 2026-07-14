# jaios-notion-gateway

<!--
JAIOS Compliance Notes
Deployment Location: Vercel → jaios-notion-gateway
Governance Impact: Ingests Notion webhook events, routes to deploy-kit, logs to Deploys DB
Sanitization Requirement: Strip PII before Notion write
Secrets Handling: Doppler only
-->

Production webhook gateway for the **JenR8ed AI Operating System (JAIOS)**.

## What it does

- Receives Notion webhook events at `POST /api/webhook`
- Verifies HMAC-SHA256 signature (`x-notion-signature` header)
- Validates event schema with Zod
- Routes events to deploy-kit actions
- Logs every event to the JAIOS Deploys DB in Notion

## Required Doppler Secrets

| Secret | Description |
|---|---|
| `NOTION_TOKEN` | Notion integration token |
| `NOTION_WEBHOOK_SECRET` | HMAC secret for webhook verification |
| `NOTION_DEPLOYS_DB_ID` | ID of the JAIOS Deploys DB |

## Deployment

1. Import this repo into Vercel as a new project
2. Set Doppler as the secrets source (do NOT use Vercel env vars directly)
3. Re-add custom domains: `jenr8ed.live` + `www.jenr8ed.live`
4. Update Notion integration with the new webhook URL: `https://jenr8ed.live/api/webhook`

## JAIOS Principles

- **Zero-trust**: Doppler only. No `.env` files. Ever.
- **FSAD**: This service is stateless. All state lives in Notion.
- **Audit trail**: Every event is logged to the Deploys DB.
