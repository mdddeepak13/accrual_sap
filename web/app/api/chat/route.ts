import { createAgentUIStreamResponse } from "ai";

import { accrualAgent } from "@/agent/accrual-agent";
import {
  cacheKey,
  captureResponseForCache,
  getCached,
  setCached,
  type UIMessage,
} from "@/lib/response-cache";

// Tool calls can take ~20s (pipeline run); keep the function alive long
// enough that the Vercel timeout doesn't cut the stream short.
export const maxDuration = 60;

const CACHED_STREAM_HEADERS: Record<string, string> = {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache",
  "x-chat-cache": "hit",
};

export async function POST(request: Request) {
  try {
    const { messages } = (await request.json()) as { messages: UIMessage[] };

    // Layer 1 — exact-match response cache (bypasses Anthropic entirely for
    // repeat first-turn questions).
    const key = cacheKey(messages);
    if (key) {
      const hit = getCached(key);
      if (hit) {
        // Wrap the bytes in a ReadableStream so the Response body type is
        // accepted by strict TS (Uint8Array isn't a valid BodyInit here).
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(hit);
            controller.close();
          },
        });
        return new Response(stream, { headers: CACHED_STREAM_HEADERS });
      }
    }

    // Layer 2 — live call. The agent's last tool carries an Anthropic
    // cacheControl breakpoint, so the system + tool-def prefix is cached
    // on Anthropic's side (~90% input-token discount within 5 minutes).
    const live = await createAgentUIStreamResponse({
      agent: accrualAgent,
      uiMessages: messages,
    });

    if (!key) return live;

    return captureResponseForCache(live, (bytes) => {
      setCached(key, bytes);
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    console.error("chat.route.error", {
      message: detail,
      stack: error instanceof Error ? error.stack : undefined,
    });
    return Response.json(
      { error: "Chat request failed", detail },
      { status: 500 },
    );
  }
}
