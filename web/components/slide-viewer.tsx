"use client";

import { ChevronLeft, ChevronRight, Download } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { MermaidChart } from "@/components/mermaid-chart";

interface Props {
  slides: string[];
}

export function SlideViewer({ slides }: Props) {
  const [index, setIndex] = useState(0);
  const total = slides.length;

  const go = useCallback(
    (delta: number) => {
      setIndex((i) => Math.min(total - 1, Math.max(0, i + delta)));
    },
    [total],
  );

  // Keyboard navigation.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      )
        return;
      if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
        e.preventDefault();
        go(1);
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        go(-1);
      } else if (e.key === "Home") {
        setIndex(0);
      } else if (e.key === "End") {
        setIndex(total - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, total]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 items-stretch justify-center bg-muted/30 px-4 py-4 md:px-8 md:py-6">
        <article
          className="prose prose-sm mx-auto flex h-full w-full max-w-5xl flex-col overflow-y-auto rounded-lg border bg-background px-6 py-8 shadow-sm md:prose-base md:px-10
            prose-headings:font-semibold
            prose-h1:mt-0 prose-h1:text-2xl md:prose-h1:text-3xl
            prose-h2:mt-2 prose-h2:text-lg md:prose-h2:text-xl
            prose-table:text-xs md:prose-table:text-sm
            prose-th:border prose-th:px-2 prose-th:py-1 prose-th:bg-muted
            prose-td:border prose-td:px-2 prose-td:py-1
            prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5
            prose-code:text-xs prose-code:before:content-none prose-code:after:content-none
            prose-pre:bg-slate-50 prose-pre:text-slate-900 prose-pre:border prose-pre:border-slate-200
            prose-pre:rounded-md prose-pre:p-4 prose-pre:text-xs prose-pre:leading-relaxed
            [&_pre_code]:!bg-transparent [&_pre_code]:!text-slate-900 [&_pre_code]:!p-0"
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw]}
            components={{
              // Collapse the Marp `<div class="cols">` hint into a two-col grid
              // and strip the small-note class, so the deck renders cleanly
              // even though we're not running Marp's CSS.
              div: ({ className, children, ...rest }) => {
                if (className?.includes("cols")) {
                  return (
                    <div
                      className="grid grid-cols-1 gap-6 md:grid-cols-2"
                      {...rest}
                    >
                      {children}
                    </div>
                  );
                }
                return (
                  <div className={className} {...rest}>
                    {children}
                  </div>
                );
              },
              // Render ```mermaid``` fenced blocks as actual diagrams.
              code: ({ className, children, ...rest }) => {
                const text = String(children ?? "").replace(/\n$/, "");
                if (className === "language-mermaid") {
                  return <MermaidChart chart={text} />;
                }
                return (
                  <code className={className} {...rest}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {slides[index] ?? ""}
          </ReactMarkdown>
        </article>
      </div>

      <nav className="shrink-0 border-t bg-background px-4 py-3 md:px-8">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => go(-1)}
            disabled={index === 0}
            className="gap-1"
          >
            <ChevronLeft size={14} />
            <span className="hidden md:inline">Previous</span>
          </Button>

          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="font-mono tabular-nums">
              {index + 1} / {total}
            </span>
            <a
              href="/presentation.md"
              download="accrual-engine.md"
              className="inline-flex items-center gap-1 underline-offset-4 hover:underline"
            >
              <Download size={12} />
              <span className="hidden md:inline">Markdown</span>
            </a>
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => go(1)}
            disabled={index === total - 1}
            className="gap-1"
          >
            <span className="hidden md:inline">Next</span>
            <ChevronRight size={14} />
          </Button>
        </div>
      </nav>
    </div>
  );
}
