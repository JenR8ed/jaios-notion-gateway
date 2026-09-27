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