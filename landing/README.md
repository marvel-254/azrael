# azrael landing

Static marketing site for [azrael](https://azrael.vercel.app) — a TUI + GUI monitor and resource controller for AI agent harnesses.

## Develop

```bash
npm install
npm run dev    # http://localhost:4321
```

## Build

```bash
npm run build  # outputs to ./dist
npm run preview
```

## Deploy

Pushed to `main` (with `landing/**` changes) by `.github/workflows/landing.yml` to Vercel at <https://azrael.vercel.app>.
