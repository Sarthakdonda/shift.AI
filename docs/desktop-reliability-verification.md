# Desktop and generation reliability — 10 September 2026

Implemented the [desktop design brief](desktop-design-brief.md): a lighter sidebar, calmer dashboard and forms, consistent navigation, compact brand marks, refined desktop spacing and a usage panel beside the composer. Layout redesign is scoped to desktop.

Prompt submission now adds the message immediately and clears the input. Stop and Escape cancel the server generation, preserve the saved message, release the project and discard a late provider result. Cancellation also covers automatic analysis after discovery. An already submitted provider request may still consume quota.

Failover keeps the chosen model and can reach all configured keys, including the ninth connection. Quota cooldowns are tracked per model; credential cooldowns apply to the whole key. Provider and database errors retain their specific safe explanations. Usage shows connection availability and retry timing; exact remaining requests and quota refill times are explicitly unavailable and linked to AI Studio.

## Evidence

- 115 backend tests passed, including ninth-key failover, model preservation, quota isolation, cooldown expiry, cancellation before start, in-flight cancellation, automatic-analysis cancellation, late-result rejection and project authorization.
- All 19 desktop Playwright scenarios passed across the targeted runs. Coverage includes immediate submission, Stop, Escape, retry without duplication, usage, sidebar search/collapse, model selection, conversation scrolling, context, voice controls, authentication, forms, discovery, documents, analysis, deliverables, approval and export.
- TypeScript, ESLint, production Next.js build and Git whitespace checks passed. ESLint now excludes generated browser reports.
- Desktop screenshots inspected at 1440×1000 and 1920×1080. Final wide-page checks reported no browser page errors or horizontal overflow. A logo overflow found during review was corrected and its browser test passed.
- Live read-only checks explicitly loaded this project's `backend/.env`, matching the local launcher. MongoDB connected; the screenshot's saved project was found; its Gemini 3.8 Flash selection generated a small test response successfully. Nine configured connections were detected. No credentials or project contents were printed; no live project data was changed.

The earlier backend log contains a database initialization timeout. The frontend's previous generic 5xx message did not establish whether the screenshot's failure was quota-related. Current successful connectivity checks do not prove uninterrupted future service. Google project quotas are shared across that project's API keys.

Temporary test builds, screenshots and browser reports were removed after review. Existing projects, environment files and prior workspace changes were preserved. Test ports 3011 and 8011 were closed. The user's subsequent instruction supersedes the original cleanup rule: leave regular servers on 3000 and 8000 running, and stop only agent-created test servers.

The desktop styles were folded into the already loaded discovery stylesheet after the normal development server reported a stale import-resolution error for the newly created `desktop.css`. Verification builds now use a separate output directory to avoid interfering with the user's `.next` development cache.
