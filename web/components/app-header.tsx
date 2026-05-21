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
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/70 md:px-6">
      <div className="flex items-center gap-2">
        {onOpenMenu && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="md:hidden"
            aria-label="Open menu"
            onClick={onOpenMenu}
          >
            <Menu size={18} />
          </Button>
        )}
        <Link href="/">
          <AppLogo />
        </Link>
      </div>
      <nav className="flex items-center gap-1 text-sm">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className="rounded-md px-3 py-1.5 text-foreground/70 hover:bg-muted hover:text-foreground"
          >
            {n.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
