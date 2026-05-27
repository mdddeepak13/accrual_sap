// Server-only orchestration shared by the chat agent tool and the
// /api/postings/start route handler. Keeps "create draft + start workflow +
// attach workflow_run_id" in one place so the two callers can't drift.

import { start } from "workflow/api";

import { postingWorkflow } from "@/workflows/posting";

const BACKEND_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

export interface StartPostingInput {
  source_type: "accrual" | "payroll";
  source_id: string;
  source_run_id?: string;
  title: string;
  payload: Record<string, unknown>;
}

export interface StartPostingResult {
  posting_id: string;
  workflow_run_id: string;
  detail_url: string;
}

export async function startPostingWorkflow(
  input: StartPostingInput,
): Promise<StartPostingResult> {
  const draftRes = await fetch(`${BACKEND_URL}/postings/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!draftRes.ok) {
    const body = await draftRes.text().catch(() => "");
    throw new Error(`POST /postings/draft → HTTP ${draftRes.status} ${body}`);
  }
  const draft = (await draftRes.json()) as { id: string; title: string };

  const run = await start(postingWorkflow, [draft.id, draft.title, input.payload]);

  await fetch(`${BACKEND_URL}/postings/${draft.id}/workflow`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workflow_run_id: run.runId }),
  }).catch(() => {
    // Non-fatal: the workflow is already running. Failing to record the
    // run_id only affects audit visibility, not correctness.
  });

  return {
    posting_id: draft.id,
    workflow_run_id: run.runId,
    detail_url: `/postings/${draft.id}`,
  };
}
