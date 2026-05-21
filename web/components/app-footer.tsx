export function AppFooter() {
  return (
    <footer className="shrink-0 border-t bg-background px-4 py-3 text-xs text-muted-foreground md:px-6">
      <div className="flex flex-col items-start gap-1 md:flex-row md:items-center md:justify-between">
        <p>
          © {new Date().getFullYear()} Accrual Agent — Python pipeline +
          Claude (Anthropic) tool-use agent.
        </p>
        <p className="font-mono">
          Backend: SAP sandbox (FI / MM / CO) → FastAPI on Fly · UI on Vercel
        </p>
      </div>
    </footer>
  );
}
