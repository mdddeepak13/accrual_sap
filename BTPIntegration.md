# SAP BTP Integration — Deploying a Mock `API_BATCH_SRV` on BTP Cloud Foundry

Sister doc to [`AccrualSourceData.md`](AccrualSourceData.md). This is the option-C playbook: stand up a real SAP-managed OData service on SAP BTP that mimics `API_BATCH_SRV/Batch`, seed it with the 100-distressed-pharma-batch fixture, and point the accrual backend at it.

The accrual backend code does **not change**. Only one env var moves (`SAP_SANDBOX_BASE_URL`) and `MOCK_MODE` stays `false`.

This guide records the configuration that actually worked after we shook out several BTP-trial-specific gotchas. The trial-account constraints (no `hdi-shared` containers, no `cf ssh`, tight route quota) drove most of the design choices below.

## Goal

End state:

```
[Vercel] accrual_sap_backend (accrualsap.vercel.app)
   │
   │  GET /s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV/Batch
   ▼
[BTP Cloud Foundry] mocksap-srv.cfapps.us10-001.hana.ondemand.com
   │
   ▼
in-memory SQLite (seeded from bundled CSV on startup)
```

The wire format the accrual backend sees is genuine SAP — TLS, `*.hana.ondemand.com` host, OData V4 JSON envelope, `Batch` PascalCase fields — but the data is yours.

## Pick the BTP flavor

| | Trial | Free Tier (recommended for keeping the demo) |
|---|---|---|
| Lifespan | 90 days then deletion; 30-day inactivity → deletion | Indefinite |
| Convertible to paid later | No | Yes |
| `hdi-shared` HANA Cloud plan | **Not entitled** (since early 2026, paid-only) | Same restriction |
| Cloud Foundry runtime | Included | Included |
| `hana-free` HANA Cloud plan | Available, auto-stops 12h idle | Available |

Either works for the demo. Free Tier survives quarterly demos; Trial expires at 90 days.

Important: **don't plan on HANA Cloud HDI containers**. Both trial and free tier give you a HANA Cloud instance via the `hana-free` plan but not auto-provisioned HDI schemas. The clean path is in-memory SQLite inside the CAP container, with the CSV bundled into the deploy artifact.

## Step 1 — Create a free SAP BTP account

1. Use any existing SAP.com account, or create one at https://account.sap.com/core/account/register.
2. Go to https://www.sap.com/products/technology-platform/pricing.html → "Free Tier" → "Get a Free Account".
3. Pick a region. **AWS `us-east-1` (US10)** is closest to Vercel `iad1`.
4. Wait ~5 minutes for provisioning.

## Step 2 — Configure the subaccount

