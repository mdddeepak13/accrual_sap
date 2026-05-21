"""CLI entrypoint — run the pipeline once and print a summary.

Usage:
    python -m accrual_pipeline.run

Runs the same `run_pipeline` coroutine as POST /runs, but synchronously
(blocks until done) and prints a compact report to stdout. Exit code 0
on success, 1 on failure.
"""
from __future__ import annotations

import asyncio
import secrets
import sys

from accrual_pipeline.persistence import get_run_summary, init_db
from accrual_pipeline.pipeline import run_pipeline


def _format_summary(summary: dict[str, object]) -> str:
    lines = [
        f"Run:          {summary['run_id']}",
        f"Status:       {summary['status']}",
        f"Model:        {summary['model']}",
        f"Accruals:     {summary['accrual_count']}",
        f"Flagged:      {len(summary['flagged'])}",  # type: ignore[arg-type]
    ]
    flagged = summary.get("flagged") or []
    assert isinstance(flagged, list)
    for item in flagged:
        severity = item.get("severity") or "-"
        reason = item["reason"]
        truncated = reason if len(reason) <= 100 else reason[:97] + "..."
        lines.append(
            f"  - [{item['tool_name']}/{severity}] "
            f"{item['accrual_id']}: {truncated}"
        )
    return "\n".join(lines)


def main() -> None:
    """Run the full pipeline once and print a summary."""
    init_db()
    run_id = f"run-{secrets.token_hex(8)}"
    print(f"Starting pipeline {run_id}...", flush=True)

    try:
        asyncio.run(run_pipeline(run_id))
    except Exception as exc:
        print(f"Run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        # Still try to print the summary so the user can see what was recorded.
        summary = get_run_summary(run_id)
        if summary is not None:
            print(_format_summary(summary), file=sys.stderr)
        sys.exit(1)

    summary = get_run_summary(run_id)
    if summary is None:
        print("Run completed but summary not found — this shouldn't happen.", file=sys.stderr)
        sys.exit(1)
    print(_format_summary(summary))


if __name__ == "__main__":
    main()
