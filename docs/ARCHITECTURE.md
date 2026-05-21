# Accrual Processing Pipeline — Architecture

## What this is

A Python/FastAPI implementation of an enterprise accrual processing pipeline that reads financial data from multiple SAP modules, sends it to Claude for analysis and anomaly detection, and routes the results to appropriate destinations.

This is a functional mirror of an SAP BTP Cloud Integration (CPI) iFlow — same architecture, same data flow, same integration points — implemented in Python so it can run without any SAP tenant or BTP subscription.

## Why this exists

The target production architecture is an SAP CPI iFlow orchestrating reads from S/4HANA (FI, MM, CO modules), calling Claude via SAP's Generative AI Hub, and writing results back. That requires a paid BTP Free Tier subscription with AI Core provisioning, plus a real or sandbox S/4HANA tenant.

This Python version achieves the same architecture by:

- Calling the SAP Business Accelerator Hub sandbox APIs (free, no tenant) for realistic S/4HANA OData payloads
- Calling Claude directly via the Anthropic SDK (bypassing Generative AI Hub)
- Orchestrating with `asyncio` + `httpx` instead of CPI's BPMN runtime

This gives us a working demo with real SAP API response shapes and real Claude processing, with zero SAP infrastructure.

## The 5-stage pipeline

Each stage maps directly to an iFlow step so the design ports cleanly to CPI later.

### Stage 1 — Scheduled trigger

Cron-based or on-demand kickoff. Equivalent to a CPI Timer sender adapter. Exposed as both a FastAPI endpoint (`POST /runs`) and a CLI command (`python -m accrual_pipeline.run`).

### Stage 2 — Parallel OData fetches

Three concurrent async HTTP calls to SAP Business Accelerator Hub sandbox APIs:

- **FI Journal Entries** — operational journal entry items from the accrual subledger
- **MM Purchase Orders** — open POs, service entry sheets, GR/IR data
- **CO Cost Centers** — cost center master data for tagging

Uses `httpx.AsyncClient` with `asyncio.gather`. This is the Python equivalent of CPI's Parallel Multicast step.

### Stage 3 — Normalize + build prompt

Merges the three payloads into unified `AccrualObject` pydantic models keyed by accrual object ID. A prompt template (Jinja2) injects the structured data into system + user prompts for Claude. Equivalent to CPI's Groovy script + Content Modifier.

### Stage 4 — Claude call with tool use

Calls Claude via the Anthropic SDK with a defined tool set for anomaly detection. Tool schemas:

- `flag_stale_po_accrual(po_id, reason, severity)` — POs with SES older than threshold days without an invoice
- `flag_duplicate_accrual(accrual_ids, reason)` — likely-duplicate postings across the dataset
- `approve_accrual(accrual_id, notes)` — clean items that pass review

Equivalent to CPI's AI Adapter → GenAI Hub → Claude path.

### Stage 5 — Route response

Parses Claude's `tool_use` blocks and routes each flagged item:

- **Persist** — all flagged items land in SQLite (dev) or HANA Cloud (prod)
- **Notify** — high-severity flags emit to stdout or local SMTP (dev), email adapter (prod)
- **Post back** — approved accruals invoke a mock "S/4 Journal Entry Post" in dev (logs the intended SOAP payload); real SOAP call in prod

Equivalent to CPI's Router + multi-receiver fan-out.

## Data sources

All OData endpoints are on `sandbox.api.sap.com`. They require an `APIKey` header from api.sap.com (free, one key covers all sandboxes).

| Module | API | Purpose |
|--------|-----|---------|
| FI | Operational Journal Entry Item (A2X) | Accrual postings from ACDOCA |
| MM | Purchase Order | Open POs, line items, SES references |
| CO | Cost Center | Master data for tagging accrual objects |

Exact endpoint paths must be confirmed at implementation time against api.sap.com — SAP rotates sandbox URLs occasionally. Start by searching the Business Accelerator Hub for each API name.

## Claude integration

- Model: `claude-opus-4-7` for production runs, `claude-sonnet-4-6` for cost-sensitive development iteration (config-toggleable)
- SDK: `anthropic` Python package
- Pattern: tool use with defined tool schemas, not free-text responses
- Max tokens: 4096 initial; may need 8192 for multi-tool responses on large datasets
- Retry: SDK built-in retries on 5xx; custom exponential backoff on 429

