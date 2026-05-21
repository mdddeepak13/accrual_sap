import { Badge } from "@/components/ui/badge";
import type { Severity } from "@/lib/types";

interface Props {
  severity: Severity | null;
}

const VARIANTS: Record<Severity, { label: string; className: string }> = {
  low: {
    label: "low",
    className: "bg-amber-100 text-amber-900 border-amber-200 hover:bg-amber-100",
  },
  medium: {
    label: "medium",
    className:
      "bg-orange-100 text-orange-900 border-orange-200 hover:bg-orange-100",
  },
  high: {
    label: "high",
    className: "bg-red-100 text-red-900 border-red-300 hover:bg-red-100",
  },
};

export function SeverityBadge({ severity }: Props) {
  if (severity === null) {
    return (
      <Badge variant="outline" className="font-mono text-xs">
        —
      </Badge>
    );
  }
  const variant = VARIANTS[severity];
  return (
    <Badge
      variant="outline"
      className={`font-mono text-xs ${variant.className}`}
    >
      {variant.label}
    </Badge>
  );
}
