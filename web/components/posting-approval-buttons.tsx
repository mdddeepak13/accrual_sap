"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";

interface Props {
  postingId: string;
}

export function PostingApprovalButtons({ postingId }: Props) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const act = (action: "approve" | "reject") => {
    setError(null);
    startTransition(async () => {
      try {
        const res = await fetch(`/api/postings/${postingId}/${action}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        if (!res.ok) {
          const body = await res.text().catch(() => "");
          throw new Error(`HTTP ${res.status}: ${body || "request failed"}`);
        }
        router.refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Request failed");
      }
    });
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Button
          type="button"
          onClick={() => act("approve")}
          disabled={pending}
          className="bg-emerald-600 text-white hover:bg-emerald-700"
        >
          <CheckCircle2 size={16} />
          Approve & post
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => act("reject")}
          disabled={pending}
          className="border-red-300 text-red-700 hover:bg-red-50"
        >
          <XCircle size={16} />
          Reject
        </Button>
      </div>
      {error && (
        <p className="text-xs text-red-700">Failed: {error}</p>
      )}
    </div>
  );
}
