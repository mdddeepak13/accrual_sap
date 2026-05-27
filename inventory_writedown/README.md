# Distressed Inventory Write-down — MB52/MBEW Extract + BlackLine JE

What's in this directory:

| File | What it is |
|---|---|
| `generate.py` | One-shot script. Reads the distressed-inventory fixture, classifies each batch's distress reason, and produces both outputs below. Re-run after editing the fixture or the rules in the script. |
| `mb52_mbew_distressed.csv` | Mock SAP extract joining the MB52 transaction (warehouse stocks by material/batch/plant) with the MBEW table (material valuation). Limited to distressed line items. Column names use SAP PascalCase (`MATNR`, `CHARG`, `LABST`, `STPRS`, `SALK3`, …). |
| `blackline_je.json` | BlackLine-importable journal entry that writes down the value of the distressed stock. Debits aggregate by plant (one expense line per plant), offset by a single credit to the obsolescence allowance. Includes per-batch supporting detail for the audit trail. |

## How distress is classified

Run from `inventory_writedown/generate.py`. First match wins.

| Reason | Rule | Write-down |
|---|---|---|
| `marked_for_deletion` | `BatchIsMarkedForDeletion == true` | 100% |
| `expired` | `ShelfLifeExpirationDate < today` | 100% |
| `quarantine` | `MatlBatchIsInRstrcdUseStock == true` | 50% |
| `near_expiry` | `ShelfLifeExpirationDate within next 90 days` | 25% |
| `slow_moving` | `LastGoodsReceiptDate > 365 days ago` | 30% |

`today` is fixed at `2026-05-21` (matches the system date used elsewhere in the demo).

## How the JE is shaped

```
  DR  894500  Inventory Write-down Expense  cc=CC-1010   $X
  DR  894500  Inventory Write-down Expense  cc=CC-1710   $Y
  DR  894500  Inventory Write-down Expense  cc=CC-2010   $Z
  …                                                        per plant
  CR  139900  Inventory Allowance — Obsolete                $X + $Y + $Z + …
```

- Company code `1000`, currency `USD`, document type `SA` (G/L Account Document).
- Each debit line carries `posting_key=40` (DR for GL postings) and `debit_credit="S"` (Soll).
- The credit line carries `posting_key=50` and `debit_credit="H"` (Haben).
- `assignment` ties all lines to `INV-WD-2026Q2`.
- `supporting_detail` array lists every contributing batch — what BlackLine reviewers and auditors expect to see attached to a JE of this size.

## Re-running

```bash
python3 inventory_writedown/generate.py
```

Idempotent. Re-run any time after editing `tests/fixtures/inventory_batches.json`, the distress rules, or the pricing table.

## Related

- Fixture (source of truth): `tests/fixtures/inventory_batches.json`
- Same distress filter via the accrual backend: `GET /inventory/batches?distress_signal=expired` (etc.)
- BlackLine → SAP integration: BlackLine posts JEs via SAP's OData service (typically `API_JOURNALENTRYBULKPOSTSRV`). Out of scope here; this artifact is the *input* a BlackLine preparer uploads.
- Pricing in `generate.py:PRICE_BY_CATEGORY` is synthetic but plausible per-unit standard prices by therapeutic category. In production these come from the MBEW table.
