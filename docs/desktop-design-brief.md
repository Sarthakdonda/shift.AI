# shift.AI desktop design master prompt

Design shift.AI as a calm, professional workspace for making business decisions. Preserve the established conversation layout and orange identity, while bringing the surrounding desktop experience to the same standard. Prioritize clear hierarchy, readable text, reliable interaction and restrained detail over decoration.

Use a warm neutral navigation surface, white content, charcoal text and a small amount of burnt orange for selection and primary actions. Give the sidebar a compact, correctly proportioned brand lockup, a clear new-conversation action, searchable recent conversations, distinct project tools and a quiet account footer. Align icons, labels and hit areas on a consistent grid. Keep secondary text readable. Make the collapsed rail equally usable.

Use generous but purposeful page margins, a consistent type scale, soft one-pixel borders and subtle elevation only for interactive floating surfaces. Refine dashboard, project creation, documents, reports, settings and workspace screens through shared desktop styles. Avoid oversized promotional panels competing with saved work. Keep the chat transcript and composer as the primary focus.

On Enter, immediately move the submitted text into the transcript and clear the field. Show thinking below that message. Replace Send with a square Stop button during generation; Escape performs the same action. Preserve saved messages, prevent late responses from appearing after cancellation, and allow the next prompt. Retry must actually retry the saved request without duplicating it.

Show an unobtrusive usage indicator beside the composer with an expandable explanation of available API connections and known cooldowns. Never fabricate quota totals or reset times. Keep the chosen model across credential failover. Distinguish quota, credentials, unavailable models, network failures and database failures in user-facing messages.

Keep keyboard focus visible, use accessible labels and reduced-motion support, and limit transitions to approximately 150–200 ms. Scope layout redesign to desktop; preserve existing mobile layout. Match logo-mark height to the adjacent wordmark everywhere.

Acceptance: verify desktop at 1440×1000 and 1920×1080, expanded/collapsed sidebar, immediate submission, Stop and Escape, retries, quota cooldown display, model retention and saved-project preservation. Stop all test servers afterward.

## References

- [Linear's UI redesign](https://linear.app/now/how-we-redesigned-the-linear-ui): alignment, visual hierarchy and quieter navigation.
- [Linear's calmer interface](https://linear.app/now/behind-the-latest-design-refresh): softer separation and restrained icon treatment.
- User-provided ChatGPT screenshot: composer Stop control and message-first submission behavior.
- [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): quotas apply per project, not per API key; actual limits depend on tier and are available in AI Studio.
