/**
 * LLM Client — Coesita FTM v2.2
 * Supports: OpenAI, Anthropic, OpenRouter, Groq, any OpenAI-compatible endpoint.
 * Uses native fetch (Node 18+), no extra SDK dependencies.
 */

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

const PROVIDER_BASE_URLS: Record<string, string> = {
  openai: "https://api.openai.com/v1",
  openrouter: "https://openrouter.ai/api/v1",
  groq: "https://api.groq.com/openai/v1",
};

export interface LLMCallOptions {
  apiKey: string;
  modelId: string;
  provider: string;
  targetUrl?: string;
  /** Agent URL mode: raw headers object to send as-is (overrides apiKey-based auth) */
  extraHeaders?: Record<string, string>;
  messages: ChatMessage[];
  maxTokens?: number;
  timeoutMs?: number;
}

/**
 * Strip chain-of-thought / reasoning blocks that some models prepend.
 * Handles: <think>...</think>, <thinking>...</thinking>, <reasoning>...</reasoning>
 * Also trims leading whitespace/newlines after stripping.
 */
function stripReasoningBlocks(text: string): string {
  return text
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/<thinking>[\s\S]*?<\/thinking>/gi, "")
    .replace(/<reasoning>[\s\S]*?<\/reasoning>/gi, "")
    .trim();
}

export async function callLLM(opts: LLMCallOptions): Promise<string> {
  const {
    apiKey,
    modelId,
    provider,
    targetUrl,
    extraHeaders,
    messages,
    maxTokens = 4096,
    timeoutMs = 90_000,
  } = opts;

  if (provider === "anthropic") {
    return callAnthropic(apiKey, modelId, messages, maxTokens, timeoutMs);
  }

  // Normalize targetUrl: strip trailing slash and /chat/completions suffix
  // so users can paste either the base URL or the full endpoint URL.
  const baseUrl = targetUrl
    ? targetUrl.replace(/\/$/, "").replace(/\/chat\/completions$/i, "")
    : (PROVIDER_BASE_URLS[provider] ?? PROVIDER_BASE_URLS.openai);

  return callOpenAICompatible(baseUrl, apiKey, modelId, messages, maxTokens, timeoutMs, provider, extraHeaders);
}

async function callOpenAICompatible(
  baseUrl: string,
  apiKey: string,
  modelId: string,
  messages: ChatMessage[],
  maxTokens: number,
  timeoutMs: number,
  provider: string,
  extraHeaders?: Record<string, string>
): Promise<string> {
  const url = `${baseUrl}/chat/completions`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (extraHeaders && Object.keys(extraHeaders).length > 0) {
    // Agent URL mode: use the caller's headers as-is (supports any auth scheme)
    Object.assign(headers, extraHeaders);
  } else {
    // API Key mode: build standard Bearer auth + provider-specific headers
    headers["Authorization"] = `Bearer ${apiKey}`;
    if (provider === "openrouter") {
      headers["HTTP-Referer"] = "https://coesita.com";
      headers["X-Title"] = "Coesita FTM Evaluation";
    }
  }

  const body = JSON.stringify({
    model: modelId,
    messages,
    max_tokens: maxTokens,
    temperature: 0.2,
  });

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers,
      body,
      signal: controller.signal,
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`API ${res.status}: ${errText.slice(0, 300)}`);
    }

    const data = await res.json() as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    const raw = data.choices?.[0]?.message?.content ?? "";
    return stripReasoningBlocks(raw);
  } finally {
    clearTimeout(timer);
  }
}

async function callAnthropic(
  apiKey: string,
  modelId: string,
  messages: ChatMessage[],
  maxTokens: number,
  timeoutMs: number
): Promise<string> {
  const systemMsg = messages.find((m) => m.role === "system");
  const chatMessages = messages
    .filter((m) => m.role !== "system")
    .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }));

  const body = JSON.stringify({
    model: modelId,
    max_tokens: maxTokens,
    system: systemMsg?.content ?? "",
    messages: chatMessages,
  });

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "x-api-key": apiKey,
    "anthropic-version": "2023-06-01",
  };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers,
      body,
      signal: controller.signal,
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`Anthropic API ${res.status}: ${errText.slice(0, 300)}`);
    }

    const data = await res.json() as {
      content?: Array<{ type: string; text?: string }>;
    };
    const raw = data.content?.find((c) => c.type === "text")?.text ?? "";
    return stripReasoningBlocks(raw);
  } finally {
    clearTimeout(timer);
  }
}
