/**
 * Vercel Workflow DevKit orchestration for pushing an approved accrual or
 * payroll reconciliation through to BlackLine + SAP BTP CAP.
 *
 * The workflow is the source of truth for the multi-step process; the
 * FastAPI backend is just persistence — every step calls `/postings/{id}/event`
 * so the UI stepper sees the same state the workflow is in.
 *
 * Flow:
 *   workflow_started
 *     → (hook) awaiting human approval
 *   approved | rejected
 *     → posting_blackline_started → real HTTP POST to /postback/blackline-mock → posting_blackline_done
 *     → posting_cap_started → real HTTP POST to /postback/cap-mock → posting_cap_done
 *   completed
 */

import { FatalError, createHook } from "workflow";

const BACKEND_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

interface PostingPayload {
  amount?: number | string;
  gl_account?: string;
  cost_center?: string;
  worker_id?: string;
  pay_period_end?: string;
  notes?: string;
  [key: string]: unknown;
}

interface ApprovalResult {
  approved: boolean;
  approver?: string;
  notes?: string;
}

async function recordEvent(
  postingId: string,
  step: string,
  payload?: Record<string, unknown>,
): Promise<void> {
  "use step";
  const res = await fetch(`${BACKEND_URL}/postings/${postingId}/event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step, payload: payload ?? null }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new FatalError(
      `Failed to record event ${step} for posting ${postingId}: HTTP ${res.status} ${body}`,
    );
  }
}

async function postToBlackline(
  postingId: string,
  title: string,
  payload: PostingPayload,
): Promise<Record<string, unknown>> {
  "use step";
  const body = {
    source_type: "posting",
    source_id: postingId,
    title,
    payload,
  };
  const res = await fetch(`${BACKEND_URL}/postback/blackline-mock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new FatalError(`BlackLine post failed: HTTP ${res.status}`);
  }
  return (await res.json()) as Record<string, unknown>;
}

async function postToCAP(
  postingId: string,
  title: string,
  payload: PostingPayload,
  blacklineReceipt: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  "use step";
  const body = {
    source_type: "posting",
    source_id: postingId,
    title,
    payload,
    upstream_blackline: blacklineReceipt,
  };
  const res = await fetch(`${BACKEND_URL}/postback/cap-mock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new FatalError(`SAP BTP CAP post failed: HTTP ${res.status}`);
  }
  return (await res.json()) as Record<string, unknown>;
}

export async function postingWorkflow(
  postingId: string,
  title: string,
  payload: PostingPayload,
): Promise<{ status: "completed" | "rejected"; blackline?: unknown; cap?: unknown }> {
  "use workflow";

  await recordEvent(postingId, "workflow_started");

  // Deterministic token so the UI can resume by posting id alone.
  using hook = createHook<ApprovalResult>({
    token: `posting-approval:${postingId}`,
  });

  const approval = await hook;

  if (!approval.approved) {
    await recordEvent(postingId, "rejected", {
      approver: approval.approver ?? "(unknown)",
      notes: approval.notes ?? null,
    });
    return { status: "rejected" };
  }

  await recordEvent(postingId, "approved", {
    approver: approval.approver ?? "(unknown)",
    notes: approval.notes ?? null,
  });

  await recordEvent(postingId, "posting_blackline_started");
  const blacklineReceipt = await postToBlackline(postingId, title, payload);
  await recordEvent(postingId, "posting_blackline_done", blacklineReceipt);

  await recordEvent(postingId, "posting_cap_started");
  const capReceipt = await postToCAP(postingId, title, payload, blacklineReceipt);
  await recordEvent(postingId, "posting_cap_done", capReceipt);

  await recordEvent(postingId, "completed");

  return { status: "completed", blackline: blacklineReceipt, cap: capReceipt };
}
