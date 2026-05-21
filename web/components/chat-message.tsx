"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { isToolUIPart } from "ai";

import type { AccrualAgentUIMessage } from "@/agent/accrual-agent";

interface Props {
  message: AccrualAgentUIMessage;
}

const TOOL_LABELS: Record<string, string> = {
  "tool-getAccruals": "Fetching accruals",
  "tool-getPlan": "Looking up plan data",
  "tool-getBatches": "Fetching pharma batches",
  "tool-detectIrregularities": "Running anomaly detection (~20s)",
  "tool-postApprovedAccruals": "Posting approved accruals to S/4",
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
    for (const key of ["accruals", "plan", "batches", "flagged", "approved"]) {
      if (Array.isArray(o[key])) return (o[key] as unknown[]).length;
    }
    return undefined;
  })();

  const copyJson = () => {
    if (!output) return;
    navigator.clipboard
      .writeText(JSON.stringify(output, null, 2))
      .catch(() => {});
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

  return (
    <div className="my-1.5 rounded-md border border-dashed bg-muted/40 text-xs">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-2 py-1.5 text-left font-mono text-muted-foreground hover:bg-muted/60"
        onClick={() => setOpen(!open)}
      >
        <span className="w-4">{errored ? "⚠" : done ? "✓" : "…"}</span>
        <span className="flex-1">
          {label}
          {done && rowCount !== undefined
            ? ` · ${rowCount} record${rowCount === 1 ? "" : "s"}`
            : done
              ? " · done"
              : ""}
        </span>
        <span className="text-[10px]">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-dashed px-2 py-2">
          {input !== undefined && (
            <details className="group">
              <summary className="cursor-pointer font-mono text-[11px] text-foreground/70">
                Parameters
              </summary>
              <pre className="mt-1 max-h-40 overflow-auto rounded bg-background p-2 text-[11px]">
                {JSON.stringify(input, null, 2)}
              </pre>
            </details>
          )}
          {output !== undefined && (
            <>
              <details className="group">
                <summary className="cursor-pointer font-mono text-[11px] text-foreground/70">
                  Raw output ({rowCount ?? "?"} records)
                </summary>
                <pre className="mt-1 max-h-80 overflow-auto rounded bg-background p-2 text-[11px]">
                  {JSON.stringify(output, null, 2)}
                </pre>
              </details>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={copyJson}
                  className="rounded border px-2 py-0.5 text-[11px] hover:bg-background"
                >
                  Copy JSON
                </button>
                <button
                  type="button"
                  onClick={downloadJson}
                  className="rounded border px-2 py-0.5 text-[11px] hover:bg-background"
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
            ? "max-w-[85%] rounded-lg bg-foreground px-4 py-2 text-sm text-background"
            : "max-w-[95%] rounded-lg bg-muted/50 px-4 py-3 text-sm"
        }
      >
        {message.parts.map((part, idx) => {
          if (part.type === "text") {
            return isUser ? (
              <p key={idx} className="whitespace-pre-wrap">
                {part.text}
              </p>
            ) : (
              <div
                key={idx}
                className="prose prose-sm max-w-none
                  prose-headings:font-semibold prose-headings:text-foreground
                  prose-h2:mt-4 prose-h2:text-sm prose-h2:uppercase prose-h2:tracking-wide prose-h2:text-muted-foreground
                  prose-p:my-1.5 prose-p:leading-relaxed
                  prose-ul:my-1.5 prose-li:my-0.5
                  prose-table:my-2 prose-table:text-xs
                  prose-th:border prose-th:px-2 prose-th:py-1 prose-th:bg-muted
                  prose-td:border prose-td:px-2 prose-td:py-1
                  prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5
                  prose-code:text-xs prose-code:before:content-none prose-code:after:content-none"
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
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
