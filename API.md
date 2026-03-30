# LinkedIn Article Generator — API Reference

Base URL: `http://<host>:8000`
Protocol: HTTP/1.1 with Server-Sent Events (SSE) for streaming
Auth: None (add a reverse-proxy layer for production)
CORS: All origins permitted

---

## Endpoints

### `GET /health`

Health check. Use this to confirm the server is up before initiating generation.

**Response `200 OK`**

```json
{
  "status": "ok",
  "timestamp": "2026-03-29T14:00:00.000000"
}
```

---

### `POST /articles/generate`

Generate a LinkedIn article. The response is a **Server-Sent Events stream** that delivers real-time progress events followed by the completed article.

**Request headers**

```
Content-Type: application/json
Accept: text/event-stream
```

**Request body**

| Field | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `draft` | string | yes | — | min 50 chars | Article draft, outline, or topic description |
| `target_score` | number | no | `89.0` | 0–100 | Quality score % to reach before returning. 89%+ = world-class |
| `max_iterations` | integer | no | `10` | 1–50 | Maximum improvement iterations before giving up |
| `word_count_min` | integer | no | `2000` | ≥100 | Minimum article word count |
| `word_count_max` | integer | no | `2500` | ≥100 | Maximum article word count |
| `model` | string | no | `"moonshotai/kimi-k2-thinking"` | — | Default model used for all components unless overridden |
| `generator_model` | string\|null | no | `null` | — | Override model for article generation |
| `judge_model` | string\|null | no | `null` | — | Override model for quality scoring |
| `rag_model` | string\|null | no | `null` | — | Override model for web search/retrieval |
| `humanizer_model` | string\|null | no | `null` | — | Override model for humanization — defaults to `generator_model` if not set |
| `recreate_ctx` | boolean | no | `false` | — | Re-run web search on each iteration (slower, potentially more accurate) |

Model strings are OpenRouter model IDs, e.g. `"anthropic/claude-3-5-sonnet"`, `"openai/gpt-4o"`, `"google/gemini-2.0-flash-001"`.

**Minimal request example**

```json
{
  "draft": "Most executives think AI will automate their workforce. They're asking the wrong question entirely. The real transformation is happening at the strategy layer, not the operations layer."
}
```

**Full request example**

```json
{
  "draft": "Most executives think AI will automate their workforce...",
  "target_score": 85.0,
  "max_iterations": 5,
  "word_count_min": 1500,
  "word_count_max": 2000,
  "generator_model": "anthropic/claude-3-5-sonnet",
  "judge_model": "openai/gpt-4o",
  "rag_model": "google/gemini-2.0-flash-001"
}
```

---

## SSE Event Stream Protocol

The response body is a stream of `text/event-stream` lines. Each event follows the standard SSE format:

```
data: <JSON>\n\n
```

All events are JSON objects. The `type` field determines the shape of the rest of the object.

### Event type: `progress`

Emitted continuously throughout generation to report the current stage.

```json
{
  "type": "progress",
  "stage": "string",
  "message": "string"
}
```

**All possible `stage` values, in order of occurrence:**

| Stage | When emitted |
|---|---|
| `init` | Pipeline initialisation |
| `start` | Generation loop begins |
| `rag_search` | Web search starting |
| `rag_queries` | Search queries chosen |
| `rag_complete` | Web search done, context ready |
| `context` | Context reuse/refresh decision |
| `generating` | LLM generating article (may repeat each iteration) |
| `scoring` | Judge evaluating current version |
| `scored` | Score received; message includes percentage and tier |
| `fact_checking` | Fact-check starting (only when score target is met) |
| `fact_check_results` | Fact-check summary |
| `fact_check_passed` | Article cleared by fact-checker |
| `fact_check_failed` | Fact-check found issues (article still returned) |
| `citation_issues` | Specific citation problems found |
| `humanizing` | Humanization rewrite starting — this is the last progress event before `complete` |
| `humanized` | Humanization complete |
| `complete_version` | Internal version complete |
| `info` | General informational message |

### Event type: `heartbeat`

Keep-alive ping emitted every ~0.5 s when the worker is busy but has no new progress to report. **Ignore the payload entirely.**

```json
{"type": "heartbeat"}
```

### Event type: `complete`

The terminal success event. The stream ends immediately after this event.

```json
{
  "type": "complete",
  "article": {
    "original": "# Article Title\n\nPre-humanization markdown...",
    "humanized": "# Article Title\n\nPost-humanization markdown..."
  },
  "score": {
    "percentage": 91.3,
    "performance_tier": "World-class",
    "word_count": 2187,
    "meets_requirements": true,
    "overall_feedback": "Strong strategic framing..."
  },
  "target_achieved": true,
  "iterations_used": 3
}
```

**`article` object fields:**

