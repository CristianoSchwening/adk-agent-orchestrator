---
name: React build pipeline
description: How to build and deploy the webapp-react app in this project
---

The React app lives in `webapp-react/` and is served by FastAPI at `/app`.

**Build command:** `npm --prefix webapp-react run build`
- Runs `tsc -b && vite build`
- Output goes to `webapp-react/dist/`
- FastAPI mounts `webapp-react/dist` with `StaticFiles(html=True)` at `/app`

**After build:** Restart the `Start application` workflow to pick up the new dist.

**Install packages:** `npm --prefix webapp-react install <pkg>` (never `cd webapp-react && npm install`)

**Path alias:** `@/` resolves to `./src/` via both `vite.config.ts` and `tsconfig.app.json`.
