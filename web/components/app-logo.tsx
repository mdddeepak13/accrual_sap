import { Receipt } from "lucide-react";

interface Props {
  size?: "sm" | "md";
}

export function AppLogo({ size = "md" }: Props) {
  const iconSize = size === "sm" ? 16 : 20;
  const textSize = size === "sm" ? "text-sm" : "text-base";
  return (
    <div className="flex items-center gap-2">
      <span
        aria-hidden
        className="inline-flex size-7 items-center justify-center rounded-md bg-foreground text-background"
      >
        <Receipt size={iconSize} strokeWidth={2} />
      </span>
      <span className={`font-semibold tracking-tight ${textSize}`}>
        Accrual Engine
      </span>
    </div>
  );
}
