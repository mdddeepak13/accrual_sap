"use client";

import { useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { isToolUIPart } from "ai";

import type { AccrualAgentUIMessage } from "@/agent/accrual-agent";
import { PaginatedTable } from "@/components/paginated-table";

const MARKDOWN_COMPONENTS: Components = {
  table: PaginatedTable,
};

interface Props {
  message: AccrualAgentUIMessage;
}

const TOOL_LABELS: Record<string, string> = {
  "tool-getAccruals": "Fetching accruals",
  "tool-getPlan": "Looking up plan data",
  "tool-getBatches": "Fetching pharma batches",
  "tool-getWritedownExtract": "Joining MB52 + MBEW from BTP",
  "tool-draftWriteoffJE": "Drafting BlackLine JE from live SAP",
  "tool-postWriteoffJE": "Posting JE to SAP via BlackLine connector",
  "tool-detectIrregularities": "Running anomaly detection (~20s)",
  "tool-postApprovedAccruals": "Posting approved accruals to S/4",
  "tool-getPayrollResults": "Fetching payroll reconciliations",
};

function ToolPart({
  type,
  state,
  input,
  output,
}: {
  type: string;
  state: string;
  input?: unknown;
  output?: unknown;
}) {
  const [open, setOpen] = useState(false);
  const label = TOOL_LABELS[type] ?? type;
  const done = state === "output-available";
  const errored = state === "output-error";
  const rowCount: number | undefined = (() => {
    if (!output || typeof output !== "object") return undefined;
    const o = output as Record<string, unknown>;
    if (typeof o.count === "number") return o.count;
    if (typeof o.line_count === "number") return o.line_count;
    for (const key of ["accruals", "plan", "batches", "flagged", "approved", "items"]) {
      if (Array.isArray(o[key])) return (o[key] as unknown[]).length;
    }
    return undefined;
  })();

  const copyJson = () => {
    if (!output) return;
    navigator.clipboard.writeText(JSON.stringify(output, null, 2)).catch(() => {});
  };

  const downloadJson = () => {
    if (!output) return;
    const blob = new Blob([JSON.stringify(output, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${type.replace("tool-", "")}-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const statusGlyph = errored ? "⚠" : done ? "✓" : "…";
  const statusColorLight = errored
    ? "text-destructive"
    : done
      ? "text-[#00AA44]"
      : "text-primary";

  return (
    <div className="my-2 overflow-hidden rounded-md border border-border bg-secondary text-xs">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left font-mono text-foreground/80 hover:bg-secondary/70"
        onClick={() => setOpen(!open)}
      >
        <span className={`w-4 ${statusColorLight}`}>{statusGlyph}</span>
        <span className="flex-1">
          {label}
          {done && rowCount !== undefined
            ? ` · ${rowCount} record${rowCount === 1 ? "" : "s"}`
            : done
              ? " · done"
              : ""}
        </span>
        <span className="text-[10px] text-muted-foreground">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-border bg-card px-2 py-2">
          {input !== undefined && (
            <details className="group">
              <summary className="cursor-pointer font-mono text-[11px] text-muted-foreground hover:text-foreground">
                Parameters
              </summary>
              <pre className="mt-1 max-h-40 overflow-auto rounded border border-border bg-secondary p-2 text-[11px] text-foreground">
                {JSON.stringify(input, null, 2)}
              </pre>
            </details>
          )}
          {output !== undefined && (
            <>
              <details className="group">
                <summary className="cursor-pointer font-mono text-[11px] text-muted-foreground hover:text-foreground">
                  Raw output ({rowCount ?? "?"} records)
                </summary>
                <pre className="mt-1 max-h-80 overflow-auto rounded border border-border bg-secondary p-2 text-[11px] text-foreground">
                  {JSON.stringify(output, null, 2)}
                </pre>
              </details>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={copyJson}
                  className="rounded border border-border bg-card px-2 py-0.5 text-[11px] text-foreground hover:border-primary/40 hover:bg-primary/10"
                >
                  Copy JSON
                </button>
                <button
                  type="button"
                  onClick={downloadJson}
                  className="rounded border border-border bg-card px-2 py-0.5 text-[11px] text-foreground hover:border-primary/40 hover:bg-primary/10"
                >
                  Download
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div
        className={
          isUser
            ? "max-w-[85%] rounded-2xl bg-primary px-4 py-2 text-base text-primary-foreground shadow-sm"
            : "max-w-[95%] rounded-2xl border border-border bg-card px-4 py-3 text-base text-foreground shadow-[0_2px_8px_rgba(0,0,0,0.06)]"
        }
      >
        {message.parts.map((part, idx) => {
          if (part.type === "text") {
            return isUser ? (
              <p key={idx} className="whitespace-pre-wrap text-primary-foreground">
                {part.text}
              </p>
            ) : (
              <div
                key={idx}
                className="prose max-w-none text-base
                  prose-headings:font-semibold prose-headings:text-foreground
                  prose-h2:mt-4 prose-h2:text-xs prose-h2:uppercase prose-h2:tracking-wider prose-h2:text-primary
                  prose-h3:mt-3 prose-h3:text-base prose-h3:text-foreground
                  prose-p:my-2 prose-p:leading-relaxed prose-p:text-foreground prose-p:text-base
                  prose-strong:text-foreground
                  prose-a:text-primary hover:prose-a:text-[#0052A3]
                  prose-ul:my-2 prose-li:my-1 prose-li:text-foreground prose-li:text-base prose-li:marker:text-primary
                  prose-hr:border-border
                  prose-table:my-3 prose-table:block prose-table:max-w-full prose-table:overflow-x-auto prose-table:text-sm prose-table:border-collapse prose-table:tabular-nums
                  prose-th:border prose-th:border-border prose-th:px-3 prose-th:py-2 prose-th:bg-secondary prose-th:text-left prose-th:text-foreground prose-th:font-semibold prose-th:whitespace-nowrap prose-th:align-bottom
                  prose-td:border prose-td:border-border prose-td:px-3 prose-td:py-1.5 prose-td:text-foreground prose-td:whitespace-nowrap prose-td:align-top
                  prose-code:rounded prose-code:bg-secondary prose-code:px-1 prose-code:py-0.5 prose-code:text-sm prose-code:text-[#FF6B35] prose-code:before:content-none prose-code:after:content-none
                  prose-pre:rounded prose-pre:border prose-pre:border-border prose-pre:bg-secondary prose-pre:text-foreground"
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
                  {part.text}
                </ReactMarkdown>
              </div>
            );
          }
          if (isToolUIPart(part)) {
            const input =
              part.state === "input-available" ||
              part.state === "output-available"
                ? part.input
                : undefined;
            const output =
              part.state === "output-available" ? part.output : undefined;
            return (
              <ToolPart
                key={idx}
                type={part.type}
                state={part.state}
                input={input}
                output={output}
              />
            );
          }
          return null;
        })}
      </div>
    </div>
  );
}
