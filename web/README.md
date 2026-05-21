# web — Accrual Pipeline Dashboard

Next.js 16 App Router UI for the `accrual_pipeline` Python service.

## Stack

- Next.js 16 (App Router, Server Components)
- React 19
- Tailwind CSS v4
- shadcn/ui (neutral base, Radix primitives)
- TypeScript

## How it talks to the backend

Server Components and Server Actions call `lib/api.ts`, which fetches from
the Python FastAPI service. The browser never touches the Python service
directly — all traffic is proxied through the Next.js server, so there are
no CORS headaches and no backend URL in the client bundle.

```
Browser ──► Next.js (server) ──► FastAPI (http://localhost:8000)
```

## Setup

```bash
# From the repo root, bring up the Python backend in one terminal:
.venv/bin/uvicorn accrual_pipeline.main:app --reload --port 8000

# In another terminal, from web/:
cp .env.example .env.local
npm run dev
# → http://localhost:3000
```

## Deploying to Vercel

Set `BACKEND_API_URL` in the Vercel project settings to wherever the
Python service is hosted (a cloud VM, an ngrok tunnel pointing at your
laptop, a deployed container, etc.). The UI otherwise has no backend
requirements.
