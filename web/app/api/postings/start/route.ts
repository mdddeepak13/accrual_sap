import { NextResponse } from "next/server";

import { startPostingWorkflow, type StartPostingInput } from "@/lib/posting-orchestration";

/**
 * POST /api/postings/start
 *
 * Thin route handler — delegates to lib/posting-orchestration so the chat
 * agent tool and this endpoint share one code path.
 */
export async function POST(request: Request) {
  const body = (await request.json()) as StartPostingInput;
  try {
    const result = await startPostingWorkflow(body);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 },
    );
  }
}
