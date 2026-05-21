/**
 * Finance chat agent — answers questions about accruals, plan, and variance
 * by calling the Python FastAPI backend on Fly as tools.
 *
 * Each tool wraps a thin HTTP GET; the agent composes them to answer
 * multi-step questions like "compare Apr 2026 actuals vs plan for IT
 * expenses and explain the variance".
 */
import { anthropic } from "@ai-sdk/anthropic";
import { InferAgentUIMessage, ToolLoopAgent, stepCountIs, tool } from "ai";
import { z } from "zod";

const API_BASE =
  process.env.BACKEND_API_URL || "http://localhost:8000";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Backend ${path} → HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

function toQuery(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== "",
  );
  if (entries.length === 0) return "";
  const qs = new URLSearchParams(
    entries.map(([k, v]) => [k, String(v)]),
  ).toString();
  return `?${qs}`;
}

export const accrualAgent = new ToolLoopAgent({
  model: anthropic("claude-sonnet-4-6"),
  stopWhen: stepCountIs(15),
  instructions: `You are a finance-team assistant helping users analyze accruals, budgets, and variances for an SAP S/4HANA dataset.

You have five tools that hit a FastAPI backend:

- \`getAccruals\` — queries the CURRENT actuals (posted + open accruals) from SAP, with optional filters for fiscal year, fiscal period, GL account prefix, cost center, or vendor name substring. Returns a list of accrual objects with 13 business fields: company_code, posting_date, document_date, gl_account_number, gl_description, vendor_number, vendor_name, short_text, long_text, accrual_from_period, accrual_to_period, amount_usd, plus joined PO and cost-center context.
- \`getPlan\` — queries the planned / budgeted amounts for a given year/period/cost-center/GL. Plan data covers fiscal years 2024, 2025, 2026. Use this for budget-vs-actuals and variance questions.
- \`detectIrregularities\` — runs the anomaly-detection pipeline (Claude reviews accruals for stale POs and duplicates). Use when the user asks to find issues, duplicates, stale POs, or what needs review. Takes ~20 seconds.
- \`postApprovedAccruals\` — triggers a full pipeline that posts clean accruals back to S/4. This is destructive-ish. Only call when the user has EXPLICITLY said they want to post, and only after showing them what would be posted. If in doubt, ask for confirmation in text first, then call with confirmed=true.
- \`getPayrollResults\` — queries the current biweekly payroll reconciliation between Workday (authoritative payroll engine) and SAP FI (what PECI delivered into the GL). Returns one row per worker per pay period with both sides' totals plus a list of orphan FI postings (FI lines with no Workday counterpart). Pay group "BIWEEKLY-US-CORP" runs on a biweekly cadence (pay periods of 10 working days, pay-date on the Friday after period end). Use this for questions like "did EMP-1045 get prorated correctly", "which workers have FI-side amount mismatches this period", or "show me all cost-center routing errors". Pass only_mismatches=true to filter to rows that need review.

GL account ranges in this dataset:
- 22xxxxxx — Accrued expenses (various sub-categories)
- 62xxxxxx — Travel & entertainment
- 63xxxxxx — Professional services
- 64xxxxxx — IT & communications
- 65xxxxxx — Office supplies

Cost centers:
- CC-1000 — Production Operations
- CC-2000 — Marketing
- CC-3000 — IT Services
- CC-1100 — Admin & Finance

Payroll context (Workday ↔ SAP FI reconciliation):
- Workday Global Payroll Cloud is the authoritative payroll source. The PECI (Payroll Effective Change Interface) integration posts payroll results into SAP FI as journal entries on AccountingDocumentType "PY".
- Workday GL expense ranges: 50100000 regular salary, 50110000 overtime, 50130000 bonus, 50200000 employer FICA, 50210000 employer Medicare, 50220000 employer 401k match.
- Workday accrual liability GLs: 22150000 (accrued net payroll), 22160000 (accrued payroll taxes).
- Mismatch types Claude flags: \`missing_in_fi\`, \`missing_in_workday\`, \`amount_mismatch\`, \`wrong_cost_center\`, \`wrong_gl_account\`, \`duplicate_fi_posting\`, \`termination_not_prorated\`.

Pharma inventory context (distressed-inventory questions):
- Batches carry a shelf_life_expiration_date (SLED) and a last_goods_receipt_date.
- Distress signals (pass as distress_signal to getBatches): \`expired\`, \`near_expiry\` (SLED within 90d), \`quarantine\` (restricted use), \`marked_for_deletion\`, \`slow_moving\` (no GR activity in 365+d), \`clean\`, or \`any_distressed\` (any of the above).
- Therapeutic categories in the data: ANTIBIOTIC, OTC, CHRONIC, INJECTABLE, CONTROLLED, ONCOLOGY, VACCINE, BIOLOGIC.
- Plants: 1010 (Frankfurt DC), 1710 (New Jersey DC), 2010 (Bangalore DC).
- For write-off exposure questions, multiply quantity × a nominal unit cost if the user hasn't given one, and say so explicitly.

Guidelines:
- When asked a question, pick the minimum set of tool calls needed.
- For variance / budget questions, call BOTH getAccruals and getPlan and compute the delta in your response.
- Always cite concrete numbers (vendor names, amounts in USD, cost centers, dates).
- If the data needed isn't available (e.g. prior-year actuals not in the demo dataset), say so clearly rather than making up numbers.

ALWAYS structure every answer with these three sections in this order:

## How I answered this
A short (3-5 bullet) methodology note: which tools you called, what
filters/parameters you passed, why you chose those, and how many records
came back. Purpose: a finance reviewer can audit your logic without
reading the raw tool output.

## Data
A full Markdown table of the relevant records. Do not truncate silently —
if a result has 25 rows, show all 25 (or say explicitly "showing top N of
total M"). This is the validation report the user needs to cross-check
your conclusions. Include the key identifier columns (e.g. accrual_id,
batch, material, SKU, vendor, amounts, dates). For inventory questions
always include: batch, material, description, plant, quantity, SLED,
last_GR_date, and any distress flags.

## Findings / Recommendation
Your analysis and call to action. 3-6 bullets max. Cite specific rows
from the Data table by identifier (e.g. "Batch B0001002 is 149 days
expired — prioritize for write-off"). End with what the user should do
next.

Keep headings as shown; finance teams will skim them.`,
  tools: {
    getAccruals: tool({
      description:
        "Fetch current accrual actuals from SAP with optional filters.",
      inputSchema: z.object({
        year: z.string().optional().describe("Fiscal year, e.g. '2026'"),
        period: z
          .string()
          .optional()
          .describe("Fiscal period as a 3-digit string, e.g. '004' for April"),
        gl_account_prefix: z
          .string()
          .optional()
          .describe("GL prefix, e.g. '62' for travel, '64' for IT"),
        cost_center: z
          .string()
          .optional()
          .describe("Exact cost center code, e.g. 'CC-2000'"),
        vendor_contains: z
          .string()
          .optional()
          .describe("Case-insensitive substring match on vendor name/number"),
        limit: z.number().optional().describe("Max rows returned. Default 200."),
      }),
      execute: async (args) => {
        return await fetchJson(`/accruals${toQuery(args)}`);
      },
    }),

    getPlan: tool({
      description:
        "Fetch planned / budgeted amounts with optional filters. Covers fiscal years 2024, 2025, 2026.",
      inputSchema: z.object({
        year: z.string().optional(),
        period: z.string().optional().describe("3-digit period, e.g. '004'"),
        cost_center: z.string().optional(),
        gl_account_prefix: z.string().optional(),
      }),
      execute: async (args) => {
        return await fetchJson(`/plan${toQuery(args)}`);
      },
    }),

    getBatches: tool({
      description:
        "Fetch pharma batch records for distressed-inventory analysis. Filters on material prefix, therapeutic category, plant, supplier, and distress signal. For 'what's at risk of write-off' questions, pass distress_signal='any_distressed'. For specific scenarios use one of: expired, near_expiry, quarantine, marked_for_deletion, slow_moving, clean, any_distressed.",
      inputSchema: z.object({
        material_prefix: z
          .string()
          .optional()
          .describe("Material SKU prefix, e.g. 'PH-AMX' for amoxicillin family"),
        therapeutic_category: z
          .string()
          .optional()
          .describe(
            "One of ANTIBIOTIC, OTC, CHRONIC, INJECTABLE, CONTROLLED, ONCOLOGY, VACCINE, BIOLOGIC",
          ),
        plant: z
          .string()
          .optional()
          .describe("Plant code: 1010 (Frankfurt), 1710 (New Jersey), 2010 (Bangalore)"),
        supplier_contains: z
          .string()
          .optional()
          .describe("Substring match on supplier name or code"),
        distress_signal: z
          .enum([
            "expired",
            "near_expiry",
            "quarantine",
            "marked_for_deletion",
            "slow_moving",
            "clean",
            "any_distressed",
          ])
          .optional(),
        near_expiry_days: z
          .number()
          .optional()
          .describe("Threshold for 'near_expiry' in days. Default 90."),
        slow_moving_days: z
          .number()
          .optional()
          .describe("Threshold for 'slow_moving' in days since last GR. Default 365."),
      }),
      execute: async (args) => {
        return await fetchJson(`/inventory/batches${toQuery(args)}`);
      },
    }),

    detectIrregularities: tool({
      description:
        "Run anomaly detection pipeline (stale POs, duplicate accruals). Kicks off a ~20s job; this tool polls until completion and returns flagged items + approved items.",
      inputSchema: z.object({}),
      execute: async () => {
        const res = await fetch(`${API_BASE}/runs`, {
          method: "POST",
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`POST /runs → HTTP ${res.status}`);
        const { run_id } = (await res.json()) as { run_id: string };

        // Poll until the run completes (max ~60s).
        for (let i = 0; i < 30; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          const detail = await fetchJson<{
            status: string;
            flagged: unknown[];
            approved: unknown[];
          }>(`/runs/${run_id}`);
          if (detail.status === "completed" || detail.status === "failed") {
            return { run_id, ...detail };
          }
        }
        return { run_id, status: "timeout", flagged: [], approved: [] };
      },
    }),

    getPayrollResults: tool({
      description:
        "Fetch the current biweekly Workday↔SAP FI payroll reconciliation. Returns one row per worker per pay period with both sides' totals, plus orphan FI postings. Pass only_mismatches=true to filter to rows that need review.",
      inputSchema: z.object({
        worker_id: z
          .string()
          .optional()
          .describe("Exact Workday Worker_Reference, e.g. 'EMP-1045'"),
        pay_group: z
          .string()
          .optional()
          .describe("Pay group ID, e.g. 'BIWEEKLY-US-CORP'"),
        pay_period_end: z
          .string()
          .optional()
          .describe("Pay period end date in ISO YYYY-MM-DD, e.g. '2026-05-10'"),
        cost_center: z
          .string()
          .optional()
          .describe("Exact cost center code, e.g. 'CC-1000'"),
        only_mismatches: z
          .boolean()
          .optional()
          .describe(
            "If true, return only rows where Workday and FI disagree (missing/duplicate FI doc, >$1 expense gap, or cost-center routing error).",
          ),
      }),
      execute: async (args) => {
        return await fetchJson(`/payroll/results${toQuery(args as Record<string, string | number | undefined>)}`);
      },
    }),

    postApprovedAccruals: tool({
      description:
        "Trigger a pipeline run that posts approved accruals back to S/4 (mock postback). DESTRUCTIVE-ish — only call when user has explicitly said they want to post, and only with confirmed=true after explicit user confirmation. If unsure, ask the user in text first.",
      inputSchema: z.object({
        confirmed: z
          .boolean()
          .describe(
            "Must be true. The agent should have already obtained explicit confirmation from the user.",
          ),
      }),
      // Prompt-cache breakpoint: marking the last tool caches the whole
      // system + tools prefix (~90% discount on subsequent input tokens
      // within a 5-min window). System + tool defs are >1024 tokens, which
      // clears Anthropic's minimum for Sonnet-4 caching.
      providerOptions: {
        anthropic: { cacheControl: { type: "ephemeral" } },
      },
      execute: async ({ confirmed }) => {
        if (!confirmed) {
          return {
            status: "awaiting_confirmation",
            message:
              "Call this tool again with confirmed=true only after the user explicitly says to post.",
          };
        }
        // This is the same detectIrregularities path — the pipeline
        // automatically posts approved items to the (mock) S/4 endpoint.
        const res = await fetch(`${API_BASE}/runs`, {
          method: "POST",
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`POST /runs → HTTP ${res.status}`);
        const { run_id } = (await res.json()) as { run_id: string };
        for (let i = 0; i < 30; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          const detail = await fetchJson<{
            status: string;
            flagged: unknown[];
            approved: unknown[];
          }>(`/runs/${run_id}`);
          if (detail.status === "completed" || detail.status === "failed") {
            return {
              run_id,
              posted_count: Array.isArray(detail.approved)
                ? detail.approved.length
                : 0,
              ...detail,
            };
          }
        }
        return { run_id, status: "timeout" };
      },
    }),
  },
});

export type AccrualAgentUIMessage = InferAgentUIMessage<typeof accrualAgent>;
