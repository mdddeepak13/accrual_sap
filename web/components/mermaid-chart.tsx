"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  chart: string;
}

/**
 * Client-side mermaid renderer. Dynamically imports mermaid to keep the
 * main bundle small and avoid SSR issues.
 *
 * Explicit light theme + a white-background container so diagrams render
 * reliably regardless of page prose styles. The "neutral" theme draws
 * cleaner lines / borders than "default" for technical architecture work.
 */
export function MermaidChart({ chart }: Props) {
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const idRef = useRef(
    `mermaid-${Math.random().toString(36).slice(2, 10)}`,
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          securityLevel: "loose",
          themeVariables: {
            background: "#ffffff",
            primaryColor: "#f4f6fa",
            primaryTextColor: "#0f172a",
            primaryBorderColor: "#1e293b",
            secondaryColor: "#fef3c7",
            secondaryTextColor: "#0f172a",
            tertiaryColor: "#e0e7ff",
            tertiaryTextColor: "#0f172a",
            lineColor: "#1e293b",
            textColor: "#0f172a",
            mainBkg: "#f4f6fa",
            nodeBorder: "#1e293b",
            clusterBkg: "#ffffff",
            clusterBorder: "#94a3b8",
            edgeLabelBackground: "#ffffff",
            fontFamily: "inherit",
            fontSize: "14px",
          },
          flowchart: {
            htmlLabels: true,
            curve: "basis",
            padding: 12,
          },
          sequence: {
            actorMargin: 50,
            width: 150,
            messageFontSize: 13,
            actorFontSize: 13,
          },
        });
        const { svg } = await mermaid.render(idRef.current, chart);
        if (!cancelled) setSvg(svg);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chart]);

  if (error) {
    return (
      <pre className="my-4 overflow-x-auto rounded border border-dashed bg-muted/40 p-3 text-xs text-red-700">
        Diagram failed to render:{"\n"}
        {error}
      </pre>
    );
  }
  if (!svg) {
    return (
      <div className="my-4 rounded border border-dashed bg-white p-4 text-xs text-muted-foreground">
        Rendering diagram…
      </div>
    );
  }
  return (
    <div className="my-4 overflow-x-auto rounded-md border bg-white p-4">
      <div
        className="mermaid-container mx-auto min-w-fit
          [&_svg]:h-auto [&_svg]:max-w-none [&_svg]:bg-white
          [&_.flowchart-link]:!stroke-[#1e293b] [&_.flowchart-link]:!stroke-[1.5]
          [&_.messageLine0]:!stroke-[#1e293b] [&_.messageLine1]:!stroke-[#1e293b]
          [&_.marker]:!fill-[#1e293b] [&_.marker]:!stroke-[#1e293b]
          [&_.edgePath_path]:!stroke-[#1e293b] [&_.edgePath_path]:!stroke-[1.5]
          [&_.arrowheadPath]:!fill-[#1e293b] [&_.arrowheadPath]:!stroke-[#1e293b]
          [&_text]:!fill-[#0f172a]
          [&_.nodeLabel]:!text-[13px] [&_foreignObject_div]:!text-[13px] [&_foreignObject_div]:!leading-tight"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  );
}
