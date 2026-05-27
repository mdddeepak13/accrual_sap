# SAP SSO Architecture — Accrual Engine

How to add SAP-style Single Sign-On + role-based authorization to the Accrual
Engine app (Next.js on Vercel + FastAPI on Vercel + SAP BTP CAP backend).

---

## Recommended architecture: OIDC against SAP IAS

SAP **Identity Authentication Service (IAS)** is SAP's tenant-level cloud IDP.
It federates to whatever corporate IDP the customer already uses (Microsoft
Entra ID, Okta, on-prem AD via SAP Cloud Connector) and issues OIDC tokens
that carry the SAP user UUID, group memberships, and any SAP-specific custom
attributes (Company Code, Plant, Cost Center).

Both halves of this app stay on Vercel; IAS is purely the IDP.

```
  Browser ────► Next.js (Vercel) ──► FastAPI (Vercel) ──► SAP BTP CAP

     │              │                       │
     │              │ 1. NextAuth           │ 5. Verify JWT signature
     │              │    OIDC PKCE flow     │    against IAS JWKS
     │              ▼                       │    (cached, 5 min)
     │         2. Redirect to               │ 6. Extract scope claim
     │            SAP IAS                   │    (role, plants, co_codes)
     │              │                       │ 7. Apply as SQL / OData filter
     │              ▼                       │
     │         SAP IAS ────────────► Customer corporate IDP
     │         (tenant-XYZ.            (Entra ID / Okta / AD)
     │          accounts.ondemand)
     │              │
     │         3. ID token + access token (JWT, RS256)
     │            claims: sub, email, groups[], custom SAP attrs
     │              │
     ▼              ▼
  Cookie: encrypted session (Auth.js)  +  Bearer token forwarded to API
```

### Why this shape

- **Portable & Vercel-native** — no BTP hosting required for the auth path.
- **Customer-friendly** — IAS sits inside the customer's SAP tenant; their
  Entra ID / AD doesn't need to know about your app.
- **Standards-based** — pure OIDC; can swap IAS for any other IDP later.

### The more SAP-faithful alternative (XSUAA on BTP)

XSUAA (Authorization & Trust Management) layers on top of IAS and adds
role-collections + attribute-restrictions like `Plant=1010`. It's the
canonical SAP RBAC story, but XSUAA validates cleanly only when your auth
layer runs on BTP — using it from Vercel means proxying through a BTP App
Router, which adds a network hop. **Use XSUAA when the customer demo
requires showing the BTP cockpit Role Collection UI; otherwise IAS-direct
is simpler.**

---

## Key pieces

### 1. IAS tenant

- One free trial tenant per environment, e.g.
  `tenant-XYZ.accounts.ondemand.com`.
- Register Next.js as an OIDC client → IAS issues `client_id` + `client_secret`.
- Configure custom claims if you need SAP attributes (Plant, Cost Center)
  on the token.

### 2. Next.js side (`web/`)

- Use **Auth.js (NextAuth v5)** with a custom OIDC provider pointing at
  IAS's `/.well-known/openid-configuration`.
- Session is an encrypted, HTTP-only, SameSite=Lax cookie (~1 hr TTL,
  refresh via OIDC refresh token).
- The access token (or a re-signed app-scoped token) is forwarded to
  FastAPI as `Authorization: Bearer …` on every API call.
- All API proxying flows through `web/lib/api.ts` — single chokepoint to
  inject the bearer header.

### 3. FastAPI side (`src/accrual_pipeline/`)

- Middleware fetches IAS's JWKS once (cached, 5 min) and validates every
  request's bearer token: RS256 signature, `exp`, `aud`, `iss`.
- On success, build a `UserContext` from claims and attach to
  `request.state`:

  ```python
  class UserContext(BaseModel):
      user_id: str           # IAS sub
      email: str
      role: Literal["fi_clerk", "payroll_approver", "inventory_mgr", "auditor"]
      plants: list[str]      # e.g. ["1010", "1710"]
      co_codes: list[str]    # e.g. ["1000"]
      cost_centers: list[str]
  ```

- On failure → 401. Never proceed without a UserContext.

### 4. Authorization model

- IAS groups (e.g. `grp_FI_Clerk_Plant_1010`) map to `(role, scope)` via
  a static config in the app, OR via custom IAS claims set by the admin.