In the BTP cockpit (https://account.hana.ondemand.com/):

1. Open the global account → **Create Subaccount** (a directory is optional).
   - Name: `accrual-demo`
   - Region: `us10`
2. Inside the subaccount, **Enable Cloud Foundry** environment. Org name and space `dev` are fine.
3. **Entitlements → Configure Entitlements** — add only the free plans you actually need:
   - `Cloud Foundry Runtime` → `free`
   - That's it. No `xsuaa` (we run no-auth). No HANA Cloud (we use in-memory SQLite).

Note on quotas — trial accounts get **one auto-created suborg** (`af3d148dtrial_accrual-demo-<random>`) with a route quota of 0, and the parent default org `af3d148dtrial` with a normal route quota. Deploy to the parent org. If you see "Routes quota exceeded", `cf target -o af3d148dtrial -s dev` and retry.

## Step 3 — Install local toolchain

```bash
# Node 20+ (CAP 9 needs 20 LTS or 22+)
node --version

# Cloud Foundry CLI v8
brew install cloudfoundry/tap/cf-cli@8

# MultiApps plugin (provides cf deploy for MTA archives — not built-in)
cf install-plugin -r CF-Community "multiapps" -f

# Cloud MTA Build Tool
npm i -g mbt

# CAP development kit
npm i -g @sap/cds-dk
```

Sanity check:

```bash
cds --version          # expect cds-dk: 9.x.x
cf --version           # expect cf version 8.x
cf plugins | grep -i multi   # expect multiapps plugin listed
mbt --version          # expect Cloud MTA Build Tool 1.2.x
```

## Step 4 — Scaffold the CAP project

```bash
# From the repo root
cds init mocksap --add typescript
cd mocksap
npm install
npm install --save-dev @cap-js/sqlite
```

Skip `--add xsuaa,destination` — we don't use them for this no-auth demo. `@cap-js/sqlite` is required even for local dev (without it `cds watch` returns `NO_DATABASE_CONNECTION`).

Then edit `package.json` so it looks like this (full file shown for clarity):

```json
{
  "devDependencies": {
    "@cap-js/cds-typer": ">=0.1",
    "@cap-js/cds-types": "^0.16.0",
    "@sap/cds-dk": "^9",
    "@types/node": "^24.0.0",
    "tsx": "^4",
    "typescript": "^6.0.0"
  },
  "imports": {
    "#cds-models/*": "./@cds-models/*/index.js"
  },
  "dependencies": {
    "@sap/cds": "^9",
    "@cap-js/sqlite": "^2.4.0"
  },
  "scripts": {
    "start": "cds-serve"
  },
  "cds": {
    "requires": {
      "db": {
        "kind": "sqlite",
        "credentials": { "url": ":memory:" },
        "[production]": {
          "kind": "sqlite",
          "credentials": { "url": ":memory:" }
        }
      },
      "auth": {
        "kind": "dummy",
        "[production]": { "kind": "dummy" }
      }
    }
  },
  "engines": {
    "node": ">=20"
  }
}
```

Three things in there that the default `cds init` doesn't produce, all of which matter for production:

- **`"@sap/cds"` in `dependencies`** — `@cap-js/sqlite` only declares it as a peer, and the Cloud Foundry Node buildpack strips devDeps, so without this the runtime can't find `cds` at startup.
- **`"scripts.start": "cds-serve"`** — the CF Node buildpack defaults to `npm start`. Without a `start` script it crashes with `npm error Missing script: "start"`.
- **`"auth": { "kind": "dummy" }`** — CAP's production default is JWT auth via `@sap/xssec`. With no `xsuaa` binding installed, that path crashes at startup with `Cannot find module '@sap/xssec'`. `kind: "dummy"` disables auth for a public read-only demo.

Run `npm install` again after this edit to sync the lock file.

## Step 5 — Define the entity matching `API_BATCH_SRV/Batch`

The accrual backend reads PascalCase SAP field names via `_FIELD_MAP` in `src/accrual_pipeline/inventory.py:66-83`. The CAP entity uses those exact names so no backend code changes.

### `mocksap/db/schema.cds`

```cds
namespace sap.s4.batch;

entity Batch {
  key Batch                       : String(10);
      Material                    : String(40);
      MaterialDescription         : String(60);
      TherapeuticCategory         : String(20);
      BatchIdentifyingPlant       : String(4);
      PlantName                   : String(40);
      ShelfLifeExpirationDate     : Date;
      ManufactureDate             : Date;
      LastGoodsReceiptDate        : Date;
      BatchIsMarkedForDeletion    : Boolean default false;
      MatlBatchIsInRstrcdUseStock : Boolean default false;
      Supplier                    : String(10);
      SupplierName                : String(40);
      CountryOfOrigin             : String(3);
      Quantity                    : Decimal(15, 3);
      BaseUnit                    : String(3);
}
```

### `mocksap/srv/api-batch-srv.cds`

The accrual backend expects the OData service at `/s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV` (see `src/accrual_pipeline/inventory.py:35`). Set that as the service `@path` directly — no approuter rewrite needed.

```cds
using sap.s4.batch from '../db/schema';

@path: '/s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV'
service API_BATCH_SRV {
  entity Batch as projection on batch.Batch;
}
```

### `mocksap/srv/api-batch-srv.ts`

CAP auto-discovers handlers by filename match (no `@(impl: ...)` annotation needed).

```ts
import cds from '@sap/cds';

export default cds.service.impl(function () {
  this.before(['CREATE', 'UPDATE', 'DELETE'], 'Batch', () => {
    throw new Error('Read-only mock SAP service');
  });
});
```

### `mocksap/srv/server.ts` — explicit schema deploy on startup

CAP's `cds-serve` does not auto-deploy schema + CSV in production mode for in-memory SQLite. Without this hook, the app starts cleanly but every query returns `500 - SqliteError: no such table`. The hook fires `cds.deploy()` after services are bound but before traffic flows.

```ts
import cds from '@sap/cds';

const _cds = cds as any;  // cds.deploy exists at runtime but isn't typed

cds.on('served', async () => {
  cds.log('init').info('=== running cds.deploy on startup ===');
  try {
    await _cds.deploy(cds.model).to(cds.db);
    cds.log('init').info('=== cds.deploy completed ===');
  } catch (err: any) {
    cds.log('init').error('cds.deploy failed:', err?.message || err);
  }
});

export default cds.server;
```

The `_cds as any` cast is because `@cap-js/cds-types` doesn't expose `cds.deploy` — TypeScript build fails with `TS2339: Property 'deploy' does not exist`. The runtime call works fine.

## Step 6 — Seed the database from the fixture

`tests/fixtures/inventory_batches.json` is already in SAP OData V2 envelope form with PascalCase keys (`{"d":{"__count": ..., "results": [...]}}`), so the converter mostly drops the two extra columns CAP doesn't model.

### `mocksap/scripts/seed_from_fixture.py`

```python
"""Convert tests/fixtures/inventory_batches.json -> db/data/sap.s4.batch-Batch.csv

Keeps the JSON fixture as single source of truth; rerun whenever it changes.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "inventory_batches.json"
OUT = Path(__file__).resolve().parents[1] / "db" / "data" / "sap.s4.batch-Batch.csv"

CAP_COLUMNS = [
    "Batch", "Material", "MaterialDescription", "TherapeuticCategory",
    "BatchIdentifyingPlant", "PlantName", "ShelfLifeExpirationDate",
    "ManufactureDate", "LastGoodsReceiptDate", "BatchIsMarkedForDeletion",
    "MatlBatchIsInRstrcdUseStock", "Supplier", "SupplierName",
    "CountryOfOrigin", "Quantity", "BaseUnit",
]


def cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = payload["d"]["results"]
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CAP_COLUMNS)
        for row in rows:
            writer.writerow([cell(row.get(col)) for col in CAP_COLUMNS])
    print(f"wrote {len(rows)} rows -> {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
```

Run once:

```bash
cd mocksap && python3 scripts/seed_from_fixture.py
# wrote 125 rows -> mocksap/db/data/sap.s4.batch-Batch.csv
```

## Step 7 — Test locally

```bash
cd mocksap
cds watch
```

Look for `init from db/data/sap.s4.batch-Batch.csv` and `successfully deployed to in-memory database` in the startup log. Then probe:

```bash
curl 'http://localhost:4004/s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV/Batch/$count'
# 125
```

If `cds watch` reports `NO_DATABASE_CONNECTION`, you forgot the dev dep — `npm install --save-dev @cap-js/sqlite`.

## Step 8 — Deploy to BTP Cloud Foundry

### 8a. Generate the MTA descriptor

```bash
cds add mta
```

Then replace the generated `mta.yaml` with this minimal shape (no HANA, no approuter, with an explicit CSV-copy step because `cds build --production` only copies CSVs into `gen/db/` when a real DB module exists):

```yaml
_schema-version: 3.3.0
ID: mocksap
version: 1.0.0
description: "Mock SAP API_BATCH_SRV — fixture-backed OData for accrual demo."
parameters:
  enable-parallel-deployments: true
build-parameters:
  before-all:
    - builder: custom
      commands:
        - npm ci
        - npx cds build --production
        - mkdir -p gen/srv/db/data
        - cp -R db/data/. gen/srv/db/data/
modules:
  - name: mocksap-srv
    type: nodejs
    path: gen/srv
    parameters:
      instances: 1
      buildpack: nodejs_buildpack
      memory: 256M
      disk-quota: 512M
    build-parameters:
      builder: npm-ci
    provides:
      - name: srv-api
        properties:
          srv-url: ${default-url}
```

### 8b. Build and deploy

```bash
mbt build                                                # produces mta_archives/mocksap_1.0.0.mtar (~7 MB)
cf api https://api.cf.us10-001.hana.ondemand.com         # check what your subaccount lists in the cockpit
cf login --sso                                           # interactive OAuth code
cf target -o af3d148dtrial -s dev                        # use the parent org, not the auto-created suborg
cf deploy mta_archives/mocksap_1.0.0.mtar
```

Initial deploy takes 3-5 minutes. When done, `cf apps` shows the route — something like:

```
af3d148dtrial-dev-mocksap-srv.cfapps.us10-001.hana.ondemand.com
```

Smoke test the deployed service:

```bash
URL=https://af3d148dtrial-dev-mocksap-srv.cfapps.us10-001.hana.ondemand.com
curl "$URL/s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV/Batch/\$count"
# 125
curl "$URL/s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV/Batch/\$count?\$filter=BatchIsMarkedForDeletion%20eq%20true"
# 14
```

Watch startup logs to confirm the deploy hook ran:

```bash
cf logs mocksap-srv --recent | grep -E "init|deploy"
# === running cds.deploy on startup ===
# === cds.deploy completed ===
```

## Step 9 — Point the accrual backend at the BTP service

One env var change on the `accrual_sap_backend` Vercel project, no code edits:

```bash
cd /Users/Eeshan/Documents/Deepak_GitHub/accrual_sap   # repo root, where .vercel/ is linked

vercel env rm SAP_SANDBOX_BASE_URL production --yes

# IMPORTANT: use printf, not echo. echo appends \n which gets baked into the value
# and httpx rejects URLs containing newline characters with InvalidURL.
printf 'https://af3d148dtrial-dev-mocksap-srv.cfapps.us10-001.hana.ondemand.com' \
  | vercel env add SAP_SANDBOX_BASE_URL production

# MOCK_MODE stays false; the fetcher now hits the BTP URL
vercel deploy --prod --yes
```

The backend's code path (`src/accrual_pipeline/inventory.py:95-110`) builds the URL as `f"{settings.sap_sandbox_base_url}{BATCH_PATH}"` → that resolves to `https://af3d148dtrial-dev-mocksap-srv.cfapps.us10-001.hana.ondemand.com/s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV/Batch`, exactly what the CAP service serves.

`unwrap_odata` in `src/accrual_pipeline/fetchers/base.py:103-115` already handles both V2 (`{"d":{"results":[]}}`) and V4 (`{"value":[]}`) envelopes, so the version difference between real SAP (V2) and CAP (V4) is invisible to the accrual code.

## Step 10 — Verify end-to-end

```bash
curl https://accrualsap.vercel.app/health
# {"status":"ok","mock_mode":false,"claude_model":"claude-sonnet-4-6"}

curl https://accrualsap.vercel.app/inventory/batches \
  | python3 -c "import sys,json; d=json.load(sys.stdin); b=d['batches'][0]; \
      print(f\"count={d['count']}, first={b['batch']}/{b.get('supplier_name')}\")"
# count=125, first=B0001000/Pfizer Global Biologics

curl 'https://accrualsap.vercel.app/inventory/batches?distress_signal=marked_for_deletion' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])"
# 14
```

Same counts you got from probing BTP directly = end-to-end pipeline is live.

## Lessons learned (gotchas we hit)

These trip you up exactly once each — captured here so the next person spots them in 5 seconds rather than the hour we spent.

1. **`cds add <facet>` doesn't update `package-lock.json`.** Each `cds add hana` / `cds add mta` / etc. writes new entries into `package.json` but leaves the lock untouched. The next `npm ci` (used inside `mbt build`'s `before-all`) fails with "lock file out of sync". Run `npm install` after each `cds add` to resync.

