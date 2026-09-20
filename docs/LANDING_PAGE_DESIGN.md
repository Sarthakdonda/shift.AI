# Light-theme landing page

Updated 15 September 2026. Reference: [Render's public homepage](https://render.com/), inspected in a browser at desktop size.

The public homepage adapts the reference's editorial layout, fine grid, square buttons, animated product preview, two-direction tile strips, bordered feature panels, and floating closing tiles to shift.AI. White and cream surfaces, orange accents, and the existing shift.AI logo remain. Product content covers discovery, evidence, solution comparison, independent review, architecture, ER models, and implementation blueprints. Illustrations are explicitly examples; no customer endorsements or infrastructure claims are borrowed.

## Scope

- `frontend/app/page.tsx`: server-rendered public page and shift.AI content.
- `frontend/components/landing/render-home.module.css`: scoped responsive styling; no workspace or PDF theme changes.
- `frontend/components/landing/landing-interactions.tsx`: rotating headline, interactive four-stage preview, moving tiles, scroll reveals, and shared motion control.
- `frontend/components/layout/site-header.tsx`: sticky desktop navigation with platform menu and compact mobile navigation.

The preview stops cycling when a visitor focuses or selects a stage. Arrow keys, Home, and End work in the tab list. Escape closes navigation and restores trigger focus. Continuous motion can be paused and respects reduced-motion preferences and document visibility. Content is server-rendered and remains readable without JavaScript. No animation library or new dependency is needed.

## Verification

From `frontend` in PowerShell:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test:e2e
```

Landing coverage lives in the standard browser suite (`frontend/tests/redesign.spec.ts`), which checks the rotating headline, the stage preview, desktop and mobile navigation, FAQ disclosure, logo proportions, reduced-motion behaviour, and horizontal overflow on isolated ports 3011/8011.

During the redesign review, a separate one-off suite additionally exercised paused motion, keyboard-driven stage changes, tile-strip smoothness, no-JavaScript content, and overflow at widths 320, 360, 390, 768, 1024, and 1440 against an isolated production build. That temporary harness, its screenshots, and its build directory have been removed; normal development servers and `.next` were left untouched.

This is a local implementation. Production deployment is a separate step.
