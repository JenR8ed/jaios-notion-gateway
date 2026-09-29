# JAIOS Notion Gateway

Production-oriented webhook gateway for the **JenR8ed AI Operating System (JAIOS)**.

> **Current state:** Implemented integration component. It provides a concrete boundary between Notion events and JAIOS deployment workflows.

## What it does

- Receives Notion webhook events at `POST /api/webhook`
- Verifies HMAC-SHA256 signatures via `x-notion-signature`
- Validates event payloads with Zod
- Routes events to deployment-kit actions
- Logs events to the JAIOS Deploys DB in Notion

## Security boundary

```
Notion Event
     |
     v
Signature Verification
     |
     v
Schema Validation
     |
     v
JAIOS Routing
     |
     +-- deployment action
     +-- audit / Deploys DB
```

Security model:
- HMAC verification at ingress
- typed request validation
- no committed credentials
- managed secrets
- audit logging
- PII minimization before Notion writes

## Relationship to JAIOS

This service is intentionally narrow:

**Notion is the event source; JAIOS routing is the control boundary; Deploys DB is the audit surface.**

It is not the JAIOS runtime itself.

## Deployment

Intended deployment target: Vercel. Environment/secrets should be injected through the managed secret workflow rather than committed .env files.

## Related repositories

- [jaios-agentic-core](https://github.com/JenR8ed/jaios-agentic-core)
- [jenr8ed-deploy-kit](https://github.com/JenR8ed/jenr8ed-deploy-kit)
- [AI-List-Assist](https://github.com/JenR8ed/AI-List-Assist)

## Local FSAD ↔ Notion sync worker

`jaios_sync/` runs as a separate long-lived local/container worker, not in the
Vercel webhook process. Markdown added or edited under `fsad_storage/` creates
or updates one worker-owned Notion page per relative path. A persisted mapping
and content hash prevent duplicate pages on repeated file events or restarts.
The first 1,900 characters are displayed in one managed paragraph; the local
file retains the full text. The worker polls the mapped pages' `Status` select
or status property and writes `fsad_storage/.notion-status.json`, keyed by
relative Markdown path. It does not overwrite Markdown or change Notion status.

Select a dedicated Notion database shared with the integration, with a `Name`
title property and optionally a `Status` select/status property. The Command
Center contains multiple task databases, so set `NOTION_DATABASE_ID` explicitly
to the intended target. Set `NOTION_TOKEN` through Doppler; no token is stored
in the repository. Run on the machine hosting the FSAD files:

```bash
cd jaios_sync
doppler run -- docker compose up --build -d
```

The Doppler configuration must provide `NOTION_TOKEN` and
`NOTION_DATABASE_ID`. `POLL_INTERVAL_SECONDS` defaults to 30. Docker Compose
bind mounts `jaios_sync/fsad_storage`; mount the actual FSAD directory there
if the canonical files live elsewhere. Keep the container's storage persistent:
`.jaios-sync-state.json` holds the page mappings. On first start existing
Markdown files are scanned. A file rename creates a new mapping, leaving its
old Notion page for manual reconciliation; deletes are never propagated. Notion
edits to the summary text are replaced by the next local Markdown edit.
