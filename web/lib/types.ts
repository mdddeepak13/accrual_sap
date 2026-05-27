// Mirrors the Python FastAPI response shapes from persistence.get_run_summary
// and list_runs. Keep in sync with src/accrual_pipeline/persistence.py
// and src/accrual_pipeline/models.py.

export type RunStatus = "running" | "completed" | "failed";

export interface Health {
  status: string;
  mock_mode: boolean;
  claude_model: string;
  in_flight_runs: number;
}

export interface RunSummary {
  run_id: string;
  started_at: string;
  finished_at: string | null;
  model: string;
  accrual_count: number;
  status: RunStatus;
  flagged_count: number;
  approved_count: number;
}

export type Severity = "low" | "medium" | "high";

/**
 * Business-shaped accrual (the 13-field spec) as served by the backend.
 * Field names match AccrualObject in the Python models. Dates are ISO strings.
 */
export interface Accrual {
  accrual_id: string;
  company_code: string;
  posting_date: string | null;
  document_date: string | null;
  gl_account_number: string;
  gl_description: string | null;
  vendor_number: string | null;
  vendor_name: string | null;
  short_text: string | null;
  long_text: string | null;
  accrual_from_period: string | null;
  accrual_to_period: string | null;
  amount_usd: string | null; // Decimal serialized as string
  // Context fields (not shown as core columns)
  fiscal_year: string;
  accounting_document: string;
  accounting_document_item: string;
  is_reversal: boolean;
  is_reversed: boolean;
  purchase_order: string | null;
  purchase_order_item: string | null;
  po_supplier_name: string | null;
  po_latest_goods_receipt_date: string | null;
  po_is_fully_invoiced: boolean | null;
  po_purchase_order_type: string | null;
  cost_center_id: string | null;
  cost_center_name: string | null;
  cost_center_responsible: string | null;
}

interface FlaggedItemBase {
  id: number;
  accrual_id: string;
  severity: Severity | null;
  reason: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface FlaggedAccrualItem extends FlaggedItemBase {
  tool_name: "flag_stale_po_accrual" | "flag_duplicate_accrual";
  accrual: Accrual | null;
}

export interface FlaggedPayrollItem extends FlaggedItemBase {
  tool_name: "flag_payroll_accrual_mismatch";
  // Payroll flags snapshot a reconciliation row instead of an AccrualObject.
  // Field name stays `accrual` because the backend serializes both under the
  // same JSON key (see persistence.accrual_snapshot_json).
  accrual: PayrollAccrualReconciliation | null;
}

export type FlaggedItem = FlaggedAccrualItem | FlaggedPayrollItem;

/** Workday↔FI reconciliation row — shape mirrors models.PayrollAccrualReconciliation. */
export interface PayrollAccrualReconciliation {
  payroll_id: string;
  worker_id: string;
  worker_name: string;
  worker_status: string | null;
  pay_group: string;
  pay_period_start: string;
  pay_period_end: string;
  pay_date: string;
  cost_center: string | null;
  termination_date: string | null;
  days_worked: string | null;
  workday_gross: string;
  workday_net: string;
  workday_total_employer_cost: string | null;
  workday_earnings_by_code: Record<string, string>;
  workday_employer_costs_by_code: Record<string, string>;
  fi_total_earnings: string;
  fi_total_employer_cost: string;
  fi_earnings_by_gl: Record<string, string>;
  fi_employer_cost_by_gl: Record<string, string>;
  fi_cost_centers_seen: string[];
  fi_document_count: number;
  fi_line_count: number;
  fi_document_numbers: string[];
  workday_monthly_total_cost: string;
  sap_actuals_posted: string;
  accrual_variance_to_post: string;
}

export interface PayrollResultsResponse {
  reconciliations: PayrollAccrualReconciliation[];
  count: number;
  orphan_fi_lines: Record<string, unknown>[];
  total_workday_records: number;
  total_fi_payroll_lines: number;
}

export interface ApprovedItem {
  id: number;
  accrual_id: string;
  notes: string;
  accrual: Accrual | null;
  created_at: string;
}

export interface RunDetail {
  run_id: string;
  started_at: string;
  finished_at: string | null;
  model: string;
  accrual_count: number;
  status: RunStatus;
  flagged: FlaggedItem[];
  approved: ApprovedItem[];
}

export interface StartRunResponse {
  run_id: string;
  status_url: string;
}

// --- Posting workflow ---

export type PostingStatus =
  | "draft"
  | "awaiting_approval"
  | "posting_blackline"
  | "posting_cap"
  | "completed"
  | "rejected"
  | "failed";

export type PostingStep =
  | "draft_created"
  | "workflow_started"
  | "awaiting_approval"
  | "approved"
  | "rejected"
  | "posting_blackline_started"
  | "posting_blackline_done"
  | "posting_cap_started"
  | "posting_cap_done"
  | "completed"
  | "failed";

export interface PostingEvent {
  id: number;
  step: PostingStep;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface PostingSummary {
  id: string;
  source_type: "accrual" | "payroll";
  source_id: string;
  source_run_id: string | null;
  title: string;
  status: PostingStatus;
  workflow_run_id: string | null;
  approval_token: string | null;
  blackline_receipt: Record<string, unknown> | null;
  cap_receipt: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  events: PostingEvent[];
  // `payload` is null on the list endpoint (we don't ship full payloads in bulk).
  payload: Record<string, unknown> | null;
}
