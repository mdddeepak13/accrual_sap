import Link from "next/link";
import { notFound } from "next/navigation";

import { AppFooter } from "@/components/app-footer";
import { AppHeader } from "@/components/app-header";
import { PostingApprovalButtons } from "@/components/posting-approval-buttons";
import { WorkflowStepper } from "@/components/workflow-stepper";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getPosting } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PostingDetailPage({ params }: Props) {
  const { id } = await params;
  const posting = await getPosting(id);
  if (!posting) notFound();

  const showApproval = posting.status === "awaiting_approval";

  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-6 md:py-10">
        <div className="mb-4 flex items-center justify-between gap-2">
          <Link
            href="/postings"
            className="text-sm text-muted-foreground underline-offset-4 hover:underline"
          >
            ← All postings
          </Link>
          <span className="font-mono text-xs text-muted-foreground">{posting.id}</span>
        </div>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">{posting.title}</CardTitle>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>
                <strong className="text-foreground">Source:</strong>{" "}
                {posting.source_type} · {posting.source_id}
              </span>
              {posting.source_run_id && (
                <span>
                  <strong className="text-foreground">Run:</strong>{" "}
                  <Link
                    href={`/runs/${encodeURIComponent(posting.source_run_id)}`}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    {posting.source_run_id}
                  </Link>
                </span>
              )}
              {posting.workflow_run_id && (
                <span>
                  <strong className="text-foreground">Workflow:</strong>{" "}
                  <span className="font-mono">{posting.workflow_run_id}</span>
                </span>
              )}
              <span>
                <strong className="text-foreground">Created:</strong>{" "}
                {formatTimestamp(posting.created_at)}
              </span>
            </div>
          </CardHeader>
          {showApproval && (
            <CardContent className="border-t border-border bg-amber-50/60 pt-4">
              <p className="mb-3 text-sm text-amber-900">
                <strong>Awaiting your approval.</strong> Approving will execute
                real HTTP POSTs to the BlackLine and SAP BTP CAP receivers and
                record the receipts below.
              </p>
              <PostingApprovalButtons postingId={posting.id} />
            </CardContent>
          )}
          {posting.error_message && (
            <CardContent className="border-t border-border bg-red-50/60 pt-4">
              <p className="text-sm text-red-900">
                <strong>Error:</strong> {posting.error_message}
              </p>
            </CardContent>
          )}
        </Card>

        <div className="grid gap-6 md:grid-cols-[2fr,1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Workflow steps</CardTitle>
            </CardHeader>
            <CardContent>
              <WorkflowStepper events={posting.events} status={posting.status} />
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Posting payload</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="max-h-96 overflow-auto rounded border border-border bg-secondary p-3 text-[11px] leading-snug text-foreground">
                  {JSON.stringify(posting.payload ?? {}, null, 2)}
                </pre>
              </CardContent>
            </Card>

            {posting.blackline_receipt && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">BlackLine receipt</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="overflow-auto rounded border border-border bg-secondary p-3 text-[11px] leading-snug text-foreground">
                    {JSON.stringify(posting.blackline_receipt, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}

            {posting.cap_receipt && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">SAP BTP CAP receipt</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="overflow-auto rounded border border-border bg-secondary p-3 text-[11px] leading-snug text-foreground">
                    {JSON.stringify(posting.cap_receipt, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>
      <AppFooter />
    </div>
  );
}
