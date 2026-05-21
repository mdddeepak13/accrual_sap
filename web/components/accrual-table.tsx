import { SeverityBadge } from "@/components/severity-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Accrual, FlaggedItem } from "@/lib/types";

/**
 * Renders the 13 business fields from the requirement as a table.
 *
 * `flagged` toggles an extra "Irregularity" column at the end showing the
 * severity badge + reason text for that row. When false, the table is used
 * for "Accruals to be posted".
 */
interface Props {
  rows: Array<{
    accrual: Accrual | null;
    notes?: string;
    flag?: FlaggedItem;
  }>;
  mode: "approved" | "flagged";
}

const fmtDate = (v: string | null) => {
  if (!v) return "—";
  // Backend emits YYYY-MM-DD or full ISO — strip to date.
  return v.length > 10 ? v.slice(0, 10) : v;
};

const fmtAmount = (v: string | null) => {
  if (!v) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
};

export function AccrualTable({ rows, mode }: Props) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {mode === "approved"
          ? "No accruals approved for posting in this run."
          : "No irregularities in this run."}
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <Table className="text-xs">
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">Sl.no.</TableHead>
            <TableHead>Company</TableHead>
            <TableHead>Posting Date</TableHead>
            <TableHead>Doc Date</TableHead>
            <TableHead>GL Acct #</TableHead>
            <TableHead>GL Description</TableHead>
            <TableHead>Vendor #</TableHead>
            <TableHead>Vendor Name</TableHead>
            <TableHead>Short Text</TableHead>
            <TableHead>Long Text</TableHead>
            <TableHead>Accr. From</TableHead>
            <TableHead>Accr. To</TableHead>
            <TableHead className="text-right">Amount (USD)</TableHead>
            {mode === "flagged" ? (
              <TableHead>Irregularity</TableHead>
            ) : (
              <TableHead>Approval notes</TableHead>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, idx) => {
            const a = row.accrual;
            if (!a) {
              return (
                <TableRow key={idx}>
                  <TableCell colSpan={14} className="text-muted-foreground">
                    (accrual snapshot missing — re-run the pipeline)
                  </TableCell>
                </TableRow>
              );
            }
            return (
              <TableRow key={a.accrual_id + idx}>
                <TableCell className="font-mono">{idx + 1}</TableCell>
                <TableCell className="font-mono">{a.company_code}</TableCell>
                <TableCell className="font-mono">
                  {fmtDate(a.posting_date)}
                </TableCell>
                <TableCell className="font-mono">
                  {fmtDate(a.document_date)}
                </TableCell>
                <TableCell className="font-mono">
                  {a.gl_account_number}
                </TableCell>
                <TableCell>{a.gl_description ?? "—"}</TableCell>
                <TableCell className="font-mono">
                  {a.vendor_number ?? "—"}
                </TableCell>
                <TableCell>{a.vendor_name ?? "—"}</TableCell>
                <TableCell className="max-w-[16ch] truncate" title={a.short_text ?? ""}>
                  {a.short_text ?? "—"}
                </TableCell>
                <TableCell className="max-w-[28ch] truncate" title={a.long_text ?? ""}>
                  {a.long_text ?? "—"}
                </TableCell>
                <TableCell className="font-mono">
                  {fmtDate(a.accrual_from_period)}
                </TableCell>
                <TableCell className="font-mono">
                  {fmtDate(a.accrual_to_period)}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {fmtAmount(a.amount_usd)}
                </TableCell>
                {mode === "flagged" && row.flag ? (
                  <TableCell className="max-w-[40ch]">
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <span className="rounded border px-2 py-0.5 font-mono text-xs text-muted-foreground">
                          {row.flag.tool_name.replace("flag_", "")}
                        </span>
                        <SeverityBadge severity={row.flag.severity} />
                      </div>
                      <span className="text-xs leading-snug text-foreground/80">
                        {row.flag.reason}
                      </span>
                    </div>
                  </TableCell>
                ) : (
                  <TableCell className="max-w-[40ch] text-xs text-foreground/80">
                    {row.notes ?? "—"}
                  </TableCell>
                )}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
