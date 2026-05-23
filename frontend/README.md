# CareerAI Frontend (Vue 3 + Vite)

This directory holds the Vue 3 source for the four authenticated pages
(`/`, `/career`, `/job`, `/interview`). The login page (`/login`) is
intentionally still a plain HTML template rendered by Flask and is **not**
part of this build.

## Quick start

```bash
cd frontend
npm install
npm run build      # produces ../static/dist/<page>.{js,css}
```

Then run the Flask app as usual:

```bash
python web_app.py
```

The Flask templates ([template/index.html](../template/index.html), etc.)
load the built bundles from `/static/dist/`. The login page is unchanged.

## Development mode

```bash
npm run dev        # Vite at http://127.0.0.1:5173 with /api proxied to 5000
```

In dev mode you should still keep `python web_app.py` running on port 5000
so that `/api/*` calls work.

## Layout

```
frontend/
├── pages/                    Vite multi-page entry HTML (dev only)
├── src/
│   ├── entries/              one main.js per page
│   ├── apps/                 root SFCs per page (HomeApp, CareerApp, ...)
│   ├── components/           shared SFCs
│   ├── composables/          reusable hooks (status, timer, SSE, ...)
│   ├── api/                  fetch wrappers for /api/* endpoints
│   └── utils/                escapeHtml, markdown rendering, formatters
└── vite.config.js            multi-entry build → ../static/dist/
```

## Style policy

All visual styling continues to live in [../static/style/](../static/style/)
and is loaded by the Flask templates via `<link rel="stylesheet">`. Vue
components only render the same markup with the same `class` names, so the
UI is preserved as-is.
