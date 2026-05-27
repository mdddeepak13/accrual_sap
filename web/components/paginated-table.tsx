"use client";

import { Children, cloneElement, isValidElement, useState, type ReactElement, type ReactNode } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

const COLLAPSE_THRESHOLD = 10;

/**
 * Markdown-table replacement that collapses tables with more than
 * COLLAPSE_THRESHOLD rows. The "last row half-cut" complaint comes from large
 * reconciliation tables (40+ rows) rendered into a chat bubble — by default
 * we show only the first 10 plus a toggle to expand.
 */
export function PaginatedTable({ children }: { children?: ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  const childArray = Children.toArray(children);

  const thead = childArray.find(
    (c): c is ReactElement<{ children?: ReactNode }> =>
      isValidElement(c) && c.type === "thead",
  );
  const tbody = childArray.find(
    (c): c is ReactElement<{ children?: ReactNode }> =>
      isValidElement(c) && c.type === "tbody",
  );

  const bodyChildren = tbody ? Children.toArray(tbody.props.children) : [];
  const trChildren = bodyChildren.filter(
    (c) => isValidElement(c) && c.type === "tr",
  );
  const totalRows = trChildren.length;
  const needsPagination = totalRows > COLLAPSE_THRESHOLD;
  const showAll = expanded || !needsPagination;

  let renderedTbody = tbody;
  if (needsPagination && !showAll && tbody) {
    let trCount = 0;
    const sliced = bodyChildren.filter((c) => {
      if (isValidElement(c) && c.type === "tr") {
        trCount += 1;
        return trCount <= COLLAPSE_THRESHOLD;
      }
      return true;
    });
    renderedTbody = cloneElement(tbody, undefined, sliced);
  }

  return (
    <div className="my-3">
      <div className="max-w-full overflow-x-auto rounded-md border border-border">
        <table className="w-full border-collapse text-sm tabular-nums">
          {thead}
          {renderedTbody}
        </table>
      </div>
      {needsPagination && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-border bg-secondary px-3 py-1.5 text-xs font-medium text-foreground hover:bg-primary/10 hover:text-primary hover:border-primary/40"
          aria-expanded={expanded}
        >
          {expanded ? (
            <>
              <ChevronUp size={14} />
              Collapse to first {COLLAPSE_THRESHOLD}
            </>
          ) : (
            <>
              <ChevronDown size={14} />
              Show all {totalRows} rows
            </>
          )}
        </button>
      )}
    </div>
  );
}