| Field | Type | Description |
|---|---|---|
| `original` | string | The article after quality scoring and fact-checking, before humanization |
| `humanized` | string | The article after the two-pass humanizer rewrite. Use this for publishing. If humanization fails, equals `original`. |

**`score` object fields:**

| Field | Type | Description |
|---|---|---|
| `percentage` | number | Quality score 0–100, evaluated against the pre-humanization article |
| `performance_tier` | string | `"World-class"` / `"Strong"` / `"Needs restructuring"` / `"Rework"` |
| `word_count` | integer | Word count of the pre-humanization article |
| `meets_requirements` | boolean | Both score and word count targets were met |
| `overall_feedback` | string\|null | Human-readable summary from the judge |

**`target_achieved`**: `true` means both `percentage >= target_score` AND word count is within range. If max_iterations was reached before hitting the target, this will be `false` but the best article found is still returned.

### Event type: `error`

The terminal failure event. The stream ends immediately after this event.

```json
{
  "type": "error",
  "message": "Could not resolve model 'bad-model-name': ..."
}
```

---

## TypeScript Types

Copy these into your project for fully typed SSE handling.

```typescript
// ── Request ──────────────────────────────────────────────────────────────────

export interface GenerateRequest {
  draft: string;
  target_score?: number;        // default 89.0
  max_iterations?: number;      // default 10
  word_count_min?: number;      // default 2000
  word_count_max?: number;      // default 2500
  model?: string;               // default "moonshotai/kimi-k2-thinking"
  generator_model?: string | null;
  judge_model?: string | null;
  rag_model?: string | null;
  humanizer_model?: string | null; // defaults to generator_model
  recreate_ctx?: boolean;       // default false
}

// ── SSE Events ───────────────────────────────────────────────────────────────

export type ProgressStage =
  | "init"
  | "start"
  | "rag_search"
  | "rag_queries"
  | "rag_complete"
  | "context"
  | "generating"
  | "scoring"
  | "scored"
  | "fact_checking"
  | "fact_check_results"
  | "fact_check_passed"
  | "fact_check_failed"
  | "citation_issues"
  | "humanizing"
  | "humanized"
  | "complete_version"
  | "info";

export interface ProgressEvent {
  type: "progress";
  stage: ProgressStage;
  message: string;
}

export interface HeartbeatEvent {
  type: "heartbeat";
}

export interface ArticleScore {
  percentage: number;
  performance_tier: "World-class" | "Strong" | "Needs restructuring" | "Rework";
  word_count: number;
  meets_requirements: boolean;
  overall_feedback: string | null;
}

export interface ArticleResult {
  /** Pre-humanization article — use for quality review or diff comparison */
  original: string;
  /** Post-humanization article — use this for publishing */
  humanized: string;
}

export interface CompleteEvent {
  type: "complete";
  article: ArticleResult;
  score: ArticleScore;
  target_achieved: boolean;
  iterations_used: number;
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type ArticleGeneratorEvent =
  | ProgressEvent
  | HeartbeatEvent
  | CompleteEvent
  | ErrorEvent;

// ── Health ───────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: "ok";
  timestamp: string; // ISO 8601
}
```

---

## JavaScript / TypeScript Client

A complete, copy-paste ready client using the browser's native `fetch` API. No external dependencies required.

```typescript
import type {
  GenerateRequest,
  ArticleGeneratorEvent,
  ArticleResult,
  ProgressEvent,
  CompleteEvent,
  ErrorEvent,
} from "./article-generator-types"; // paste the types above into this file

export interface GenerationCallbacks {
  /** Called for every progress stage update */
  onProgress?: (stage: string, message: string) => void;
  /** Called when generation completes successfully */
  onComplete: (event: CompleteEvent) => void;
  /** Called when generation fails */
  onError: (message: string) => void;
}

/**
 * Generate a LinkedIn article by streaming events from the API.
 *
 * Returns an AbortController — call controller.abort() to cancel the request.
 *
 * @example
 * const ctrl = generateArticle(
 *   "http://localhost:8000",
 *   { draft: "AI is changing everything..." },
 *   {
 *     onProgress: (stage, message) => console.log(`[${stage}] ${message}`),
 *     onComplete: (event) => setArticle(event.article.humanized),
 *     onError: (msg) => setError(msg),
 *   }
 * );
 * // To cancel: ctrl.abort();
 */
export function generateArticle(
  baseUrl: string,
  request: GenerateRequest,
  callbacks: GenerationCallbacks
): AbortController {
  const controller = new AbortController();

  (async () => {
    let response: Response;

    try {
      response = await fetch(`${baseUrl}/articles/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      });
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") return;
      callbacks.onError(`Network error: ${(err as Error).message}`);
      return;
    }

    if (!response.ok) {
      const body = await response.text().catch(() => "");
      callbacks.onError(`HTTP ${response.status}: ${body}`);
      return;
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE lines are separated by double newlines
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? ""; // keep the incomplete trailing chunk

        for (const part of parts) {
          const dataLine = part
            .split("\n")
            .find((line) => line.startsWith("data: "));
          if (!dataLine) continue;

          let event: ArticleGeneratorEvent;
          try {
            event = JSON.parse(dataLine.slice(6)) as ArticleGeneratorEvent;
          } catch {
            continue; // malformed line — skip
          }

          if (event.type === "heartbeat") {
            // Keep-alive — nothing to do
          } else if (event.type === "progress") {
            callbacks.onProgress?.(event.stage, event.message);
          } else if (event.type === "complete") {
            callbacks.onComplete(event);
            return;
          } else if (event.type === "error") {
            callbacks.onError(event.message);
            return;
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") return;
      callbacks.onError(`Stream error: ${(err as Error).message}`);
    } finally {
      reader.releaseLock();
    }
  })();

  return controller;
}

