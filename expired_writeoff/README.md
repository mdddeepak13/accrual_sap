# Expired-Batch Write-off Workflow

Companion to [`../BlackLineIntegration.md`](../BlackLineIntegration.md). This directory contains the artifacts that initiate the write-off workflow for the 35 expired pharma batches: an SAP-style MB52+MBEW extract limited to expired stock, and the accrual journal entry that BlackLine would import and post to S/4HANA.

## Files

| File | What it is |
|---|---|
| `generate.py` | Reads `tests/fixtures/inventory_batches.json`, filters to batches with `ShelfLifeExpirationDate < today`, computes the write-off accrual aggregated by plant, and emits the three artifacts below. Re-run after fixture or pricing edits. |
| `expired_batches_extract.csv` | MB52 + MBEW joined extract limited to the 35 expired batches. One row per batch with stock quantity, standard price, valuation class, stock value, days past SLED, and the 100% write-off amount. SAP PascalCase column names. |
| `blackline_accrual_je.csv` | BlackLine-importable CSV — one row per JE line. Header columns map to the standard BlackLine JE import template (Journal_ID, Posting_Date, GL_Account, Cost_Center, Debit_Amount, Credit_Amount, etc.). Matches the column shape BlackLine's "Import JE" function expects. |
| `blackline_accrual_je.json` | Same JE as structured JSON with `supporting_detail` (per-batch contribution) — BlackLine attaches this to the JE as audit evidence. |

## The accrual posting

Standard pre-physical-removal accrual: recognize the expense and the obligation, then later relieve the accrual when the inventory is physically scrapped.

```
DR  894500  Inventory Write-off Expense   CC-1010 Frankfurt DC    $4,473,600.00
DR  894500  Inventory Write-off Expense   CC-1710 New Jersey DC      $12,000.00
DR  894500  Inventory Write-off Expense   CC-2010 Bangalore DC      $642,780.00
DR  894500  Inventory Write-off Expense   CC-3010 Sao Paulo DC      $154,450.00
DR  894500  Inventory Write-off Expense   CC-4010 Singapore DC    $1,946,750.00
CR  220100  Accrued Inventory Write-off                          $7,229,580.00
                                                                 ─────────────
                                                          Balanced  ✓
```

- 35 expired batches → 5 plant-level debit lines + 1 consolidated credit
- Total $7,229,580.00 USD (100% write-off of stock value at standard price)
- Document type `SA` (G/L Account Document), company code `1000`, reference `INV-WO-EXPIRED-Q2-2026`

This is distinct from the broader write-down workflow in [`../inventory_writedown/`](../inventory_writedown/), which covers all 118 distressed batches at varying severity (25% / 30% / 50% / 100%). The expired-batch run is 100% impairment on a focused subset.

## How this maps to the workflow

```
1. Generate the artifacts:           python3 expired_writeoff/generate.py
2. Preparer reviews extract:         expired_batches_extract.csv
3. Preparer imports JE into BlackLine: blackline_accrual_je.csv
4. Controller / CFO approves in BlackLine
5. BlackLine posts via Web Services Connector → SAP S/4HANA
6. SAP returns doc number → recorded in BlackLine
```

Full integration details (BlackLine signup, SAP connector setup, posting back-channel) live in [`../BlackLineIntegration.md`](../BlackLineIntegration.md).

## Re-running

```bash
python3 expired_writeoff/generate.py
```

Idempotent. Re-run after editing `tests/fixtures/inventory_batches.json` or the `PRICE_BY_CATEGORY` table in `generate.py`.

## Related

- Source of truth: `tests/fixtures/inventory_batches.json`
- Broader distress workflow (118 batches, multi-severity): `../inventory_writedown/`
- Integration steps with BlackLine: `../BlackLineIntegration.md`
- Where the SAP-shaped data comes from: `../AccrualSourceData.md`