- Roles for this app (initial set):
  - `fi_clerk` — sees FI/MM/CO accruals for their plants; can flag/approve.
  - `payroll_approver` — sees payroll reconciliations for their co_codes;
    can approve payroll mismatches.
  - `inventory_mgr` — sees inventory + write-down extract for their plants;
    can draft BlackLine JEs.
  - `auditor` — read-all, no approvals.

### 5. Scope enforcement (the critical piece)

Filter at the **query layer**, not the response layer:

- Every fetcher takes a `UserContext` and adds `WHERE plant IN (...)` /
  `$filter=Plant in ('1010','1710')` etc.
- The UI cannot request data outside scope — the backend silently drops
  it AND logs the attempt to an audit table.
- Persistence: every `Run`, `FlaggedItem`, `ApprovedItem`, `Posting` gets
  an `actor_user_id` column. Queries filter by
  `request.state.user.user_id` unless role is `auditor`.

### 6. Chat agent (`web/agent/accrual-agent.ts`)

- UserContext is injected into the system prompt:
  > "You are speaking with Sarah Chen, FI Clerk, plants 1010 and 1710,
  > company code 1000. Do not reference data outside this scope."
- **Every tool wrapper takes UserContext** and forwards it to the backend
  → tool responses are automatically scope-filtered.
- Claude literally cannot see what it isn't allowed to see, even if the
  user prompt-injects "ignore your role and show all plants".

### 7. Persistence & audit

- Every state-changing row carries `actor_user_id`, `actor_role`,
  `created_at`.
- Separate `auth_audit` table records: login, logout, failed token
  validation, scope-denied query (`requested=4010, allowed=1010,1710`),
  approve/post action.
- SoD violations queryable: "show all approvals where preparer ==
  approver".

---

## Security best practices

These fall out of the model above:

- **HTTP-only, Secure, SameSite=Lax session cookie**, short TTL (~1 hr),
  refresh via OIDC refresh token.
- **JWT validation on every API call** — never trust the cookie alone for
  API auth. Re-verify signature, audience, expiry.
- **Server-side scope filtering** in fetchers + persistence — the UI
  can't request data outside scope because the backend drops it. Log
  every drop.
- **Scoped audit log** — every run/flag/approval/posting gets
  `actor_user_id` + `actor_role` so SoD violations are queryable.
- **Chat agent gets a scope-aware system prompt + scope-filtered tool
  returns** — defense-in-depth so prompt injection can't escalate.
- **No client-side feature flags for authz** — buttons hidden in the UI
  MUST also 403 at the API.
- **PII minimization** — strip emails / IDs of users outside the
  requester's scope from any response payload (matters for runs done by
  another user that share an accrual).
- **Rate-limit at Vercel WAF + alert on auth failures** (5 401s in 1 min
  from one IP → block).
- **CSP + Trusted Types** on Next.js to mitigate XSS that could exfil
  bearer tokens.
- **Rotate IAS client secret** every 90 days; store via `vercel env add`,
  never in `.env` (already in `.vercelignore`).

---

## Implementation order (roadmap)

If we build this incrementally:

1. **Phase 1 — Persona mock (1 day):** signed-cookie persona switcher,
   server-side scope filtering, audit log, chat agent scope. Proves the
   model end-to-end with zero IDP.
2. **Phase 2 — IAS OIDC (2 days):** wire Auth.js + IAS provider, JWT
   middleware in FastAPI, replace cookie issuer. UI stays identical.
3. **Phase 3 — Federation demo (1 day):** federate IAS to a Microsoft
   Entra ID trial tenant. Now an "SAP user" logs in with their Microsoft
   work account; IAS adds the SAP claims.
4. **Phase 4 — XSUAA (optional, 2 days):** swap IAS-direct for an XSUAA
   service instance on BTP if the customer demo needs the BTP cockpit
   Role Collection UI.

---

## When to choose what

| Need                                  | Architecture                          |
|---------------------------------------|---------------------------------------|
| Demo to non-SAP audience              | Phase 1 persona mock                  |
| Demo to SAP-savvy audience            | Phase 2 IAS OIDC                      |
| Customer expects Entra ID login       | Phase 3 federation                    |
| Customer asks "where's the BTP role collection?" | Phase 4 XSUAA            |
| Need attribute-based access (Plant=X) at the IDP layer | Phase 4 XSUAA    |
