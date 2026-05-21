# accrual-pipeline

Python/FastAPI mirror of an SAP BTP Cloud Integration (CPI) iFlow for accrual
processing. Reads FI/MM/CO data from the SAP Business Accelerator Hub sandbox
APIs, sends it to Claude for anomaly detection via tool use, and routes
flagged items to persistence / notification / postback.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design — the
five-stage pipeline, data sources, and CPI port path.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for package management
- SAP Business Accelerator Hub API key — free, from <https://api.sap.com>
- Anthropic API key — from <https://console.anthropic.com>

## Setup

```bash
# Create a virtualenv and install with dev extras
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env and set SAP_API_KEY + ANTHROPIC_API_KEY.
# MOCK_MODE=true by default — fetchers serve fixtures instead of hitting
# the SAP sandbox. Claude calls are never mocked.
```

## Run

```bash
# FastAPI server
uvicorn accrual_pipeline.main:app --reload
curl http://localhost:8000/health

# CLI (wired in Phase 5)
python -m accrual_pipeline.run

# Tests
pytest

# Type check
mypy
```

## Layout

```
src/accrual_pipeline/
├── config.py              # pydantic-settings
├── main.py                # FastAPI app
├── run.py                 # CLI entrypoint
├── models.py              # pydantic models (AccrualObject etc.)
├── fetchers/              # FI / MM / CO OData clients
│   ├── base.py            # shared httpx client factory
│   ├── fi.py              # journal entries
│   ├── mm.py              # purchase orders
│   └── co.py              # cost centers
├── normalizer.py          # merge fetcher outputs → AccrualObject
├── claude_client.py       # Anthropic SDK wrapper + tool schemas
├── prompts/               # Jinja2 prompt templates
│   └── accrual_analysis.md
├── router.py              # route tool_use blocks
├── persistence.py         # SQLAlchemy models
└── postback.py            # mock S/4 post back
```

## Build status

Phase 1 — skeleton only. Modules are stubbed; see `docs/ARCHITECTURE.md` for
the phased build plan.
