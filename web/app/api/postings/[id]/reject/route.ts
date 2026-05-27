import { NextResponse } from "next/server";
import { resumeHook } from "workflow/api";

interface RejectBody {
  approver?: string;
  notes?: string;
}

/**
 * POST /api/postings/[id]/reject
 *
 * Resumes the posting workflow's approval hook with approved=false. The
 * workflow records the rejection and exits without touching BlackLine/CAP.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const body = ((await request.json().catch(() => ({}))) ?? {}) as RejectBody;

  await resumeHook(`posting-approval:${id}`, {
    approved: false,
    approver: body.approver ?? "demo-user",
    notes: body.notes,
  });

  return NextResponse.json({ ok: true });
}
