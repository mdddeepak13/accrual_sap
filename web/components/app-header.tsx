"use client";

import Link from "next/link";
import { Menu } from "lucide-react";

import { AppLogo } from "@/components/app-logo";
import { Button } from "@/components/ui/button";

interface Props {
  onOpenMenu?: () => void;
}

const NAV = [
  { href: "/", label: "Chat" },
  { href: "/runs", label: "Runs" },
  { href: "/presentation", label: "Presentation" },
];

export function AppHeader({ onOpenMenu }: Props) {
  return (
    <>
      {/* Solid brand strip — Woorank blue */}
      <div aria-hidden className="h-1 shrink-0 bg-primary" />
      <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-card/90 px-4 backdrop-blur supports-[backdrop-filter]:bg-card/80 md:px-6">
        <div className="flex items-center gap-2">
          {onOpenMenu && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-foreground/80 hover:text-foreground md:hidden"
              aria-label="Open menu"
              onClick={onOpenMenu}
            >
              <Menu size={18} />
            </Button>
          )}
          <Link href="/" className="text-foreground">
            <AppLogo />
          </Link>
        </div>
        <nav className="flex items-center gap-1 text-sm font-medium">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="rounded-md px-3 py-1.5 text-foreground/70 transition hover:bg-secondary hover:text-primary"
            >
              {n.label}
            </Link>
          ))}
        </nav>
      </header>
    </>
  );
}
