# Verification record

Verified locally on Windows with Node.js 22.18.0 and Python 3.13.7.

| Check | Result | Scope |
| --- | --- | --- |
| Backend tests | 41 passed | Original workflow coverage plus key fallback, cooldowns, RetryInfo handling, bounded exhaustion, authentication failures, embedding fallback, and backup-only configuration |
| Live key fallback | Passed | Simulated a quota error on the first configured credential; the next credential completed real structured generation |
| Browser tests | 4 passed | Complete desktop and mobile workflows, reload persistence, uploads, analysis, blueprint download, deletion, configuration errors, setup/login screens, horizontal overflow |
| TypeScript | Passed | Strict frontend type checking |
| ESLint | Passed | Frontend lint, no errors or warnings |
| Next.js production build | Passed | All routes compile and production assets generate |
| MongoDB Atlas connection | Passed, live | Authenticated connection and required collection indexes |
| Atlas persistence | Passed, live | Project/messages read through an independent MongoClient connection; temporary verification data deleted |
| Dependency audit | No npm vulnerabilities reported at installation | Installed dependency tree |
| Secret handling | Verified | Real `.env` files excluded from Git; only placeholder templates committed |
| Visual review | Completed | Desktop landing/workspace and mobile layout inspected from Chromium screenshots |

The Python test runner emits one upstream Starlette/AnyIO deprecation warning. It does not affect test results.

## What requires your credentials

- **Live Gemini connectivity verified:** the primary key passed a structured generation request, and both supplied backup credentials passed individual generation requests. Local configuration uses `gemini-3.6-flash` because Google rejected the previous default for this account. Full business-analysis quality remains unverified with live models; workflow tests use a deterministic provider substitute.
- **Live Google account sign-in has not been tested:** no Google OAuth client ID was supplied. Server-side verification, nonce matching, signed cookies, origin checks, and ownership rules were tested with mocked Google verification. Configure the Web application client and its JavaScript origin as described in the root README.
- **Atlas Vector Search is optional and disabled by default:** no vector index was provisioned. Keyword retrieval works without one. The optional embedding/search integration requires the documented Atlas index and a Gemini key.

## Practical limits

- Analysis and document processing run as local background jobs with saved stage updates. An interrupted job is retryable after its 30-minute operation lease expires; it does not automatically continue from an exact graph checkpoint.
- Original document bytes are not retained. Scanned PDFs need OCR before upload. File/character/row limits are documented in the root README.
- AI necessity and feasibility scores are advisory. Business-value assumptions and unresolved review findings are shown explicitly.
- Google accounts use separate projects. Local workspace projects are not silently migrated into a Google account.

No deployment or hosting was attempted, in accordance with the supplied SRS.
