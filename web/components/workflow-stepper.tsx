import { Check, CircleAlert, CircleDot, Loader2 } from "lucide-react";

import type { PostingEvent, PostingStatus, PostingStep } from "@/lib/types";

interface StepDef {
  key: string;
  label: string;
  description: string;
  /** Event step names that mark this stage as in-progress or done. */
  startSteps?: PostingStep[];
  doneSteps: PostingStep[];
}

const STEPS: StepDef[] = [
  {
    key: "draft",
    label: "Draft created",
    description: "Posting payload prepared and recorded in DB",
    doneSteps: ["draft_created", "workflow_started"],
  },
  {
    key: "approval",
    label: "Human approval",
    description: "Awaiting reviewer decision (gate)",
    startSteps: ["workflow_started"],
    doneSteps: ["approved", "rejected"],
  },
  {
    key: "blackline",
    label: "Pushed to BlackLine",
    description: "Single batch JE file POSTed to BlackLine /journals (real HTTP)",
    startSteps: ["posting_blackline_started"],
    doneSteps: ["posting_blackline_done"],
  },
  {
    key: "cap",
    label: "Pushed to SAP BTP CAP",
    description: "POST to SAP BTP CAP /odata/v4/postings (real HTTP)",
    startSteps: ["posting_cap_started"],
    doneSteps: ["posting_cap_done"],
  },
  {
    key: "complete",
    label: "Completed",
    description: "All downstream systems acknowledged",
    doneSteps: ["completed"],
  },
];

type StepState = "pending" | "active" | "done" | "rejected" | "failed";

function stepState(
  step: StepDef,
  events: PostingEvent[],
  postingStatus: PostingStatus,
): StepState {
  const eventSteps = new Set(events.map((e) => e.step));

  if (step.key === "approval" && eventSteps.has("rejected")) return "rejected";
  if (postingStatus === "failed") {
    // Mark the first un-done step as failed.
    if (step.doneSteps.some((s) => eventSteps.has(s))) return "done";
    return "failed";
  }
  if (step.doneSteps.some((s) => eventSteps.has(s))) return "done";
  if (step.startSteps?.some((s) => eventSteps.has(s))) return "active";
  return "pending";
}

function StepIcon({ state }: { state: StepState }) {
  if (state === "done") {
    return (
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 ring-2 ring-emerald-200">
        <Check size={18} strokeWidth={2.5} />
      </div>
    );
  }
  if (state === "active") {
    return (
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary ring-2 ring-primary/30">
        <Loader2 size={18} className="animate-spin" />
      </div>
    );
  }
  if (state === "rejected") {
    return (
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-100 text-amber-700 ring-2 ring-amber-200">
        <CircleAlert size={18} />
      </div>
    );
  }
  if (state === "failed") {
    return (
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-red-100 text-red-700 ring-2 ring-red-200">
        <CircleAlert size={18} />
      </div>
    );
  }
  return (
    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary text-muted-foreground ring-2 ring-border">
      <CircleDot size={16} />
    </div>
  );
}

export function WorkflowStepper({
  events,
  status,
}: {
  events: PostingEvent[];
  status: PostingStatus;
}) {
  return (
    <ol className="relative space-y-5 border-l border-border pl-6">
      {STEPS.map((step) => {
        const state = stepState(step, events, status);
        const matchingEvent = [...events]
          .reverse()
          .find(
            (e) =>
              step.doneSteps.includes(e.step) ||
              (step.startSteps?.includes(e.step) ?? false),
          );
        return (
          <li key={step.key} className="relative">
            <div className="absolute -left-[34px] top-0">
              <StepIcon state={state} />
            </div>
            <div className="space-y-1">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-semibold text-foreground">
                  {step.label}
                </span>
                {matchingEvent && (
                  <time className="text-xs text-muted-foreground">
                    {new Date(matchingEvent.created_at).toLocaleString()}
                  </time>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{step.description}</p>
              {matchingEvent?.payload && (
                <pre className="mt-1 max-w-xl overflow-x-auto rounded border border-border bg-secondary px-2 py-1 text-[11px] leading-snug text-foreground">
                  {JSON.stringify(matchingEvent.payload, null, 2)}
                </pre>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
