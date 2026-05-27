"use client";

import { useEffect, useRef } from "react";
import type { ChatStatus } from "ai";

import { ChatMessage } from "@/components/chat-message";
import { WelcomePicker } from "@/components/suggestions-list";
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
    <div className="flex h-full min-h-0 flex-col bg-background">
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-6 md:px-8"
      >
        {messages.length === 0 ? (
          <WelcomePicker onPick={submit} disabled={isBusy} />
        ) : (
          <div className="mx-auto max-w-5xl space-y-4">
            {messages.map((m) => (
              <ChatMessage key={m.id} message={m} />
            ))}
            {isBusy && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
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
        className="shrink-0 border-t border-border bg-card/80 px-4 py-3 backdrop-blur md:px-8 md:py-4"
      >
        <div className="mx-auto flex max-w-5xl items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(input);
              }
            }}
            placeholder="Ask about accruals, payroll, inventory, write-offs…"
            rows={1}
            className="flex-1 resize-none rounded-md border border-border bg-card px-3 py-2 text-base text-foreground placeholder:text-muted-foreground outline-none transition focus:border-primary/60 focus:ring-1 focus:ring-primary/40 disabled:opacity-50"
            disabled={isBusy}
          />
          <Button
            type="submit"
            disabled={isBusy || !input.trim()}
            className="bg-primary text-primary-foreground hover:bg-[#0052A3]"
          >
            {isBusy ? "Working…" : "Ask"}
          </Button>
        </div>
      </form>
    </div>
  );
}
