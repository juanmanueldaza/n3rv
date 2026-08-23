/**
 * N3RV RPC helpers — shared across OpenCode tools and plugins.
 *
 * Exports:
 *   memoryRpc(method, params, timeoutMs)  — call n3rv-memory MCP
 *   hubRpc(method, params, timeoutMs)     — call n3rv-hub MCP
 *   withTimeout(ms)                        — AbortController-based timeout
 *   healthCheck()                          — check n3rv-hub /health endpoint
 *
 * All functions return structured JSON with `error` key on failure.
 */

const MEMORY_MCP_URL = "http://127.0.0.1:19821";
const HUB_MCP_URL = "http://127.0.0.1:19820";
const DEFAULT_TIMEOUT_MS = 2000;

/**
 * Returns an AbortSignal that aborts after `ms` milliseconds.
 * Uses AbortController + setTimeout for maximum portability.
 */
export function withTimeout(ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  // Clear the timer if the signal is already aborted (safety)
  controller.signal.addEventListener(
    "abort",
    () => clearTimeout(timer),
    { once: true },
  );
  return controller.signal;
}

/**
 * Internal: generic JSON-RPC 2.0 POST to an MCP server.
 */
async function rpcCall(baseUrl, method, params, timeoutMs) {
  const signal = withTimeout(timeoutMs);

  try {
    const res = await fetch(`${baseUrl}/rpc`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: Date.now(),
        method,
        params,
      }),
      signal,
    });

    if (!res.ok) {
      return { error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data = await res.json();
    if (data.error) {
      return { error: data.error.message ?? String(data.error) };
    }
    return data.result;
  } catch (err) {
    if (err.name === "AbortError") return { error: "timeout" };
    return { error: err.message ?? "unavailable" };
  }
}

/**
 * Call an RPC method on the n3rv-memory MCP server.
 */
export async function memoryRpc(method, params = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  return rpcCall(MEMORY_MCP_URL, method, params, timeoutMs);
}

/**
 * Call an RPC method on the n3rv-hub MCP server.
 */
export async function hubRpc(method, params = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  return rpcCall(HUB_MCP_URL, method, params, timeoutMs);
}

/**
 * Check whether the n3rv-hub /health endpoint is reachable.
 * Returns { connected: true/false, ...data }.
 */
export async function healthCheck() {
  const signal = withTimeout(DEFAULT_TIMEOUT_MS);

  try {
    const res = await fetch(`${HUB_MCP_URL}/health`, { signal });
    if (!res.ok) {
      return { connected: false, status: res.status };
    }
    const data = await res.json();
    return { connected: true, ...data };
  } catch {
    return { connected: false };
  }
}