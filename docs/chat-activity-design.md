# Chat identity and activity copy

Use the existing shift.AI symbol at 21px high, with no orange tile, star, adjacent wordmark or repeated Discovery badge. Completed replies keep the symbol and timestamp; the enclosing article has an accessible "Assistant response" label. The conversation welcome state uses the same asset at 36px high.

During work, keep the small logo stationary beside one short activity label. Apply a gentle 2.2-second fade only to the text, with no blinking dots or logo animation. Keep the text legible at the dimmest point and disable animation for reduced-motion preferences. Completed replies retain their small logo. Do not invent a timed sequence of internal thoughts, tool calls or debugging steps.

| Observed state | Visible label |
| --- | --- |
| Discovery request, reasoning enabled | Thinking… |
| Discovery request, Instant mode | Preparing your reply… |
| File upload | Uploading document… |
| Document analysis | Reading documents… |
| Analysis queued | Preparing analysis… |
| System analysis | Analyzing your workflow… |
| AI necessity assessment | Evaluating whether AI is needed… |
| Solution generation | Developing your solution… |
| Red Team review | Reviewing risks and assumptions… |
| Business value | Assessing business value… |
| Cancellation requested | Stopping response… |
| Other active work | Working… |

Poll while the generation request is active, including before the first busy state arrives. Server workflow stages take precedence over the initial generic action label. Completion, cancellation and failure remove the active indicator through the existing request lifecycle. The app currently reports workflow activities, not model-generated reasoning summaries.

References reviewed:

- [Anthropic: visible extended thinking](https://www.anthropic.com/news/visible-extended-thinking): reasoning/progress appears separately from the final answer.
- [Claude API: extended thinking](https://platform.claude.com/docs/en/docs/build-with-claude/extended-thinking): surfaced thinking can be summarized; it should not be confused with a fabricated transcript of internal reasoning.
- User-provided screenshot: replace the star tile and repeated name with the product's small standalone mark.

Verification: desktop browser checks passed for the standalone brand mark, live workflow label changes while a request remains pending, final reply headers, and Stop/Escape cancellation. The desktop screenshots were visually reviewed. ESLint and an isolated production build (including TypeScript) passed. Temporary test output was removed; only isolated test servers were stopped.
