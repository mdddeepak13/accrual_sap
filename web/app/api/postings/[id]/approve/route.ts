import { NextResponse } from "next/server";
import { resumeHook } from "workflow/api";

interface ApproveBody {
  approver?: string;
  notes?: string;
}

/**
 * POST /api/postings/[id]/approve
 *
 * Resumes the posting workflow's approval hook. The workflow then proceeds
 * to push to BlackLine + CAP. Body is optional — defaults to a "demo"
 * approver.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const body = ((await request.json().catch(() => ({}))) ?? {}) as ApproveBody;

  await resumeHook(`posting-approval:${id}`, {
    approved: true,
    approver: body.approver ?? "demo-user",
    notes: body.notes,
  });

  return NextResponse.json({ ok: true });
}