The prompt template lives in `src/accrual_pipeline/prompts/accrual_analysis.md` so it can be iterated independently of code.

## Key design decisions

**FastAPI over a bare script.** The iFlow is trigger-driven; a `/runs` endpoint mimics that pattern and makes room for monitoring endpoints (`/runs/{id}`, `/health`) without restructuring.

**`httpx.AsyncClient` over `requests` or `aiohttp`.** Parallel fan-out is the entire point of Stage 2. `requests` would serialize the three calls. `aiohttp` works but `httpx`'s API is cleaner and supports sync + async from the same client.

**Pydantic for normalization.** CPI catches schema drift at runtime via message mapping failures. Pydantic catches it at the same boundary — when the OData response hits the model — with clearer error messages and IDE autocomplete as a bonus.

**SQLite for dev persistence.** Matches what a HANA Cloud client would do, without the setup. Swap the SQLAlchemy engine URL to promote to HANA.

**`MOCK_MODE` flag.** Iterating on the Claude prompt without burning sandbox API quota or Claude tokens. When `MOCK_MODE=true`, OData fetchers return fixture JSON from `tests/fixtures/` instead of hitting the network. Claude calls are never mocked — the real SDK runs so prompt iteration is meaningful.

**Tool use over free-text.** Structured tool calls give the router deterministic inputs. Parsing free-text "here are the flagged items" is fragile and defeats the point of using Claude for a batch workflow.

## Project structure

```
accrual-pipeline/
├── README.md
├── pyproject.toml
├── .env.example
├── docs/
│   └── ARCHITECTURE.md        # this file
├── src/accrual_pipeline/
│   ├── __init__.py
│   ├── config.py              # pydantic-settings
│   ├── main.py                # FastAPI app
│   ├── run.py                 # CLI entrypoint
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py            # shared httpx client + auth
│   │   ├── fi.py              # journal entries
│   │   ├── mm.py              # purchase orders
│   │   └── co.py              # cost centers
│   ├── models.py              # pydantic models
│   ├── normalizer.py          # merge + build accrual objects
│   ├── claude_client.py       # Anthropic SDK wrapper + tool schemas
│   ├── prompts/
│   │   └── accrual_analysis.md
│   ├── router.py              # decide persist/notify/postback
│   ├── persistence.py         # SQLAlchemy models + session
│   └── postback.py            # mock S/4 post back (logs the call)
└── tests/
    ├── fixtures/              # sample OData JSON payloads
    ├── test_fetchers.py
    ├── test_normalizer.py
    ├── test_claude_client.py  # mocked Anthropic client
    ├── test_router.py
    └── test_end_to_end.py     # MOCK_MODE=true full pipeline
```

## Running the project

```bash
# Install
uv pip install -e ".[dev]"

# Configure
cp .env.example .env
# edit .env: SAP_API_KEY, ANTHROPIC_API_KEY, MOCK_MODE

# Run once from CLI
python -m accrual_pipeline.run

# Or start the API
uvicorn accrual_pipeline.main:app --reload
curl -X POST http://localhost:8000/runs

# Run tests
pytest
```

## Graduating to real CPI (future phases)

Once the Python version works end-to-end, the same design ports to:

**Path B — BTP Trial (free, 90 days).** Rebuild as a real CPI iFlow using Integration Suite. OData receiver adapters point at the same sandbox URLs. For Claude, use an HTTPS receiver adapter pointing at `api.anthropic.com/v1/messages` directly — no AI Core needed. The Groovy script for normalization mirrors `normalizer.py`.

**Path C — BTP Free Tier (credit card required, free within limits).** Same iFlow, but swap the HTTPS Claude adapter for the AI Adapter (AICore-GenAIHub variant). Adds data masking and the orchestration service on top.

The Python implementation is the reference spec for either port — the normalizer, prompt template, tool schemas, and routing logic all carry over directly.

## References

- **SAP Business Accelerator Hub**: https://api.sap.com
- **Sandbox API guide**: https://help.sap.com/docs/business-accelerator-hub/sap-business-accelerator-hub/trying-out-apis-in-sandbox-environment
- **Anthropic SDK docs**: https://docs.claude.com
- **SAP CPI AI Adapter** (for Path B/C reference): search SAP Community for "AI Adapter Integration Suite"
- **Journal Entry APIs catalog**: search SAP Community for "APIs for Journal Entries collection"
