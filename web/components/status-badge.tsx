import { Badge } from "@/components/ui/badge";
import type { RunStatus } from "@/lib/types";

interface Props {
  status: RunStatus;
}

const STYLES: Record<RunStatus, string> = {
  running:
    "bg-sky-100 text-sky-900 border-sky-200 hover:bg-sky-100",
  completed:
    "bg-emerald-100 text-emerald-900 border-emerald-200 hover:bg-emerald-100",
  failed: "bg-red-100 text-red-900 border-red-300 hover:bg-red-100",
};

export function StatusBadge({ status }: Props) {
  return (
    <Badge variant="outline" className={`font-mono text-xs ${STYLES[status]}`}>
      {status}
    </Badge>
  );
}
