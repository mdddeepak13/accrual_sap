# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo layout — two services in one repo

- **`src/accrual_pipeline/`** — Python 3.11+ FastAPI backend. Mirrors an SAP BTP CPI iFlow that reads FI/MM/CO data, sends it to Claude for anomaly detection via tool use, and routes the response. Deployed to Vercel as `accrual_sap_backend` (https://accrualsap.vercel.app) via `api/index.py` + `vercel.json`.
- **`web/`** — Next.js 16 (App Router) + React 19 dashboard + AI-SDK chat agent. Deployed to Vercel. The browser never talks to FastAPI directly; Server Components and Server Actions in `web/lib/api.ts` proxy through the Next.js server (`BACKEND_API_URL` env var).

The two parts share concepts (accruals, runs) but no code. They are developed, tested, and deployed independently. See `docs/ARCHITECTURE.md` for the full pipeline design — keep it in sync if you change Stage 1–5 boundaries.

## Common commands

### Backend (run from repo root)

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env   # then fill in SAP_API_KEY + ANTHROPIC_API_KEY

# Dev server
uvicorn accrual_pipeline.main:app --reload --port 8000

# CLI — runs the full pipeline once and prints a summary
python -m accrual_pipeline.run

# Tests (pytest-asyncio is in auto mode; do not add @pytest.mark.asyncio)
pytest
pytest tests/test_router.py::test_specific_case   # single test

# Type check (strict mode is on; both pydantic-mypy plugin + respx override active)
mypy
```

### Web (run from `web/`)

```bash
npm run dev       # http://localhost:3000 — assumes FastAPI on :8000
npm run build
npm run lint      # eslint v9 flat config (eslint.config.mjs)
```

There is no test suite for `web/`.

## Architecture notes that aren't obvious from a single file

### The 5-stage pipeline lives in `pipeline.py`

`run_pipeline(run_id, anthropic_client=None)` is the single orchestration entrypoint. Both `POST /runs` (background task) and the CLI (`run.py`) call it. The stages:

1. `fetchers/fi.py`, `mm.py`, `co.py` — three concurrent OData fetches via `asyncio.gather` against `sandbox.api.sap.com`.
2. `normalizer.normalize(fi, mm, co)` — merges into `list[AccrualObject]` keyed by accrual_id.
3. `claude_client.analyze_accruals(...)` — Jinja2-renders `prompts/accrual_analysis.md`, calls Anthropic with `TOOL_SCHEMAS`, returns parsed `ToolCall`s.
4. `router.route(...)` — dispatches each tool_use block (`flag_stale_po_accrual`, `flag_duplicate_accrual`, `approve_accrual`) to persistence + `postback.py` (mock S/4 SOAP Journal Entry Post — logs "WOULD CALL" envelopes, no network).

If you add a new tool, you must update **three** places consistently: the schema in `claude_client.TOOL_SCHEMAS`, the prompt in `prompts/accrual_analysis.md`, and a dispatch branch in `router.route` (unknown tools raise `ValueError` — silent drops are intentionally not allowed).

### Sibling data sources outside the pipeline

`inventory.py` and `plan.py` are **not** part of `run_pipeline`. They back the `GET /inventory/batches` and `GET /plan` endpoints, which exist purely so the chat agent (`web/agent/accrual-agent.ts`) can answer questions like "distressed pharma batches?" or "actuals vs Q1 plan?". `inventory.py` hits SAP `API_BATCH_SRV` (or MOCK_MODE fixture `tests/fixtures/inventory_batches.json`); `plan.py` is fixture-only because the SAP sandbox has no plan cube matching our demo cost centers. Both are read-only — they don't write to the runs/accruals tables.

### Payroll: a second Claude call inside the pipeline

`run_pipeline` makes **two** independent Claude calls per run: the existing FI/MM/CO accrual analysis, and a Workday↔SAP-FI payroll reconciliation. They have separate prompts, separate tool schemas, and separate router dispatch — but they share the `FlaggedItem`/`ApprovedItem` persistence tables, distinguished by `tool_name`.

- **Two sides, two pay periods.** `fetchers/payroll.py` returns both the Workday `Get_Payroll_Results` SOAP response (`fetch_workday_payroll_results`) and the SAP FI lines PECI is supposed to have posted (`fetch_peci_fi_lines`). The live Workday path is a hand-rolled SOAP envelope + WS-Security UsernameToken; it's stubbed (`NotImplementedError`) until a real tenant is wired up. **The demo never leaves `MOCK_MODE=true`** — there's no Workday developer tenant.
- **Bi-weekly accrual scenario.** `tests/fixtures/workday_payroll_results.json` (20 US employees, `BIWEEKLY-US-CORP`) holds **40 Pay_Result records** — one per worker per bi-weekly period: Period 1 = 2026-05-04 → 2026-05-17 (pay date 2026-05-22), Period 2 = 2026-05-18 → 2026-05-31 (pay date 2026-06-05). `tests/fixtures/fi_payroll_lines.json` (81 OData lines) carries **Period 1's FI posting only** — Period 2 is unposted as of the demo date 2026-05-25, so its `accrual_variance_to_post` per row equals the full bi-weekly cost and the sum across rows IS the accrual the close team books. Both fixtures are regenerated by `tests/fixtures/generate_payroll.py` with `random.seed(42)`. **Workforce events**: EMP-1003 starts 2026-05-10 (5 days in P1), EMP-1010 resigns 2026-05-20 (3 days in P2, status="Terminated"), EMP-1015 takes 3 days leave during P1. **Six anomalies seeded on the P1 FI side**: wrong CC (CC-9999) on EMP-1005, wrong GL (50130000 instead of 50100000) on EMP-1007, missing FI posting on EMP-1012, duplicate FI posting on EMP-1017, employer FICA under-posted by $75 on EMP-1019, phantom worker EMP-9999 in FI with no Workday match.
- **Join key.** `(Pay_Group_Reference, Pay_Period_End_Date, Worker_Reference)`. PECI populates the same triple on FI lines as custom fields `PayGroupReference` / `PayPeriodEndDate` / `WorkerReference` — those are declared on `FIJournalEntry` but only populated for `AccountingDocumentType="PY"` lines. `normalizer.normalize_payroll` produces one `PayrollAccrualReconciliation` per Workday record; `find_orphaned_fi_payroll_lines` returns FI postings with no Workday counterpart (phantom payroll postings — Claude flags those with `mismatch_type="missing_in_workday"`).
- **Adding a new payroll tool needs the same three-place update** as the FI side: schema in `claude_client.PAYROLL_TOOL_SCHEMAS`, instruction in `prompts/payroll_analysis.md`, dispatch branch in `router.route_payroll` (unknown tools raise `ValueError`). The current tools are `flag_payroll_accrual_mismatch` (with a `mismatch_type` enum) and `approve_payroll_accrual`.
- **No S/4 postback for approved payroll.** PECI is the system of record for payroll postings; by the time we reconcile, the entries are already in FI. `route_payroll._handle_payroll_approve` just records the approval — it does not call `postback.post_journal_entry`.
- **payroll_id format**: `WD/{pay_group}/{period_end_iso}/{worker_id}`, e.g. `WD/BIWEEKLY-US-CORP/2026-05-17/EMP-1019`. This is stored in the `FlaggedItem.accrual_id` column for payroll flags — so a single SQL query can't distinguish FI vs payroll rows by `accrual_id` shape alone; filter by `tool_name`. The UI's run-detail page (`web/app/runs/[runId]/page.tsx`) uses a TS type predicate to split the union.
- **The UI types are a discriminated union.** `FlaggedItem` in `web/lib/types.ts` is `FlaggedAccrualItem | FlaggedPayrollItem`, discriminated by `tool_name`. The snapshot field `accrual` carries different shapes on each — `Accrual` (the 13-field FI object) or `PayrollAccrualReconciliation` (Workday-vs-FI totals). Don't widen this back to a single type; the page filters explicitly on `tool_name` to render the right table.

The chat agent exposes `getPayrollResults` against `GET /payroll/results`, which runs the fetch + normalize on demand (no Claude call, no persistence) — same query-time pattern as `/accruals`, `/inventory/batches`, `/plan`.

### `MOCK_MODE` and fixtures

`MOCK_MODE=true` (default in `.env.example` and the Dockerfile) makes the FI/MM/CO fetchers serve JSON from `tests/fixtures/` instead of hitting the SAP sandbox. **Claude calls are never mocked at runtime** — the real Anthropic SDK runs so prompt iteration is meaningful. Tests inject a fake `AsyncAnthropic` via the `anthropic_client=` parameter of `run_pipeline`.

`fetchers/base.py` resolves the fixture dir via `Path(__file__).resolve().parents[3] / "tests" / "fixtures"`. The Dockerfile copies `tests/` into the image and `.dockerignore` excludes `tests/test_*.py` but keeps `tests/fixtures/` — don't change one without the other or production breaks in MOCK_MODE.

### Prompt template split

`prompts/accrual_analysis.md` and `prompts/payroll_analysis.md` each contain both the system and user prompt, separated by the literal line `---USER---` (defined as `_SYSTEM_USER_DELIM` in `claude_client.py`). The two halves are loaded and rendered as separate Jinja2 templates that share the same context dict — for accrual it's `accruals` / `today` / `stale_days_threshold` / `duplicate_days_window` / `run_id`; for payroll it's `reconciliations` / `orphan_fi_lines` / `today` / `run_id`. Editing the marker breaks loading. A pre-rendered copy of the payroll prompt (for human review) lives at `docs/prompts/payroll_analysis.md`; that copy is informational — the runtime reads from `src/`.

### Persistence

`persistence.py` uses a **sync** SQLAlchemy engine even though the rest of the code is async — write volume is tiny and async-SA isn't worth the complexity. The engine is created lazily via `init_db()`; tests call `reset_db()` to force a rebuild. `DATABASE_URL=sqlite:///./accrual.db` for dev; the same code switches to HANA by changing the URL only.

`record_run_start` is **idempotent**. The POST `/runs` endpoint inserts the row synchronously before kicking off the background task so an immediate follow-up GET `/runs/{id}` doesn't 404; `run_pipeline` calls it again from the CLI path. Both must work.

`accrual_snapshot_json` on flagged/approved rows freezes the business fields at decision time so the UI can render without re-joining FI/MM/CO. Keep that snapshot in sync with `AccrualObject` if you add fields the UI needs.

### Background task lifetime

`main._background_tasks: set[asyncio.Task]` holds strong refs to in-flight pipeline tasks so the event loop doesn't GC them mid-run. Tasks self-remove via `add_done_callback`. They survive client disconnects but not process restarts — production would swap in a real queue.

### Settings

`config.get_settings()` is `@lru_cache(maxsize=1)`. It re-reads env only on process restart. Don't mutate `Settings` instances at runtime — pass overrides as function args. Secrets are `SecretStr`; call `.get_secret_value()` only at the boundary that hands the value to a client.

### Web ↔ Backend boundary

`web/lib/api.ts` is the only file in `web/` that knows the backend URL. It uses `process.env.BACKEND_API_URL || "http://localhost:8000"` — the `||` (not `??`) fallback is intentional so an empty-string env var (which Vercel has shipped before) also falls back.

The chat agent (`web/agent/accrual-agent.ts`) hits the backend's `/accruals`, `/plan`, `/inventory/batches`, `/runs` endpoints as tools. If you add a new backend endpoint, expose it through both `lib/api.ts` (for UI) and as a `tool({...})` in the agent (for chat).

## Conventions

- **Async everywhere in `accrual_pipeline`** except persistence (deliberate — see above). Don't call `requests`; use the `httpx.AsyncClient` from `fetchers/base.create_sap_client()`.
- **Tool use over free-text from Claude.** All structured output goes through `TOOL_SCHEMAS`. Don't parse free-text responses.
- **`from __future__ import annotations`** is at the top of every Python module. Keep it.
- **`structlog` for logging**, not stdlib `logging`. Use kwarg fields, not f-strings: `log.info("pipeline.start", run_id=run_id)`.
- **`web/` runs on Next.js 16** — `web/AGENTS.md` warns that APIs and conventions may differ from training-data Next.js. Read `node_modules/next/dist/docs/` (or current docs) before guessing.

## Deployment

Both backend and frontend deploy to Vercel under Deepak's account (`deepaks-projects-9bb7e3f1`).

- **Backend** — Vercel project `accrual_sap_backend` at https://accrualsap.vercel.app. Built from `api/index.py` + `vercel.json` + root `requirements.txt`. `api/index.py` adds `src/` to `sys.path` and re-exports `accrual_pipeline.main.app`; `vercel.json` rewrites all paths to `/api/index` so the FastAPI app sees raw URLs. Root `requirements.txt` is what Vercel installs — keep it in sync with `pyproject.toml` runtime deps. `.vercelignore` excludes `.env` because pydantic-settings reads it at runtime and would silently shadow `vercel env add` values. Deploy from repo root: `vercel --prod`.
- **Frontend** — Vercel project `accural_sap_frontend` at https://accuralsap.vercel.app (note the typo in the URL). `BACKEND_API_URL` env var points at the backend project's URL. Deploy from `web/`: `vercel --prod`.

## Not a git repository

This working directory is not under git (`Is a git repository: false`). `git log` / `git blame` won't work. Don't recommend git-based workflows unless the user initializes a repo first.
