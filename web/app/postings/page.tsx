import Link from "next/link";

import { AppFooter } from "@/components/app-footer";
import { AppHeader } from "@/components/app-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listPostings } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import type { PostingStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

const STATUS_CLASSES: Record<PostingStatus, string> = {
  draft: "bg-slate-100 text-slate-700",
  awaiting_approval: "bg-amber-100 text-amber-800",
  posting_blackline: "bg-sky-100 text-sky-800",
  posting_cap: "bg-sky-100 text-sky-800",
  completed: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-800",
  failed: "bg-red-100 text-red-800",
};

function StatusPill({ status }: { status: PostingStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
        STATUS_CLASSES[status] ?? "bg-slate-100 text-slate-700"
      }`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

export default async function PostingsPage() {
  const postings = await listPostings().catch(() => []);

  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-6 md:py-10">
        <div className="mb-4">
          <Link
            href="/"
            className="text-sm text-muted-foreground underline-offset-4 hover:underline"
          >
            ← Back to chat
          </Link>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Postings</CardTitle>
            <p className="text-sm text-muted-foreground">
              Workflow runs that push approved accruals + payroll into
              BlackLine and SAP BTP CAP. Most recent first.
            </p>
          </CardHeader>
          <CardContent>
            {postings.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No postings yet. Start one from chat (&quot;Push EMP-1019&apos;s P1
                accrual&quot;) or from a flagged-items page.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {postings.map((p) => (
                    <TableRow key={p.id} className="hover:bg-secondary/40">
                      <TableCell className="font-mono text-xs">
                        <Link
                          href={`/postings/${encodeURIComponent(p.id)}`}
                          className="text-primary underline-offset-4 hover:underline"
                        >
                          {p.id}
                        </Link>
                      </TableCell>
                      <TableCell className="max-w-md truncate">{p.title}</TableCell>
                      <TableCell className="text-xs">
                        <span className="rounded bg-secondary px-1.5 py-0.5">
                          {p.source_type}
                        </span>{" "}
                        <span className="text-muted-foreground">{p.source_id}</span>
                      </TableCell>
                      <TableCell>
                        <StatusPill status={p.status} />
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatTimestamp(p.created_at)}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatTimestamp(p.updated_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </main>
      <AppFooter />
    </div>
  );
}
