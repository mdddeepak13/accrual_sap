"use client";

import { useEffect, useRef } from "react";
import type { ChatStatus } from "ai";

import { ChatMessage } from "@/components/chat-message";
import { Button } from "@/components/ui/button";
import type { AccrualAgentUIMessage } from "@/agent/accrual-agent";

interface Props {
  messages: AccrualAgentUIMessage[];
  input: string;
  onInputChange: (v: string) => void;
  onSend: (text: string) => void;
  status: ChatStatus;
}

export function ChatPanel({
  messages,
  input,
  onInputChange,
  onSend,
  status,
}: Props) {
  const isBusy = status === "submitted" || status === "streaming";
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isBusy]);

  const submit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isBusy) return;
    onSend(trimmed);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-6 md:px-8"
      >
        {messages.length === 0 ? (
          <div className="mx-auto max-w-2xl pt-8 md:pt-16">
            <h2 className="mb-2 text-xl font-semibold md:text-2xl">
              Ask anything about accruals, plan, or variance
            </h2>
            <p className="text-sm text-muted-foreground">
              The agent queries your SAP cube and plan data in real time.
              Pick an example from the sidebar or type your own question
              below. Conversation history persists until you start a new
              chat.
            </p>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.map((m) => (
              <ChatMessage key={m.id} message={m} />
            ))}
            {isBusy && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-foreground/40" />
                <span>Thinking…</span>
              </div>
            )}
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
        className="shrink-0 border-t bg-background px-4 py-3 md:px-8 md:py-4"
      >
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(input);
              }
            }}
            placeholder="Ask about accruals, budgets, variances, or irregularities…"
            rows={1}
            className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
            disabled={isBusy}
          />
          <Button type="submit" disabled={isBusy || !input.trim()}>
            {isBusy ? "Working…" : "Ask"}
          </Button>
        </div>
      </form>
    </div>
  );
}
