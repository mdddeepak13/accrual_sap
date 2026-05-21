// Server-side API client. Called from Server Components and Server Actions.
// Reads BACKEND_API_URL from env; defaults to the FastAPI dev port.

import type {
  Health,
  PayrollResultsResponse,
  RunDetail,
  RunSummary,
  StartRunResponse,
} from "./types";

// `||` (not `??`) so an empty string falls back too — Vercel once shipped
// us an empty-string env var that coalesced through `??` and broke the UI.
const API_BASE =
  process.env.BACKEND_API_URL || "http://localhost:8000";

interface ApiError extends Error {
  status?: number;
  body?: string;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    const err: ApiError = new Error(`API ${path} → ${res.status}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return (await res.json()) as T;
}

export async function getHealth(): Promise<Health> {
  return jsonFetch<Health>("/health");
}

export async function listRuns(): Promise<RunSummary[]> {
  const body = await jsonFetch<{ runs: RunSummary[] }>("/runs");
  return body.runs;
}

export async function getRun(runId: string): Promise<RunDetail | null> {
  try {
    return await jsonFetch<RunDetail>(`/runs/${encodeURIComponent(runId)}`);
  } catch (e) {
    if ((e as ApiError).status === 404) return null;
    throw e;
  }
}

export async function startRun(): Promise<StartRunResponse> {
  return jsonFetch<StartRunResponse>("/runs", { method: "POST" });
}

export interface PayrollResultsFilters {
  workerId?: string;
  payGroup?: string;
  payPeriodEnd?: string;
  costCenter?: string;
  onlyMismatches?: boolean;
}

export async function getPayrollResults(
  filters: PayrollResultsFilters = {},
): Promise<PayrollResultsResponse> {
  const params = new URLSearchParams();
  if (filters.workerId) params.set("worker_id", filters.workerId);
  if (filters.payGroup) params.set("pay_group", filters.payGroup);
  if (filters.payPeriodEnd) params.set("pay_period_end", filters.payPeriodEnd);
  if (filters.costCenter) params.set("cost_center", filters.costCenter);
  if (filters.onlyMismatches) params.set("only_mismatches", "true");
  const qs = params.toString();
  return jsonFetch<PayrollResultsResponse>(
    `/payroll/results${qs ? `?${qs}` : ""}`,
  );
}
