# Accrual Source Data Options

## Context

The accrual pipeline's `/inventory/batches` endpoint is wired to SAP's `API_BATCH_SRV` OData service at `https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV/Batch`. In `MOCK_MODE=false`, the live SAP sandbox returns 200 batches but **every distress-signal field is null** (`shelf_life_expiration_date`, `manufacture_date`, `plant`, `supplier`, `quantity`, etc.), so the distressed-filter returns 200/200 — a meaningless artifact. The shared SAP API Business Hub sandbox is a read-only multi-tenant demo; arbitrary users cannot persist data into it, so the 100 hand-crafted distressed pharma batches in `tests/fixtures/inventory_batches.json` can't simply be pushed "into SAP" for the app to read back.

This document records the four practical paths to demonstrate distressed inventory and the tradeoffs between them.

## Options

### A. Stay on `MOCK_MODE=true`

Set `MOCK_MODE=true` on the Vercel `accrual_sap_backend` project and let `inventory.py` short-circuit to the fixture file.

- **What changes:** one env var flip + redeploy.
- **Wire path:** none — `fetch_batch_records` reads `tests/fixtures/inventory_batches.json` directly.
- **Authenticity:** low. No HTTP call to anything that looks like SAP.
- **Effort:** ~30 seconds.

```
vercel env rm  MOCK_MODE production --yes --cwd .
vercel env add MOCK_MODE production --cwd .       # enter: true
vercel deploy --prod --cwd .
```

### B. Local OData "fake SAP" service (recommended)

Stand up a small FastAPI service that mimics the SAP `API_BATCH_SRV/Batch` OData shape and serves the 100-batch fixture. Deploy as a second Vercel project (e.g. `accrual_sap_mocksap`). Point the existing app at it by overriding `SAP_SANDBOX_BASE_URL`.

- **What changes:** new service + one env var on the backend (`SAP_SANDBOX_BASE_URL=https://accrual-sap-mocksap.vercel.app`). The accrual backend code does not change — `MOCK_MODE=false` and it makes a real HTTP call.
- **Wire path:** identical to production — TLS, OData URL shape, JSON response envelope. Only the upstream host differs.
- **Authenticity:** high. Same code path as a real S/4 integration.
- **Effort:** ~1 hour to write and deploy.
- **Caveat:** the API gateway in front of real SAP (Apigee) isn't there, so headers like `APIKey` are accepted-and-ignored. Not a problem for a demo.

### C. SAP BTP trial + CAP service

Provision an SAP BTP trial account, build a CAP (Cloud Application Programming Model) project that exposes a `Batch` entity, seed it with the fixture, deploy it to BTP Cloud Foundry or Kyma, and bind an API key. Point `SAP_SANDBOX_BASE_URL` at the BTP route.

- **What changes:** real SAP gateway + OAuth or APIKey flow. The accrual backend stays on `MOCK_MODE=false` and treats the BTP service exactly like SAP.
- **Wire path:** real SAP infrastructure (BTP managed approuter / destination service / xsuaa for auth).
- **Authenticity:** very high — SAP-managed network, identity, and gateway.
- **Effort:** ~half a day, plus a BTP trial account.
- **Caveat:** BTP trials expire and have quotas; redeploying after a long gap can require re-provisioning.

### D. S/4HANA Cloud trial

Obtain an S/4HANA Cloud trial tenant (limited-time or partner-edition). POST 100 distressed batches via `API_BATCH_SRV` with proper auth, then have the accrual backend read them back through the same API.

- **What changes:** the fixture becomes the *seed script* — load it once into S/4 via POST.
- **Wire path:** an actual S/4HANA system, not a stand-in.
- **Authenticity:** highest — there is no clearer way to demonstrate "this is real SAP data".
- **Effort:** full day or more for tenant provisioning, IAM setup, seeding.
- **Caveat:** trial tenants are time-limited and paid; this is the heaviest path.

## Decision Matrix

| Option | Authenticity | Effort | Cost | Best when |
|---|---|---|---|---|
| A. MOCK_MODE=true | Low | ~30s | Free | You just need the demo to work |
| **B. Fake SAP OData (recommended)** | **High** | **~1h** | **Free** | **You want the demo to look like real SAP** |
| C. BTP CAP service | Very high | ~½ day | BTP trial | You want a real SAP-managed gateway |
| D. S/4 Cloud trial | Highest | 1+ day | Paid trial | You want a true end-to-end S/4 story |

## Recommendation

**Go with option B.** It gives the demo a genuine "SAP API over HTTPS" code path without paying the BTP/S4 cost. The fixture stays the source of truth, but the data leaves the Python process, hits a real network endpoint, and comes back through the same code path the production integration would use. The only file that changes inside `accrual_pipeline` is the `SAP_SANDBOX_BASE_URL` env var.

If demo time is short, option A is fine — note in the talk track that the fixture stands in for SAP, and walk through `inventory.py:100-110` to show the swap point.

## Pointers in the codebase

- Fixture: `tests/fixtures/inventory_batches.json` (100 distressed + 25 baseline = 125 batches)
- Branching: `src/accrual_pipeline/inventory.py:100-110` — `if settings.mock_mode: ... else: ...`
- Endpoint constant: `src/accrual_pipeline/inventory.py:35` — `BATCH_PATH = "/s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV/Batch"`
- Base URL setting: `src/accrual_pipeline/config.py:49` — `sap_sandbox_base_url: str = Field(default="https://sandbox.api.sap.com")`
- HTTP client factory: `src/accrual_pipeline/fetchers/base.py:35` — `create_sap_client()`
