/**
 * API client for Sanctum backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_KEY_STORAGE_KEY = 'sanctum_api_key';

export interface VisualizeRequest {
  data: Record<string, unknown>[];
  prompt: string;
  epsilon?: number;
  total_budget?: number;
  api_key?: string;
}

export interface ConfigStatusResponse {
  api_key_configured: boolean;
}

// API key management
export function getApiKey(): string | null {
  return localStorage.getItem(API_KEY_STORAGE_KEY);
}

export function setApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE_KEY, key);
}

export function clearApiKey(): void {
  localStorage.removeItem(API_KEY_STORAGE_KEY);
}

export interface VisualizeResponse {
  image: string;
  code: string;
}

export interface HealthResponse {
  status: string;
}

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new ApiError('Health check failed', response.status);
  }
  return response.json();
}

export async function checkConfigStatus(): Promise<ConfigStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/config/status`);
  if (!response.ok) {
    throw new ApiError('Config status check failed', response.status);
  }
  return response.json();
}

export async function visualize(request: VisualizeRequest): Promise<VisualizeResponse> {
  const response = await fetch(`${API_BASE_URL}/visualize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(
      `Visualization failed: ${error.detail}`,
      response.status,
      error.detail
    );
  }

  return response.json();
}

export interface StreamEvent {
  event: 'status' | 'result' | 'error';
  data: StatusEventData | ResultEventData | ErrorEventData;
}

export interface StatusEventData {
  stage: 'initializing' | 'generating' | 'validating' | 'executing' | 'retrying';
  message: string;
  attempt?: number;
}

export interface ToolCallLog {
  tool: string;
  input: Record<string, unknown>;
  result: unknown;
}

export interface MessageLog {
  role: 'user' | 'assistant';
  content: unknown;
}

export interface AgentLog {
  tool_calls: ToolCallLog[];
  messages: MessageLog[];
}

export interface ResultEventData {
  image: string;
  code: string;
  agent_log?: AgentLog;
}

export interface ReplayResultEventData extends ResultEventData {
  was_fixed: boolean;
}

export interface ErrorEventData {
  message: string;
}

export interface ReplayRequest {
  data: Record<string, unknown>[];
  code: string;
  original_prompt: string;
  total_budget?: number;
  api_key?: string;
}

export type StreamCallback = (event: StreamEvent) => void;

export async function visualizeStream(
  request: VisualizeRequest,
  onEvent: StreamCallback,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/visualize/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(
      `Visualization stream failed: ${error.detail}`,
      response.status,
      error.detail
    );
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new ApiError('No response body', 500);
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE events from buffer
    const lines = buffer.split('\n');
    buffer = lines.pop() || ''; // Keep incomplete line in buffer

    let currentEvent: string | null = null;
    let currentData: string | null = null;

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        currentData = line.slice(6).trim();
      } else if (line === '' && currentEvent && currentData) {
        // End of event, emit it
        try {
          const data = JSON.parse(currentData);
          onEvent({ event: currentEvent as StreamEvent['event'], data });
        } catch {
          console.error('Failed to parse SSE data:', currentData);
        }
        currentEvent = null;
        currentData = null;
      }
    }
  }
}

export interface ReplayStreamEvent {
  event: 'status' | 'result' | 'error';
  data: StatusEventData | ReplayResultEventData | ErrorEventData;
}

export type ReplayStreamCallback = (event: ReplayStreamEvent) => void;

export async function replayStream(
  request: ReplayRequest,
  onEvent: ReplayStreamCallback,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/visualize/replay`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(
      `Replay stream failed: ${error.detail}`,
      response.status,
      error.detail
    );
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new ApiError('No response body', 500);
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    let currentEvent: string | null = null;
    let currentData: string | null = null;

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        currentData = line.slice(6).trim();
      } else if (line === '' && currentEvent && currentData) {
        try {
          const data = JSON.parse(currentData);
          onEvent({ event: currentEvent as ReplayStreamEvent['event'], data });
        } catch {
          console.error('Failed to parse SSE data:', currentData);
        }
        currentEvent = null;
        currentData = null;
      }
    }
  }
}
