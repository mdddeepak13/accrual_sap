"use client";

import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";

export const SUGGESTION_GROUPS: {
  heading: string;
  prompts: string[];
}[] = [
  {
    heading: "Current period",
    prompts: [
      "Show me current accruals",
      "Which ones look like duplicates or stale POs?",
      "What accruals should be posted this month?",
    ],
  },
  {
    heading: "Actuals vs plan",
    prompts: [
      "Compare April 2026 actuals vs plan for IT expenses",
      "Which cost centers are over budget in April 2026?",
      "Flag all GL accounts with more than 20% variance vs plan",
    ],
  },
  {
    heading: "Period comparisons",
    prompts: [
      "Year-over-year comparison for GL 62 (travel) in 2025 vs 2026",
      "Compare Jan 2025 vs Jan 2024 for IT expenses",
      "Show travel expenses by cost center for 2026",
    ],
  },
  {
    heading: "Drill-down",
    prompts: [
      "Top 5 vendors by accrual amount",
      "Show me all professional services accruals",
      "What is driving the travel expense variance?",
    ],
  },
  {
    heading: "Pharma inventory",
    prompts: [
      "Show me distressed inventory across all plants",
      "Which batches are expired or near expiry?",
      "What's in quarantine right now?",
      "Slow-moving pharma batches (no movement in 1 year)",
      "Antibiotic batches at write-off risk",
    ],
  },
];

interface Props {
  onPick: (prompt: string) => void;
  onNewChat?: () => void;
  disabled?: boolean;
}

export function SuggestionsList({ onPick, onNewChat, disabled }: Props) {
  return (
    <div className="flex h-full flex-col">
      {onNewChat && (
        <div className="shrink-0 border-b p-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onNewChat}
            className="w-full justify-start gap-2"
          >
            <Plus size={14} />
            New chat
          </Button>
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-3">
        <p className="mb-3 px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Example questions
        </p>
        <nav className="space-y-4">
          {SUGGESTION_GROUPS.map((group) => (
            <div key={group.heading}>
              <h3 className="mb-1.5 px-1 text-xs font-semibold text-foreground/80">
                {group.heading}
              </h3>
              <ul className="space-y-1">
                {group.prompts.map((prompt) => (
                  <li key={prompt}>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => onPick(prompt)}
                      className="w-full rounded-md px-2 py-1.5 text-left text-xs leading-snug text-foreground/80 hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {prompt}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </div>
    </div>
  );
}
