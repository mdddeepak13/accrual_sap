import Link from "next/link";
import { notFound } from "next/navigation";

import { AccrualTable } from "@/components/accrual-table";
import { StatusBadge } from "@/components/status-badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getRun } from "@/lib/api";
import { formatDuration, formatTimestamp } from "@/lib/format";
import type {
  ApprovedItem,
  FlaggedAccrualItem,
  FlaggedItem,
  FlaggedPayrollItem,
} from "@/lib/types";

function isPayrollFlag(item: FlaggedItem): item is FlaggedPayrollItem {
  return item.tool_name === "flag_payroll_accrual_mismatch";
}

function isAccrualFlag(item: FlaggedItem): item is FlaggedAccrualItem {
  return item.tool_name !== "flag_payroll_accrual_mismatch";
}

function isAccrualApproved(item: ApprovedItem): boolean {
  // ApprovedItem.accrual is the snapshot; payroll snapshots have
  // `workday_gross`, FI snapshots have `company_code`.
  return item.accrual === null || "company_code" in item.accrual;
}

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ runId: string }> };

export async function generateMetadata({ params }: Props) {
  const { runId } = await params;
  return { title: `Run ${runId}` };
}

export default async function RunDetailPage({ params }: Props) {
  const { runId } = await params;
  const run = await getRun(runId);
  if (!run) notFound();

  // Payroll items have a different snapshot shape (PayrollAccrualReconciliation),
  // so they're rendered in their own section below; the AccrualTable only
  // handles FI-style accruals.
  const approvedRows = run.approved.filter(isAccrualApproved).map((a) => ({
    accrual: a.accrual,
    notes: a.notes,
  }));
  const flaggedAccrualItems = run.flagged.filter(isAccrualFlag);
  const flaggedPayrollItems = run.flagged.filter(isPayrollFlag);
  const flaggedRows = flaggedAccrualItems.map((f) => ({
    accrual: f.accrual,
    flag: f,
  }));

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <Link
        href="/"
        className="mb-4 inline-block text-sm text-muted-foreground underline-offset-4 hover:underline"
      >
        ← All runs
      </Link>

      <div className="mb-8">
        <h1 className="font-mono text-2xl font-semibold tracking-tight">
          {run.run_id}
        </h1>
        <div className="mt-2 flex items-center gap-3 text-sm text-muted-foreground">
          <StatusBadge status={run.status} />
          <span>·</span>
          <span className="font-mono">{run.model}</span>
        </div>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Run metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm md:grid-cols-5">
            <div>
              <dt className="text-muted-foreground">Started</dt>
              <dd className="font-mono text-xs">
                {formatTimestamp(run.started_at)}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Finished</dt>
              <dd className="font-mono text-xs">
                {formatTimestamp(run.finished_at)}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Duration</dt>
              <dd className="font-mono text-xs">
                {formatDuration(run.started_at, run.finished_at)}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Accruals reviewed</dt>
              <dd className="font-mono text-xs">{run.accrual_count}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">
                Posted / Irregularities
              </dt>
              <dd className="font-mono text-xs">
                <span className="text-emerald-700">{run.approved.length}</span>
                {" / "}
                <span className="text-amber-700">{run.flagged.length}</span>
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">
            Accruals to be posted ({run.approved.length})
          </CardTitle>
          <CardDescription>
            Claude approved these as clean. At the end of the run they are
            collected into a single BlackLine JE file and sent to BlackLine
            in one batch POST — not posted individually.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AccrualTable rows={approvedRows} mode="approved" />
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">
            FI irregularities ({flaggedAccrualItems.length})
          </CardTitle>
          <CardDescription>
            Stale POs and probable duplicates — require human review before
            period close.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AccrualTable rows={flaggedRows} mode="flagged" />
        </CardContent>
      </Card>

      {flaggedPayrollItems.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Payroll mismatches ({flaggedPayrollItems.length})
            </CardTitle>
            <CardDescription>
              Workday ↔ SAP FI reconciliation — rows where PECI did not deliver
              what Workday says is the authoritative payroll result.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-left text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3">Worker</th>
                    <th className="py-2 pr-3">Cost center</th>
                    <th className="py-2 pr-3">Mismatch</th>
                    <th className="py-2 pr-3">Severity</th>
                    <th className="py-2 pr-3 text-right">Workday $</th>
                    <th className="py-2 pr-3 text-right">FI $</th>
                    <th className="py-2 pr-3">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {flaggedPayrollItems.map((f) => {
                    const p = f.payload as Record<string, string>;
                    return (
                      <tr key={f.id} className="border-t">
                        <td className="py-2 pr-3 font-mono">
                          {f.accrual?.worker_name ?? p.worker_id}
                          <br />
                          <span className="text-muted-foreground">
                            {p.worker_id}
                          </span>
                        </td>
                        <td className="py-2 pr-3 font-mono">
                          {f.accrual?.cost_center ?? "—"}
                        </td>
                        <td className="py-2 pr-3">{p.mismatch_type}</td>
                        <td className="py-2 pr-3">{f.severity ?? "—"}</td>
                        <td className="py-2 pr-3 text-right font-mono">
                          {p.workday_amount || "—"}
                        </td>
                        <td className="py-2 pr-3 text-right font-mono">
                          {p.fi_amount || "—"}
                        </td>
                        <td className="py-2 pr-3">{f.reason}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
