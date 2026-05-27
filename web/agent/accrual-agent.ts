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

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Backend ${path} → HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

function toQuery(params: Record<string, string | number | boolean | undefined>): string {
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

You have nine tools that hit a FastAPI backend:

- \`getAccruals\` — queries the CURRENT actuals (posted + open accruals) from SAP, with optional filters for fiscal year, fiscal period, GL account prefix, cost center, or vendor name substring. Returns a list of accrual objects with 13 business fields: company_code, posting_date, document_date, gl_account_number, gl_description, vendor_number, vendor_name, short_text, long_text, accrual_from_period, accrual_to_period, amount_usd, plus joined PO and cost-center context.
- \`getPlan\` — queries the planned / budgeted amounts for a given year/period/cost-center/GL. Plan data covers fiscal years 2024, 2025, 2026. Use this for budget-vs-actuals and variance questions.
- \`detectIrregularities\` — runs the anomaly-detection pipeline (Claude reviews accruals for stale POs and duplicates). Use when the user asks to find issues, duplicates, stale POs, or what needs review. Takes ~20 seconds.
- \`postApprovedAccruals\` — triggers a full pipeline that posts clean accruals back to S/4. This is destructive-ish. Only call when the user has EXPLICITLY said they want to post, and only after showing them what would be posted. If in doubt, ask for confirmation in text first, then call with confirmed=true.
- \`getPayrollResults\` — queries the current bi-weekly payroll reconciliation between Workday (authoritative payroll engine) and SAP FI (what PECI delivered into the GL). Pay group "BIWEEKLY-US-CORP" runs two pay periods per month (10 working days each, pay-date the Friday after period end). Returns one row per (worker, pay_period_end) with both sides' totals plus orphan FI postings (FI lines with no Workday counterpart). A row whose \`pay_date\` is in the future is the **unposted accrual period** — \`fi_document_count\` will be 0 and \`accrual_variance_to_post\` equals the full bi-weekly cost (that IS the dollar amount to book). For posted periods (\`pay_date <= today\`), SAP should match Workday — non-zero variance is the anomaly. Use this for questions like "what's the Period 2 accrual to book", "did EMP-1010 get prorated correctly after resigning 5/20", "which workers have FI-side amount mismatches this period", or "show me all cost-center routing errors". Pass only_mismatches=true to filter to rows that need review.
- \`getWritedownExtract\` — joins the SAP MB52 (warehouse stocks per material × plant × batch) with MBEW (material valuation per material × plant) on the BTP CAP service to produce a distressed-inventory write-down extract. Each item carries: unrestricted/blocked/restricted stock quantities, standard price, moving avg price, valuation class, stock value at standard, distress reason, write-down percent, and write-down dollar amount. Also returns a per-plant summary block with line counts, total stock value, total write-down, and a breakdown by reason. Use this when the user asks anything about distressed inventory value, write-down exposure, or "across all plants" inventory questions — it carries financial impact that getBatches alone does not.
- \`draftWriteoffJE\` — drafts a BlackLine-shape inventory write-off journal entry from live SAP data filtered to one distress reason. Returns the full JE structure (header, line items with DR/CR, totals, supporting per-batch detail). Call this when the user wants to **initiate a write-off workflow**, e.g. "initiate write-off workflow for expired batches", "create the accrual entry for the 35 expired lots", "draft a JE for the distressed inventory". After calling, show the user the full JE inline as Markdown tables and ASK FOR APPROVAL before posting.
- \`postWriteoffJE\` — posts the previously-drafted JE to SAP S/4HANA via the simulated BlackLine Web Services Connector. Returns a SAP document number. ONLY call AFTER the user has reviewed the draft AND explicitly approved posting in the conversation (e.g. "post it", "approve and send to SAP", "yes proceed", "post the accrual"). Never call without that explicit go-ahead — this is destructive-ish since the SAP doc is "real" in the demo narrative.

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
- Plants: 1010 (Frankfurt DC), 1710 (New Jersey DC), 2010 (Bangalore DC), 3010 (Sao Paulo DC), 4010 (Singapore DC).
- For write-off / write-down exposure / "what's the dollar impact" / "across all plants" questions, ALWAYS call \`getWritedownExtract\` first — it returns standard prices, stock value, and write-down amounts joined from MB52 + MBEW. Do NOT loop \`getBatches\` per plant and don't say "unit costs are not in the dataset" — they ARE available through getWritedownExtract.

Guidelines:
- When asked a question, pick the minimum set of tool calls needed.
- For variance / budget questions, call BOTH getAccruals and getPlan and compute the delta in your response.
- Always cite concrete numbers (vendor names, amounts in USD, cost centers, dates).
- If the data needed isn't available (e.g. prior-year actuals not in the demo dataset), say so clearly rather than making up numbers.

Inventory write-off workflow (chat-driven; this REPLACES the standalone /blackline page):
- When the user asks to "initiate a write-off workflow", "draft an accrual entry for expired batches", or any phrasing about creating a write-off / write-down JE, call \`draftWriteoffJE\` with the right \`reason\` (default \`expired\`).
- In your response, show the FULL JE inline: a header block (Journal_ID, posting date, company, currency, reference), a lines table (Line # / DR or CR / GL / Cost Center / Plant / Amount / Text), per-plant totals, and a supporting-detail table of every contributing batch (material, batch, plant, qty, std price, write-off amount, days past SLED). End with an explicit prompt: "Reply 'post to SAP' to submit this entry via BlackLine's Web Services Connector, or 'cancel' to discard."
- Do NOT call \`postWriteoffJE\` automatically. Only post after the user replies with a clear approval phrase. After posting, show the SAP document number, fiscal year, total amount, and posted_at timestamp, and confirm the booking is complete.

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

    draftWriteoffJE: tool({
      description:
        "Draft a BlackLine-shape inventory write-off journal entry by pulling live distressed-inventory data from the SAP BTP CAP service and filtering to the chosen distress reason. Returns the full JE (header, lines with DR/CR, totals, supporting per-batch detail). Use this when the user says things like 'initiate write-off workflow', 'draft a write-off JE', or 'create the accrual entry for expired batches'. ALWAYS show the user the full JE table (lines + per-plant breakdown + supporting detail) and ask for explicit approval before calling postWriteoffJE.",
      inputSchema: z.object({
        reason: z
          .enum([
            "expired",
            "near_expiry",
            "quarantine",
            "marked_for_deletion",
            "slow_moving",
            "all_distressed",
          ])
          .describe(
            "Distress reason to filter on. Default 'expired' = 100% write-off of past-SLED batches. Use 'all_distressed' for the union of all reasons (each batch's individual write-down %).",
          ),
      }),
      execute: async (args) => {
        return await fetchJson(`/blackline/draft-writeoff${toQuery(args)}`);
      },
    }),

    postWriteoffJE: tool({
      description:
        "Post the previously-drafted inventory write-off JE to SAP S/4HANA via the simulated BlackLine Web Services Connector. Re-drafts deterministically from the same `reason`, validates balance, and returns a SAP document number. ONLY call after the user has reviewed the draft AND explicitly approved posting (e.g. 'post it', 'approve and post', 'send to SAP', 'yes proceed'). NEVER call without prior approval in the conversation.",
      inputSchema: z.object({
        reason: z
          .enum([
            "expired",
            "near_expiry",
            "quarantine",
            "marked_for_deletion",
            "slow_moving",
            "all_distressed",
          ])
          .describe("Same reason used for draftWriteoffJE."),
      }),
      execute: async (args) => {
        const je = await fetchJson(`/blackline/draft-writeoff${toQuery(args)}`);
        return await postJson("/blackline/post", je);
      },
    }),

    getWritedownExtract: tool({
      description:
        "Distressed inventory across all plants joined with MBEW valuation. Returns per-batch detail (stock qty, standard price, stock value, distress reason, write-down %, write-down $) plus a summary aggregated by plant (line count, total stock value, total write-down, breakdown by reason). Use this for 'show me distressed inventory across all plants', write-down exposure, or any question that needs the dollar impact of distressed stock.",
      inputSchema: z.object({
        distressed_only: z
          .boolean()
          .optional()
          .describe("Default true. Set false to include all batches with their (often zero) write-down."),
      }),
      execute: async (args) => {
        return await fetchJson(`/inventory/writedown-extract${toQuery(args)}`);
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
        "Fetch the current BI-WEEKLY payroll reconciliation between Workday and SAP FI for pay group BIWEEKLY-US-CORP. Each month holds two pay periods; Workday has finalized payroll for every (worker, period), while SAP FI receives PECI's posting only after each period's pay-date. Returns one row per (worker, pay_period_end) with both sides' totals plus any orphan FI postings. A row whose pay_date is in the future is the **unposted accrual period** (fi_document_count=0 by design; the variance equals the full bi-weekly cost — that IS the accrual). A row whose pay_date is in the past is a **posted period** — SAP should match Workday and a non-zero variance is the anomaly. ALWAYS render the response as a Markdown table with these columns: Worker ID, Worker Name, Pay Period End, Status, Cost Center, Workday Total ($), SAP Posted ($), Variance ($), Notes. Pass only_mismatches=true to filter to rows that need review (this excludes the standard unposted-period rows).",
      inputSchema: z.object({
        worker_id: z
          .string()
          .optional()
          .describe("Exact Workday Worker_Reference, e.g. 'EMP-1010'"),
        pay_group: z
          .string()
          .optional()
          .describe("Pay group ID, e.g. 'BIWEEKLY-US-CORP'"),
        pay_period_end: z
          .string()
          .optional()
          .describe("Pay period end date in ISO YYYY-MM-DD, e.g. '2026-05-31'"),
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

    createPosting: tool({
      description:
        "Kick off a Vercel Workflow run that pushes an approved accrual or payroll reconciliation through to BlackLine + SAP BTP CAP, with a human approval gate in the middle. Returns posting_id and a detail_url the user can open to approve and watch the workflow steps. Use when the user says things like \"post EMP-1019's P1 accrual to BlackLine\" or \"push this to CAP\". Always include a brief, human-readable `title` and the relevant amount / GL / cost-center fields in `payload`.",
      inputSchema: z.object({
        source_type: z
          .enum(["accrual", "payroll"])
          .describe("Which side of the demo this posting is for."),
        source_id: z
          .string()
          .describe(
            "ID of the source row — accrual_id (FI/MM/CO) or payroll_id (WD/...). Pulled from the row the user is referring to.",
          ),
        source_run_id: z
          .string()
          .optional()
          .describe("Optional pipeline run_id this posting was derived from."),
        title: z
          .string()
          .describe(
            "Short human-readable label, e.g. 'EMP-1019 employer FICA shortfall (P1 2026-05-17)'.",
          ),
        payload: z
          .record(z.string(), z.unknown())
          .describe(
            "Free-form JSON pushed downstream as-is. Include amount, GL account, cost center, and any other context BlackLine/CAP need to record the journal.",
          ),
      }),
      execute: async (args) => {
        const { startPostingWorkflow } = await import("@/lib/posting-orchestration");
        return await startPostingWorkflow(args);
      },
    }),

    listPostings: tool({
      description:
        "List recent posting workflow runs (newest first). Each row shows id, source, status, and timestamps. Use to answer 'show me past postings' or 'which postings are awaiting approval'. Render as a Markdown table with these columns: ID, Title, Source, Status, Created.",
      inputSchema: z.object({}),
      execute: async () => {
        return await fetchJson("/postings");
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