2. **`@sap/cds` isn't a direct dep by default.** `cds init` adds it as a peer of `@cap-js/sqlite`. The CF Node buildpack strips devDeps and resolves only direct deps, so the deployed app crashes with `Cannot find module '@sap/cds'`. Declare it explicitly in `dependencies`.

3. **No `start` script means crashloop.** The Node buildpack runs `npm start`. The default `gen/srv/package.json` inherits whatever your source has, and `cds init` doesn't add a `scripts` block. Add `"scripts": { "start": "cds-serve" }`.

4. **CAP production default is JWT auth.** Without `@sap/xssec` installed (we deliberately don't), startup crashes during middleware loading. Set `cds.requires.auth.kind = "dummy"` to disable auth.

5. **In-memory SQLite is not auto-deployed in production.** `cds watch` deploys schema + CSV at startup; `cds-serve` does not. Add the `srv/server.ts` `cds.on('served', cds.deploy(...))` hook.

6. **`cds.deploy` isn't typed.** `@cap-js/cds-types` omits it; TypeScript compile fails. Cast through `any`: `(cds as any).deploy(cds.model).to(cds.db)`.

7. **CSVs only land in `gen/srv/` when there's a DB module.** With HANA we'd get `gen/db/data/*.csv` for the HDI deployer; without HANA, nothing copies the data. Add an explicit `cp -R db/data/. gen/srv/db/data/` step in the MTA's `before-all`.

8. **`hdi-shared` is paid-only as of early 2026.** Trials and Free Tier get `hana-free` (a HANA Cloud instance) but not HDI containers. Don't plan around `hana / hdi-shared`.

9. **Trial creates a route-quota-0 sub-org.** `cf push` to the auto-created `af3d148dtrial_<sub>` org fails with "Routes quota exceeded for organization". Use the parent `af3d148dtrial` org via `cf target -o af3d148dtrial`.

10. **`cf ssh` is disabled on trials.** "You are not authorized to perform the requested action." Debug the running app via `cf logs <app> --recent` only.

11. **`echo` adds a trailing newline.** Piping into `vercel env add` bakes the newline into the env value, and httpx rejects URLs containing `\n` with `InvalidURL`. Use `printf` instead.

12. **`cf deploy` isn't built-in.** It's added by the MultiApps plugin: `cf install-plugin -r CF-Community multiapps -f`.

13. **No approuter needed.** Set the CAP service's `@path:` to the full SAP-style URL (including the `/s4hanacloud/...` prefix) and the CF default route serves it directly. The original plan to use approuter for a path rewrite was unnecessary complexity.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `cf deploy` says "'deploy' is not a registered command" | MultiApps plugin missing | `cf install-plugin -r CF-Community multiapps -f` |
| `mbt build` fails with `npm ci` error about missing deps | `package-lock.json` out of sync after `cds add ...` | `npm install` in `mocksap/`, then rebuild |
| Deploy fails with "Service plan hdi-shared not found" | Trial doesn't have `hdi-shared` entitlement | Remove HANA from `mta.yaml`; use in-memory SQLite (this guide) |
| Deploy fails with "Routes quota exceeded for organization" | Targeting the route-quota-0 auto-created org | `cf target -o af3d148dtrial -s dev`, then `cf deploy` |
| App crashes with `Missing script: "start"` | Source `package.json` has no `scripts.start` | Add `"start": "cds-serve"` |
| App crashes with `Cannot find module '@sap/cds'` | `@sap/cds` only declared as peer of `@cap-js/sqlite` | Add `"@sap/cds": "^9"` to `dependencies` |
| App crashes with `Cannot find module '@sap/xssec'` | Production-default JWT auth requires xsuaa | Set `cds.requires.auth.kind = "dummy"` in `package.json` |
| App starts but all queries return `500 - SqliteError: no such table` | Schema never deployed | Add `srv/server.ts` with `cds.on('served', cds.deploy(...))` |
| Accrual backend returns 500 with `httpx.InvalidURL: '\n' at position N` | `echo` piped into `vercel env add` baked a newline | Re-add with `printf` (no trailing newline) |
| `cf ssh` says "not authorized" | Trial accounts disable SSH | Use `cf logs <app>` instead |
| Local `cds watch` says `NO_DATABASE_CONNECTION` | `@cap-js/sqlite` not installed locally | `npm install --save-dev @cap-js/sqlite` |

## Code references in this repo

- Fixture: `tests/fixtures/inventory_batches.json` (125 batches)
- SAP field name mapping the CAP entity must match: `src/accrual_pipeline/inventory.py:66-83`
- URL composition: `src/accrual_pipeline/inventory.py:95-110`
- Base URL setting: `src/accrual_pipeline/config.py:49`
- OData V2/V4 envelope unwrap: `src/accrual_pipeline/fetchers/base.py:103-115`
- BatchRecord Pydantic shape returned by `/inventory/batches`: `src/accrual_pipeline/inventory.py:44-63`
- CAP project: `mocksap/`
- Deployable artifact: `mocksap/mta_archives/mocksap_1.0.0.mtar`

## Lifecycle and maintenance

- **Updating the fixture** — edit `tests/fixtures/inventory_batches.json` → rerun `python3 mocksap/scripts/seed_from_fixture.py` → `mbt build && cf deploy mta_archives/mocksap_1.0.0.mtar`. ~3 min cycle.
- **No paid surprises** as long as you stay on `free` service plans. BTP cockpit's "Usage Analytics" shows $0 charges if you've stayed within free quotas.
- **CF app restart wipes the DB** — in-memory SQLite is recreated from the bundled CSV on every container start. That's a feature for a fixture-backed demo: the data is deterministic and reproducible.
- **Resizing memory** — `cf scale mocksap-srv -m 512M`. Default 256M is fine for 125 batches; tight if you 10x the fixture.

## What this does *not* cover

- **OAuth via xsuaa.** This guide is no-auth public read-only. For a production-shaped story, re-add the xsuaa binding to `mta.yaml`, install `@sap/xssec`, flip `cds.requires.auth.kind` back to `jwt`, and have the accrual backend acquire an OAuth token before each call. Roughly half a day of work, out of scope for the source-data demo.
- **Real SAP API Management gateway.** BTP CF gives you `*.cfapps.<region>.hana.ondemand.com` directly. The real API gateway in front of S/4HANA Cloud is a separate product. For our demo the bare CF route is enough.
- **HANA Cloud as the storage engine.** Possible via `hana-free` plan + manual HDI container creation in the cockpit, but adds ~30 min of setup, 12h-idle auto-stop flakiness, and zero visible difference to the accrual backend.
