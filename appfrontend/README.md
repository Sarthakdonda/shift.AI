# shift.AI app frontend

The phone application surface. This is what the Android shell in `../android`
loads. It is a separate Next.js app from the marketing website in `../frontend`
and shares the same backend, so changing one never affects the other.

## What makes it an app, not a website in a WebView

- **No landing page.** `/` resolves the saved session and goes straight to
  `/chats` or `/login`. There is no marketing route, and `/dashboard` is a 404.
- **A fixed frame.** `html, body { overflow: hidden }`, one `position: fixed`
  frame per screen, and a single inner scroll region. The page itself never
  scrolls, so there is no address-bar shift, no rubber-band bounce, and no
  disappearing composer.
- **Touch-first sizing.** 44–50 px targets, 16 px inputs so Android never
  zooms on focus, `touch-action: manipulation` to remove the double-tap delay,
  and no hover-only affordances.
- **Compositor-only motion.** Every transition animates `transform` and
  `opacity` only, with an iOS-like `cubic-bezier(0.32, 0.72, 0, 1)` curve.
  Long transcripts use `content-visibility: auto`. Scroll position is tracked
  in a ref, not state, so a flick never re-renders the conversation.
- **Native navigation.** A bottom tab bar for the three root screens, push
  transitions for detail screens, bottom sheets instead of desktop dialogs, and
  the Android hardware back button closes a sheet instead of leaving the screen.
- **Skeletons, not spinners,** for anything that has a known shape.
- `prefers-reduced-motion` collapses every animation.

## Screens

| Route | Purpose |
| --- | --- |
| `/` | Session probe and redirect. Shows the boot splash only. |
| `/login`, `/signup` | Email access. Google sign-in needs a full browser and says so. |
| `/forgot-password`, `/reset-password` | Password recovery, same tokens as the website. |
| `/chats` | Projects with search, filters, progress and a compose action. |
| `/new` | Create a project, with fillable examples. |
| `/chat/[id]` | The conversation. Discovery questions render in the answer surface. |
| `/chat/[id]/documents` | Upload, processing status, extracted facts, removal. |
| `/chat/[id]/report` | Diagnosis, Solution, Red Team and Blueprint in a segmented view, with share and PDF/DOCX download. |
| `/settings` | Account, workspace counts, connection status, sign out. |

## The discovery question design

A question is one block — numbered label, topic, the question, why it is being
asked, and an optional hint — rendered by `components/chat/question.tsx`. The
same block appears in the transcript for answered questions and inside the
composer for the open one, where the composer becomes the answer surface and
`Send` is replaced by an explicit **Submit answer**. A question never looks like
two different things.

## Run it

```powershell
cd appfrontend
Copy-Item .env.local.example .env.local
npm.cmd ci
npm.cmd run dev
```

Open <http://localhost:3100>. The API base defaults to `http://localhost:8000`
and is rewritten to the serving host on a phone, so Wi-Fi works without extra
configuration. The backend must allow `http://localhost:3100` in
`CORS_ORIGINS`; that is the shipped default.

For the phone over Wi-Fi, use `start-wifi.cmd` in the repository root, which
starts the backend with `--lan` and this app on `0.0.0.0:3100`.

## Verification

```powershell
npm.cmd run typecheck
npm.cmd run lint
$env:SHIFT_TEST_BUILD_DIR='.next-verify'; npm.cmd run build
```

`SHIFT_TEST_BUILD_DIR` keeps a verification build out of the `.next` directory a
running dev server owns.

## Dependencies

Next, React, `lucide-react` icons and locally served Inter. No utility CSS
framework and no component library: the design system is hand-written CSS in
`app/styles/` so the shell parses as little as possible at startup.
