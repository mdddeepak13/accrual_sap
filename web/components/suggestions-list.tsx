"use client";

import { useState, type ReactNode } from "react";
import {
  ChevronDown,
  type LucideIcon,
  MoreHorizontal,
  Pill,
  Plus,
  ShoppingCart,
  Sparkles,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";

export interface SuggestionGroup {
  heading: string;
  description: string;
  icon: LucideIcon;
  /** Tailwind class fragments — literal so the JIT picks them up. */
  color: {
    iconBg: string;
    iconText: string;
    accent: string;
    ring: string;
  };
  prompts: string[];
}

export const SUGGESTION_GROUPS: SuggestionGroup[] = [
  {
    heading: "Pharma Reserve",
    description: "Distressed inventory, expiry, write-offs.",
    icon: Pill,
    color: {
      iconBg: "bg-emerald-100",
      iconText: "text-emerald-700",
      accent: "bg-emerald-500",
      ring: "hover:border-emerald-400 hover:shadow-emerald-100",
    },
    prompts: [
      "Show me distressed inventory across all plants with values high level overview",
      "Initiate write-off workflow in SAP for all 35 expired batches",
      "Which batches are expired or near expiry?",
      "What's in quarantine right now?",
      "Slow-moving pharma batches (no movement in 1 year)",
      "Antibiotic batches at write-off risk",
    ],
  },
  {
    heading: "Workday Payroll Expense",
    description: "Workday ↔ SAP FI reconciliations.",
    icon: Users,
    color: {
      iconBg: "bg-sky-100",
      iconText: "text-sky-700",
      accent: "bg-sky-500",
      ring: "hover:border-sky-400 hover:shadow-sky-100",
    },
    prompts: [
      "What's the bi-weekly accrual to book for the unposted Period 2 (5/18–5/31)?",
      "Did EMP-1010 get prorated correctly after resigning on May 20?",
      "Which workers have FI-side mismatches in the posted Period 1?",
      "Show all cost-center routing errors in this period's payroll",
      "List orphan FI payroll postings with no Workday counterpart",
      "Why is EMP-1019's employer FICA short?",
    ],
  },
  {
    heading: "Purchase Order Expense",
    description: "PO-backed accruals & vendor activity.",
    icon: ShoppingCart,
    color: {
      iconBg: "bg-violet-100",
      iconText: "text-violet-700",
      accent: "bg-violet-500",
      ring: "hover:border-violet-400 hover:shadow-violet-100",
    },
    prompts: [
      "Show me current PO-backed accruals",
      "Top 5 vendors by accrual amount",
      "Which ones look like duplicates or stale POs?",
      "Show me all professional services accruals",
      "What accruals should be posted this month?",
    ],
  },
  {
    heading: "Others",
    description: "Budget, variance, GL drill-downs.",
    icon: MoreHorizontal,
    color: {
      iconBg: "bg-orange-100",
      iconText: "text-orange-700",
      accent: "bg-orange-500",
      ring: "hover:border-orange-400 hover:shadow-orange-100",
    },
    prompts: [
      "Compare April 2026 actuals vs plan for IT expenses",
      "Which cost centers are over budget in April 2026?",
      "Flag all GL accounts with more than 20% variance vs plan",
      "Year-over-year comparison for GL 62 (travel) in 2025 vs 2026",
      "What is driving the travel expense variance?",
    ],
  },
];

interface Props {
  onPick: (prompt: string) => void;
  onNewChat?: () => void;
  disabled?: boolean;
}

export function SuggestionsList({ onPick, onNewChat, disabled }: Props) {
  const [openIdx, setOpenIdx] = useState<number>(0);

  return (
    <div className="flex h-full flex-col bg-sidebar">
      {onNewChat && (
        <div className="shrink-0 border-b border-sidebar-border p-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onNewChat}
            className="w-full justify-start gap-2 border-border bg-background text-foreground hover:bg-primary/10 hover:text-primary hover:border-primary/40"
          >
            <Plus size={14} />
            New chat
          </Button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-2 py-3">
        <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Example questions
        </p>

        <nav className="space-y-1.5">
          {SUGGESTION_GROUPS.map((group, idx) => {
            const Icon = group.icon;
            const isOpen = openIdx === idx;
            return (
              <div
                key={group.heading}
                className={`overflow-hidden rounded-lg border transition ${
                  isOpen
                    ? "border-primary/30 bg-card shadow-sm"
                    : "border-border bg-card"
                }`}
              >
                <button
                  type="button"
                  onClick={() => setOpenIdx(isOpen ? -1 : idx)}
                  className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left hover:bg-secondary"
                  aria-expanded={isOpen}
                >
                  <span className="flex items-center gap-2.5">
                    <span
                      className={`flex h-7 w-7 items-center justify-center rounded-md ${group.color.iconBg} ${group.color.iconText}`}
                    >
                      <Icon size={15} />
                    </span>
                    <span className="text-sm font-semibold leading-tight text-foreground">
                      {group.heading}
                    </span>
                  </span>
                  <ChevronDown
                    size={14}
                    className={`shrink-0 text-muted-foreground transition-transform ${
                      isOpen ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {isOpen && (
                  <ul className="space-y-0.5 border-t border-border px-1.5 pb-1.5 pt-1">
                    {group.prompts.map((prompt) => (
                      <li key={prompt}>
                        <button
                          type="button"
                          disabled={disabled}
                          onClick={() => onPick(prompt)}
                          className="w-full rounded-md px-2.5 py-2 text-left text-[13px] leading-snug text-foreground/80 hover:bg-primary/10 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {prompt}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </nav>
      </div>
    </div>
  );
}

/**
 * Welcome / category-picker for the empty chat state — white cards on the
 * subtle blue-gray background. Picking a category reveals its prompts inline.
 */
export function WelcomePicker({
  onPick,
  disabled,
}: {
  onPick: (prompt: string) => void;
  disabled?: boolean;
}) {
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const active = activeIdx == null ? null : SUGGESTION_GROUPS[activeIdx];

  return (
    <div className="relative mx-auto w-full max-w-5xl pt-8 md:pt-12">
      <div className="relative">
        <div className="mb-6 flex items-center gap-2 text-xs">
          <Sparkles size={14} className="text-primary" />
          <span className="font-semibold uppercase tracking-wider text-muted-foreground">
            Choose a workflow
          </span>
        </div>

        {active == null ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {SUGGESTION_GROUPS.map((group, idx) => {
              const Icon = group.icon;
              return (
                <button
                  key={group.heading}
                  type="button"
                  onClick={() => setActiveIdx(idx)}
                  className={`group relative flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card p-5 text-left shadow-[0_2px_8px_rgba(0,0,0,0.06)] transition hover:shadow-lg ${group.color.ring}`}
                >
                  <span
                    aria-hidden
                    className={`absolute inset-x-0 top-0 h-1 ${group.color.accent}`}
                  />
                  <div className="mb-3 flex items-center gap-3">
                    <span
                      className={`flex h-10 w-10 items-center justify-center rounded-lg ${group.color.iconBg} ${group.color.iconText}`}
                    >
                      <Icon size={20} />
                    </span>
                    <span className="text-lg font-semibold text-foreground">
                      {group.heading}
                    </span>
                  </div>
                  <p className="mb-3 flex-1 text-sm text-muted-foreground">
                    {group.description}
                  </p>
                  <span className={`text-xs font-semibold ${group.color.iconText}`}>
                    {group.prompts.length} example questions →
                  </span>
                </button>
              );
            })}
          </div>
        ) : (
          <Section
            icon={<active.icon size={18} />}
            iconBg={active.color.iconBg}
            iconText={active.color.iconText}
            accent={active.color.accent}
            title={active.heading}
            onBack={() => setActiveIdx(null)}
          >
            <ul className="grid gap-3 sm:grid-cols-2">
              {active.prompts.map((prompt) => (
                <li key={prompt}>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onPick(prompt)}
                    className="block h-full w-full rounded-xl border border-border bg-card p-4 text-left text-sm leading-snug text-foreground shadow-[0_2px_8px_rgba(0,0,0,0.06)] transition hover:border-primary/40 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50 md:text-[15px]"
                  >
                    {prompt}
                  </button>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({
  icon,
  iconBg,
  iconText,
  accent,
  title,
  onBack,
  children,
}: {
  icon: ReactNode;
  iconBg: string;
  iconText: string;
  accent: string;
  title: string;
  onBack: () => void;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className={`flex h-11 w-11 items-center justify-center rounded-xl ${iconBg} ${iconText}`}
          >
            {icon}
          </span>
          <div>
            <h3 className="text-xl font-semibold text-foreground">{title}</h3>
            <div className={`mt-1.5 h-0.5 w-12 rounded-full ${accent}`} />
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onBack}
          className="text-foreground/70 hover:bg-secondary hover:text-foreground"
        >
          ← All workflows
        </Button>
      </div>
      {children}
    </div>
  );
}
