/**
 * In-memory cache of chat API responses.
 *
 * Keyed by the normalized text of a single-turn user message. Multi-turn
 * conversations are never cached (context-dependent). Entries expire after
 * 30 minutes so stale SAP data eventually refreshes.
 *
 * Scope: lives for the lifetime of a Vercel Function instance. Fluid
 * Compute reuses instances aggressively, so hit rate is high in practice
 * despite not being a shared cache. For a cross-instance cache, swap this
 * for Vercel Runtime Cache or Upstash Redis later.
 */

interface Entry {
  bytes: Uint8Array;
  expiresAt: number;
}

const TTL_MS = 30 * 60 * 1000;
const MAX_ENTRIES = 100; // bounded LRU to cap memory
const store = new Map<string, Entry>();

export interface UIPart {
  type: string;
  text?: string;
}
export interface UIMessage {
  id?: string;
  role: "user" | "assistant" | "system";
  parts?: UIPart[];
}

export function cacheKey(messages: UIMessage[]): string | null {
  // Only cache first-turn user messages — follow-ups depend on history.
  if (messages.length !== 1) return null;
  const [msg] = messages;
  if (msg.role !== "user") return null;
  const text =
    (msg.parts ?? [])
      .filter((p) => p.type === "text")
      .map((p) => p.text ?? "")
      .join(" ")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
  return text.length > 0 ? text : null;
}

export function getCached(key: string): Uint8Array | null {
  const entry = store.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    store.delete(key);
    return null;
  }
  // LRU touch: re-insert so this entry is the newest.
  store.delete(key);
  store.set(key, entry);
  return entry.bytes;
}

export function setCached(key: string, bytes: Uint8Array): void {
  if (store.size >= MAX_ENTRIES) {
    const oldest = store.keys().next().value;
    if (oldest !== undefined) store.delete(oldest);
  }
  store.set(key, { bytes, expiresAt: Date.now() + TTL_MS });
}

/**
 * Captures a streaming response body into a Uint8Array for caching while
 * the original bytes continue flowing to the client. Uses ReadableStream.tee()
 * so the client sees zero added latency.
 */
export function captureResponseForCache(
  response: Response,
  onComplete: (bytes: Uint8Array) => void,
): Response {
  if (!response.body) return response;

  const [forClient, forCache] = response.body.tee();

  // Drain the cache branch in the background.
  (async () => {
    try {
      const reader = forCache.getReader();
      const chunks: Uint8Array[] = [];
      let total = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value) {
          chunks.push(value);
          total += value.length;
        }
      }
      const combined = new Uint8Array(total);
      let offset = 0;
      for (const chunk of chunks) {
        combined.set(chunk, offset);
        offset += chunk.length;
      }
      onComplete(combined);
    } catch (err) {
      // If the background capture fails, just don't cache; don't disturb
      // the client stream.
      console.warn("response-cache.capture_failed", err);
    }
  })();

  return new Response(forClient, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
}
