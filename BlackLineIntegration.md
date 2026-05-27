# BlackLine Integration Guide — Posting Inventory Write-off Accruals into SAP

Companion to [`expired_writeoff/`](expired_writeoff/) — that directory generates the artifacts (MB52+MBEW extract, accrual JE in BlackLine CSV + JSON). This doc covers everything outside the artifacts: BlackLine account setup, integration architecture, where the CSV slots in, and the actual posting back to SAP.

## TL;DR

| | Reality |
|---|---|
| Permanent free tier | **No.** BlackLine is enterprise-sales-only. |
| 30-day free trial via web | **Not available.** Was offered historically (2008-2015 era); current intake requires sales call. |
| Demo tenant for evaluation | **Yes**, via "Request a Demo" → sales call → 14–30 day eval tenant provisioned. |
| Partner / consulting access | **Yes** — if you work with an SAP SI partner who has a BlackLine sandbox, fastest route. |
| Free training / community access | **Yes** — BlackLine University (`blackline.com/services/blackline-university`) offers product training without a paid tenant. |
| SAP S/4HANA integration | **Three** certified paths. File-based SFTP, BlackLine SAP Connector (extract), Web Services Connector (post). |

The TL;DR: you cannot self-serve sign up for BlackLine. Plan on a sales conversation. For a demo *without* a real BlackLine tenant, the most honest path is to produce the import-ready CSV (which we already do in `expired_writeoff/blackline_accrual_je.csv`) and show the would-be integration architecture below.

## How to request a BlackLine account

### Step 1 — Pick the engagement path

| Path | Best when | Lead time |
|---|---|---|
| **Sales-driven demo** | You're a prospective customer evaluating Modern Accounting Cloud | 1–2 weeks |
| **Partner sandbox** | You work with a Big-4 / SAP SI that already has BlackLine | 1–3 days |
| **BlackLine University only** | You just want product training, no real tenant | Immediate |
| **Existing customer adding sandbox** | Your company already has BlackLine | Internal ticket |

### Step 2 — Request the demo / trial

1. Go to https://www.blackline.com/ → "Request a Demo" (top right).
2. Fill out the form. Required fields: name, work email, company, role, country, what product you're interested in (pick "Journal Entry" + "Account Reconciliation").
3. BlackLine sales rep reaches out within 1–3 business days. They'll ask:
   - Company size and revenue (this affects pricing tier)
   - Current ERP (S/4HANA, Oracle, etc.)
   - Use case
   - Whether you're authorized to evaluate
4. If qualified, they provision a **demo tenant** at `<yourtenant>.blackline.net` with pre-loaded sample data. Typical eval window: 14–30 days.

### Step 3 — Get tenant credentials

You receive an email with:
- Tenant URL (`https://<companyname>.blackline.net`)
- Initial admin user + temp password
- BlackLine support contact for the eval

### Step 4 — (Optional) BlackLine University

Independent of a tenant, you can sign up at https://www.blackline.com/services/blackline-university/ for:
- Free product training videos
- Certification paths (paid)
- Documentation library access (some content is gated, some open)

This is the fastest way to see BlackLine's actual JE template format and configurator UI without waiting on sales.

## Integration architecture with SAP S/4HANA

BlackLine has been SAP-certified since 2020. Three integration patterns, often combined in production:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        SAP S/4HANA (system of record)                       │
└──────────────┬──────────────────────────────────────▲──────────────────────┘
               │                                       │
       ┌───────▼─────────┐                  ┌─────────┴────────┐
       │  ETL out of SAP │                  │  POST back to SAP│
       │  (trial bal,    │                  │  (post the JE,   │
       │   open items,   │                  │   close period,  │
       │   journals)     │                  │   etc.)          │
       └───────┬─────────┘                  └─────────▲────────┘
               │                                       │
   ┌───────────▼───────────────────────────────────────┴──────────┐
   │                       BlackLine Cloud                         │
   │  • Account Reconciliation • Journal Entry • Close Manager     │
   │  • Variance Analysis      • Intercompany   • Smart Close      │
   └───────────────────────────────────────────────────────────────┘
