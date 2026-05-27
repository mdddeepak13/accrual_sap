import { TcsLogo } from "@/components/tcs-logo";

export function AppFooter() {
  return (
    <footer className="shrink-0 border-t border-border bg-card">
      <div className="flex flex-col items-start gap-5 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-6">
        <div className="flex flex-col gap-1 text-xs text-muted-foreground">
          <p>
            © {new Date().getFullYear()} Accrual Engine — Python pipeline +
            Claude (Anthropic) tool-use agent.
          </p>
          <p className="font-mono">
            Backend: SAP BTP CAP (FI / MM / CO / Inventory / Plan) → FastAPI on
            Vercel · UI on Vercel
          </p>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Powered by
          </span>
          <TcsLogo size={72} />
          <span className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-primary">
            Demo
          </span>
        </div>
      </div>
    </footer>
  );
}
