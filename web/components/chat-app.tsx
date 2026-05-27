"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { useState } from "react";

import { AppFooter } from "@/components/app-footer";
import { AppHeader } from "@/components/app-header";
import { AppLogo } from "@/components/app-logo";
import { ChatPanel } from "@/components/chat-panel";
import { SuggestionsList } from "@/components/suggestions-list";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { AccrualAgentUIMessage } from "@/agent/accrual-agent";

export function ChatApp() {
  const [input, setInput] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);

  const { messages, sendMessage, setMessages, status } =
    useChat<AccrualAgentUIMessage>({
      transport: new DefaultChatTransport({ api: "/api/chat" }),
    });

  const isBusy = status === "submitted" || status === "streaming";

  const handleSend = (text: string) => {
    if (!text.trim() || isBusy) return;
    sendMessage({ text });
    setInput("");
  };

  const handlePick = (prompt: string) => {
    handleSend(prompt);
    // Close the mobile drawer after a pick so the user sees the reply.
    setDrawerOpen(false);
  };

  const handleNewChat = () => {
    setMessages([]);
    setInput("");
    setDrawerOpen(false);
  };

  return (
    <div className="flex h-dvh flex-col bg-background text-foreground">
      <AppHeader onOpenMenu={() => setDrawerOpen(true)} />

      <div className="flex min-h-0 flex-1">
        {/* Desktop sidebar — white rail, subtle right border */}
        <aside className="hidden w-72 shrink-0 border-r border-border bg-sidebar md:flex md:flex-col">
          <SuggestionsList
            onPick={handlePick}
            onNewChat={handleNewChat}
            disabled={isBusy}
          />
        </aside>

        {/* Main chat region */}
        <main className="min-w-0 flex-1 bg-background">
          <ChatPanel
            messages={messages}
            input={input}
            onInputChange={setInput}
            onSend={handleSend}
            status={status}
          />
        </main>
      </div>

      <AppFooter />

      {/* Mobile drawer with the same suggestions */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="left" className="w-72 p-0">
          <SheetHeader className="border-b px-3 py-3">
            <SheetTitle>
              <AppLogo size="sm" />
            </SheetTitle>
          </SheetHeader>
          <SuggestionsList
            onPick={handlePick}
            onNewChat={handleNewChat}
            disabled={isBusy}
          />
        </SheetContent>
      </Sheet>
    </div>
  );
}