```

### Three connector options

| Path | What it does | Direction | Used when |
|---|---|---|---|
| **BlackLine SAP Connector** (SAP-certified, on `sap.com/marketplace`) | Pre-built ETL that pulls GL balances, open items, AR/AP details out of S/4 on a schedule | SAP → BlackLine | Daily / period-close data refresh |
| **BlackLine Web Services Connector** | Posts journal entries from BlackLine into S/4 via S/4's OData / RFC interfaces | BlackLine → SAP | Posting reviewed JEs (this is the part we care about for the write-off workflow) |
| **File-based SFTP** | Either party drops CSV/XML/TXT into a shared SFTP location; the other picks up on a schedule | Either | Legacy / simple integrations; when API access is restricted |

For our **expired-batch write-off workflow**, the relevant data flow is:

```
1. SAP MB52 + MBEW data        →  BlackLine          (already done via our extract)
2. BlackLine JE template       →  preparer reviews   (creates the JE we built)
3. BlackLine JE                →  approver approves
4. BlackLine Web Services Conn →  SAP S/4HANA        (posts the actual document)
5. SAP document number         →  BlackLine          (closes the loop, references the posted doc)
```

## How our generated CSV slots in

`expired_writeoff/blackline_accrual_je.csv` is the file a BlackLine preparer would import. Its columns match BlackLine's standard JE import template:

| Column | What BlackLine does with it |
|---|---|
| `Journal_ID` | Sets the BlackLine JE name; unique per submission |
| `Posting_Date` / `Document_Date` | Becomes the `BUDAT` / `BLDAT` when posted to SAP |
| `Document_Type` | Maps to SAP `BLART` (we use `SA`) |
| `Company_Code` | SAP `BUKRS` |
| `Currency` | Document currency (`USD`) |
| `Header_Text` | SAP document header text (`BKTXT`) |
| `Reference` | SAP reference (`XBLNR`) |
| `Line_Number` | Order of lines; BlackLine renumbers on post |
| `Posting_Key` | SAP `BSCHL` — `40` for debit, `50` for credit |
| `GL_Account` | SAP `HKONT` (G/L account) |
| `Cost_Center` | SAP `KOSTL` |
| `Profit_Center` | SAP `PRCTR` |
| `Plant` | SAP `WERKS` (relevant for COGS allocation) |
| `Debit_Amount` / `Credit_Amount` | The amount; only one per row |
| `Line_Item_Text` | SAP `SGTXT` |
| `Assignment` | SAP `ZUONR` — useful for clearing / linkage |

The structured JSON file (`blackline_accrual_je.json`) adds `supporting_detail` (per-batch contribution) — BlackLine attaches that to the JE as evidence for audit.

## End-to-end integration steps (once you have a BlackLine tenant)

### Phase 1 — Tenant setup (½ day)

1. Log into your BlackLine tenant.
2. **Administration → Company → Companies** → add your SAP company code (`1000`) as a BlackLine company. Set base currency `USD`.
3. **Administration → Chart of Accounts** → either bulk-import your S/4 GL master, or sync via the SAP Connector. At minimum load `894500`, `220100`, `139900`.
4. **Administration → Cost Centers / Profit Centers** → load `CC-1010 … CC-4010`, profit centers similarly.

### Phase 2 — Install the SAP Connector (1 day)

1. In SAP, download the BlackLine SAP Connector transport from SAP Marketplace (search "BlackLine"). Requires basis to import.
2. Activate the role `Z_BLACKLINE_CONNECTOR_USER` for a technical user.
3. In BlackLine: **Administration → Integration → SAP Connector → Configure**. Provide:
   - SAP application server host
   - System number, client, technical user / password
   - GL account ranges to extract
4. Schedule the extract job (typically nightly).

### Phase 3 — Install the Web Services Connector (½ day) — needed to *post* JEs

1. In SAP: enable the standard FI posting RFC `BAPI_ACC_DOCUMENT_POST` for the BlackLine technical user. SAP Note `2718856` covers the required authorizations.
2. In BlackLine: **Administration → Integration → Web Services → Configure**. Same SAP host, same technical user.
3. Test with a dummy `$0.01` JE to confirm round-trip works (post → SAP returns a doc number → BlackLine records the reference).

### Phase 4 — Configure the Journal Entry module (1 day)

1. **Modules → Journal Entry → Templates → New Template** → "Inventory Write-off Accrual" template:
   - Map CSV columns to BlackLine fields (one-time)
   - Set default `Document_Type = SA`, `Currency = USD`
   - Define required approver workflow (e.g., preparer → controller → CFO)
2. **Modules → Journal Entry → Recurring Schedules** → schedule the monthly inventory write-off review (e.g., last working day of each month).

### Phase 5 — Posting the actual JE (the workflow we care about)

1. Run `python3 expired_writeoff/generate.py` → produces `blackline_accrual_je.csv`.
2. In BlackLine: **Journal Entry → Import** → select the file. BlackLine validates structure, balances debits/credits (must be zero), flags duplicates.
3. BlackLine assigns the JE a sequence number and routes for approval per the template's workflow rules.
4. Reviewer (controller) clicks **Approve**. Approver (CFO) clicks **Approve**.
5. BlackLine triggers the Web Services Connector → calls `BAPI_ACC_DOCUMENT_POST` against S/4 → SAP returns document number, e.g. `4900000123 / 2026 / 1000`.
6. The SAP doc number is written back into BlackLine for the audit trail.

## Free-tier alternatives for the demo (if you don't have BlackLine)

If you need to demonstrate the workflow without a real BlackLine tenant:

| Stand-in | What it gives you | Effort |
|---|---|---|
| **Just our CSV file** | Show the BlackLine-shape import file we generate; explain the workflow | 0 (we already have this) |
| **Vercel-hosted "fake BlackLine"** | Build a small Next.js page that uploads the CSV, shows preparer/approver workflow, posts to our FastAPI which simulates SAP posting | ~half day |
| **BlackLine sandbox via partner** | Get real BlackLine UI from an SAP SI that already has one | 1–3 days; partner-dependent |

For the current demo, **showing the generated CSV + this doc + a slide of the architecture** is the highest-fidelity story without paying for a BlackLine tenant.

## Real costs (rough, for context)

- BlackLine subscription: typically **$60K–$300K/year** depending on modules and revenue tier. No published price list.
- Implementation: **$50K–$250K** with a partner.
- Pay-as-you-go / per-user free tier: **does not exist**.

If you're presenting this to a CFO, those numbers explain why the demo skips the actual BlackLine UI step.

## Reference

- BlackLine + SAP overview: https://www.blackline.com/sap/
- SAP-certified integrations announcement: https://www.blackline.com/about/press-releases/2020/blackline-announces-three-sap-certified-integrations-with-sap-s-4hana-1909/
- BlackLine University (free training): https://www.blackline.com/services/blackline-university/
- SAP Community thread on the integration: https://community.sap.com/t5/enterprise-resource-planning-q-a/integrating-blackline-with-sap-s-4hana-a-comprehensive-guide/qaq-p/14000888
- SAP Note `2718856` — BAPI authorization for BlackLine
- Connector docs (customer-only): `https://docs.blackline.com/`

## See also

- [`expired_writeoff/`](expired_writeoff/) — the artifacts this doc references
- [`inventory_writedown/`](inventory_writedown/) — the broader write-down workflow (118 distressed batches, multi-tier severity)
- [`AccrualSourceData.md`](AccrualSourceData.md) — where the source data comes from
