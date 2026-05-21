import Link from "next/link";

import { AppFooter } from "@/components/app-footer";
import { AppHeader } from "@/components/app-header";
import { StartRunForm } from "@/components/start-run-form";
import { StatusBadge } from "@/components/status-badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getHealth, listRuns } from "@/lib/api";
import { formatDuration, formatTimestamp } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function RunsDashboardPage() {
  const [health, runs] = await Promise.all([
    getHealth().catch(() => null),
    listRuns().catch(() => []),
  ]);

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
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
            Pipeline runs (audit view)
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Every chat request that triggers anomaly detection or postback
            creates a run here. Drill in for the full 13-column accrual
            table plus flagged-item reasoning.
          </p>
        </div>
        <StartRunForm />
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Service status</CardTitle>
          <CardDescription>
            Backend liveness and pipeline configuration.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {health ? (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm md:grid-cols-4">
              <div>
                <dt className="text-muted-foreground">Status</dt>
                <dd className="font-mono">{health.status}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Mock mode</dt>
                <dd className="font-mono">
                  {health.mock_mode ? "true" : "false"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Claude model</dt>
                <dd className="font-mono">{health.claude_model}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">In-flight runs</dt>
                <dd className="font-mono">{health.in_flight_runs}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-red-600">
              Backend unreachable. Is <code>uvicorn</code> running on{" "}
              <code>localhost:8000</code>?
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent runs</CardTitle>
          <CardDescription>
            Newest first. Click a run_id to see flagged items and reasoning.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No runs yet. Click &ldquo;Start new run&rdquo; to kick one off.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead className="text-right">Accruals</TableHead>
                  <TableHead className="text-right">To be posted</TableHead>
                  <TableHead className="text-right">Irregularities</TableHead>
                  <TableHead>Model</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((r) => (
                  <TableRow key={r.run_id}>
                    <TableCell>
                      <Link
                        href={`/runs/${r.run_id}`}
                        className="font-mono text-xs underline-offset-4 hover:underline"
                      >
                        {r.run_id}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={r.status} />
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {formatTimestamp(r.started_at)}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {formatDuration(r.started_at, r.finished_at)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {r.accrual_count}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {r.approved_count > 0 ? (
                        <span className="font-semibold text-emerald-700">
                          {r.approved_count}
                        </span>
                      ) : (
                        r.approved_count
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {r.flagged_count > 0 ? (
                        <span className="font-semibold text-amber-700">
                          {r.flagged_count}
                        </span>
                      ) : (
                        r.flagged_count
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {r.model}
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