/** Check that the API server is reachable. */
export async function checkHealth(baseUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl}/health`);
    const data = await res.json();
    return data.status === "ok";
  } catch {
    return false;
  }
}
```

### React hook example

```tsx
import { useState, useRef, useCallback } from "react";
import { generateArticle } from "./article-generator-client";
import type { GenerateRequest, CompleteEvent } from "./article-generator-types";

interface UseArticleGeneratorReturn {
  generate: (request: GenerateRequest) => void;
  cancel: () => void;
  isGenerating: boolean;
  progressMessages: string[];
  result: CompleteEvent | null;
  error: string | null;
}

export function useArticleGenerator(baseUrl: string): UseArticleGeneratorReturn {
  const [isGenerating, setIsGenerating] = useState(false);
  const [progressMessages, setProgressMessages] = useState<string[]>([]);
  const [result, setResult] = useState<CompleteEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const generate = useCallback(
    (request: GenerateRequest) => {
      setIsGenerating(true);
      setProgressMessages([]);
      setResult(null);
      setError(null);

      controllerRef.current = generateArticle(baseUrl, request, {
        onProgress: (stage, message) => {
          setProgressMessages((prev) => [...prev, `[${stage}] ${message}`]);
        },
        onComplete: (event) => {
          setResult(event);
          setIsGenerating(false);
        },
        onError: (msg) => {
          setError(msg);
          setIsGenerating(false);
        },
      });
    },
    [baseUrl]
  );

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    setIsGenerating(false);
  }, []);

  return { generate, cancel, isGenerating, progressMessages, result, error };
}
```

### Usage in a React component

```tsx
function ArticleGenerator() {
  const { generate, cancel, isGenerating, progressMessages, result, error } =
    useArticleGenerator("http://localhost:8000");

  const handleSubmit = (draft: string) => {
    generate({
      draft,
      target_score: 89.0,
      max_iterations: 10,
      word_count_min: 2000,
      word_count_max: 2500,
    });
  };

  return (
    <div>
      {/* ... your form ... */}

      {isGenerating && (
        <div>
          <button onClick={cancel}>Cancel</button>
          <ul>
            {progressMessages.map((msg, i) => (
              <li key={i}>{msg}</li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {result && (
        <div>
          <p>Score: {result.score.percentage.toFixed(1)}% — {result.score.performance_tier}</p>
          <p>Words: {result.score.word_count} | Iterations: {result.iterations_used}</p>
          <article>{result.article.humanized}</article>
        </div>
      )}
    </div>
  );
}
```

---

## Error Reference

| Scenario | Behaviour |
|---|---|
| `draft` shorter than 50 characters | HTTP `422 Unprocessable Entity` before stream opens |
| `target_score` outside 0–100 | HTTP `422 Unprocessable Entity` |
| `max_iterations` outside 1–50 | HTTP `422 Unprocessable Entity` |
| Invalid/unavailable model name | `error` event on the SSE stream |
| `OPENROUTER_API_KEY` missing or invalid | `error` event on the SSE stream |
| `TAVILY_API_KEY` missing (web search fails) | Generation continues without RAG context |
| `target_score` not reached within `max_iterations` | `complete` event with `target_achieved: false`; best article is returned |
| Server not running | `fetch` throws `TypeError: Failed to fetch` |

---

## Performance Notes

- Generation typically takes **5–20 minutes** depending on `max_iterations` and model speed.
- Keep the HTTP connection open for the full duration. Do not set short fetch timeouts.
- The `heartbeat` event is emitted every ~0.5 s to prevent proxy/browser connection timeouts.
- For production deployments behind nginx, set `proxy_read_timeout 1800;` (30 min).
- The server uses `--workers 1`. Multiple concurrent requests are supported (up to 4 in-flight at once via the internal thread pool) but they share the same process.
