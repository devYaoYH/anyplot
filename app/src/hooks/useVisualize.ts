/**
 * Hook for visualization API communication with streaming support.
 */

import { useCallback, useRef, useState } from 'react';
import {
  visualizeStream,
  replayStream,
  continueStream,
  convertStream,
  ApiError,
  getApiKey,
} from '../lib/api';
import type {
  VisualizeRequest,
  StreamEvent,
  ReplayStreamEvent,
  StatusEventData,
  ResultEventData,
  ReplayResultEventData,
  ErrorEventData,
  AgentLog,
  ToolCallLog,
  VizMode,
  VizType,
  VisualizationResult,
} from '../lib/api';

export interface ProgressStatus {
  stage: StatusEventData['stage'];
  message: string;
  attempt?: number;
}

export interface VisualizeResult {
  image?: string;
  vegaSpec?: object;
  vizType: VizType;
  code: string;
  agentLog?: AgentLog;
  wasFixed?: boolean;
}

export interface SessionState {
  messages: unknown[];
  toolCalls: ToolCallLog[];
  originalPrompt: string;
}

export interface UseVisualizeReturn {
  isLoading: boolean;
  error: string | null;
  result: VisualizeResult | null;
  matplotlibResult: VisualizeResult | null;
  altairResult: VisualizeResult | null;
  progress: ProgressStatus | null;
  session: SessionState | null;
  hasActiveSession: boolean;
  generateVisualization: (data: Record<string, unknown>[], prompt: string, vizMode?: VizMode) => Promise<void>;
  continueVisualization: (data: Record<string, unknown>[], prompt: string) => Promise<void>;
  replayVisualization: (data: Record<string, unknown>[], code: string, originalPrompt: string) => Promise<void>;
  convertVisualization: (data: Record<string, unknown>[], code: string, originalPrompt: string, targetMode: VizMode) => Promise<void>;
  cancelVisualization: () => void;
  clearResult: () => void;
  clearSession: () => void;
  restoreResults: (matplotlib: VisualizationResult | null, altair: VisualizationResult | null) => void;
}

export function useVisualize(): UseVisualizeReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VisualizeResult | null>(null);
  const [matplotlibResult, setMatplotlibResult] = useState<VisualizeResult | null>(null);
  const [altairResult, setAltairResult] = useState<VisualizeResult | null>(null);
  const [progress, setProgress] = useState<ProgressStatus | null>(null);
  const [session, setSession] = useState<SessionState | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const generateVisualization = useCallback(
    async (data: Record<string, unknown>[], prompt: string, vizMode: VizMode = 'matplotlib') => {
      if (data.length === 0) {
        setError('No data to visualize');
        return;
      }

      if (!prompt.trim()) {
        setError('Please enter a visualization prompt');
        return;
      }

      // Cancel any existing request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();

      setIsLoading(true);
      setError(null);
      setResult(null);
      setProgress(null);
      // Clear session when starting a new visualization
      setSession(null);

      const promptTrimmed = prompt.trim();

      try {
        const apiKey = getApiKey();
        const request: VisualizeRequest = {
          data,
          prompt: promptTrimmed,
          viz_mode: vizMode,
          ...(apiKey && { api_key: apiKey }),
        };

        await visualizeStream(
          request,
          (event: StreamEvent) => {
            switch (event.event) {
              case 'status': {
                const statusData = event.data as StatusEventData;
                setProgress({
                  stage: statusData.stage,
                  message: statusData.message,
                  attempt: statusData.attempt,
                });
                break;
              }
              case 'result': {
                const resultData = event.data as ResultEventData;
                const newResult: VisualizeResult = {
                  image: resultData.image,
                  vegaSpec: resultData.vega_spec,
                  vizType: resultData.viz_type,
                  code: resultData.code,
                  agentLog: resultData.agent_log,
                };
                setResult(newResult);
                // Store in the appropriate result bucket
                if (resultData.viz_type === 'vega_lite') {
                  setAltairResult(newResult);
                } else {
                  setMatplotlibResult(newResult);
                }
                // Save session state for continuation
                if (resultData.agent_log) {
                  setSession({
                    messages: resultData.agent_log.messages,
                    toolCalls: resultData.agent_log.tool_calls,
                    originalPrompt: promptTrimmed,
                  });
                }
                setProgress(null);
                break;
              }
              case 'error': {
                const errorData = event.data as ErrorEventData;
                setError(errorData.message);
                setProgress(null);
                break;
              }
            }
          },
          abortControllerRef.current.signal
        );
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          // Request was cancelled, don't set error
          return;
        }
        if (err instanceof ApiError) {
          setError(err.detail || err.message);
        } else {
          setError(`Unexpected error: ${err}`);
        }
      } finally {
        setIsLoading(false);
        setProgress(null);
        abortControllerRef.current = null;
      }
    },
    []
  );

  const replayVisualization = useCallback(
    async (data: Record<string, unknown>[], code: string, originalPrompt: string) => {
      if (data.length === 0) {
        setError('No data to visualize');
        return;
      }

      if (!code.trim()) {
        setError('No code to replay');
        return;
      }

      // Cancel any existing request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();

      setIsLoading(true);
      setError(null);
      setResult(null);
      setProgress(null);

      try {
        const apiKey = getApiKey();
        const request = {
          data,
          code: code.trim(),
          original_prompt: originalPrompt,
          ...(apiKey && { api_key: apiKey }),
        };

        await replayStream(
          request,
          (event: ReplayStreamEvent) => {
            switch (event.event) {
              case 'status': {
                const statusData = event.data as StatusEventData;
                setProgress({
                  stage: statusData.stage,
                  message: statusData.message,
                  attempt: statusData.attempt,
                });
                break;
              }
              case 'result': {
                const resultData = event.data as ReplayResultEventData;
                const newResult: VisualizeResult = {
                  image: resultData.image,
                  vegaSpec: resultData.vega_spec,
                  vizType: resultData.viz_type || 'image',
                  code: resultData.code,
                  agentLog: resultData.agent_log,
                  wasFixed: resultData.was_fixed,
                };
                setResult(newResult);
                setProgress(null);
                break;
              }
              case 'error': {
                const errorData = event.data as ErrorEventData;
                setError(errorData.message);
                setProgress(null);
                break;
              }
            }
          },
          abortControllerRef.current.signal
        );
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        if (err instanceof ApiError) {
          setError(err.detail || err.message);
        } else {
          setError(`Unexpected error: ${err}`);
        }
      } finally {
        setIsLoading(false);
        setProgress(null);
        abortControllerRef.current = null;
      }
    },
    []
  );

  const convertVisualization = useCallback(
    async (data: Record<string, unknown>[], code: string, originalPrompt: string, targetMode: VizMode) => {
      if (data.length === 0) {
        setError('No data to visualize');
        return;
      }

      if (!code.trim()) {
        setError('No code to convert');
        return;
      }

      // Cancel any existing request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();

      setIsLoading(true);
      setError(null);
      setProgress(null);

      try {
        const apiKey = getApiKey();
        const request = {
          data,
          current_code: code.trim(),
          target_mode: targetMode,
          original_prompt: originalPrompt,
          ...(apiKey && { api_key: apiKey }),
        };

        await convertStream(
          request,
          (event: StreamEvent) => {
            switch (event.event) {
              case 'status': {
                const statusData = event.data as StatusEventData;
                setProgress({
                  stage: statusData.stage,
                  message: statusData.message,
                  attempt: statusData.attempt,
                });
                break;
              }
              case 'result': {
                const resultData = event.data as ResultEventData;
                const newResult: VisualizeResult = {
                  image: resultData.image,
                  vegaSpec: resultData.vega_spec,
                  vizType: resultData.viz_type,
                  code: resultData.code,
                  agentLog: resultData.agent_log,
                };
                setResult(newResult);
                // Store in the appropriate result bucket
                if (resultData.viz_type === 'vega_lite') {
                  setAltairResult(newResult);
                } else {
                  setMatplotlibResult(newResult);
                }
                setProgress(null);
                break;
              }
              case 'error': {
                const errorData = event.data as ErrorEventData;
                setError(errorData.message);
                setProgress(null);
                break;
              }
            }
          },
          abortControllerRef.current.signal
        );
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        if (err instanceof ApiError) {
          setError(err.detail || err.message);
        } else {
          setError(`Unexpected error: ${err}`);
        }
      } finally {
        setIsLoading(false);
        setProgress(null);
        abortControllerRef.current = null;
      }
    },
    []
  );

  const continueVisualization = useCallback(
    async (data: Record<string, unknown>[], prompt: string) => {
      if (data.length === 0) {
        setError('No data to visualize');
        return;
      }

      if (!prompt.trim()) {
        setError('Please enter an adjustment request');
        return;
      }

      if (!session) {
        setError('No active session to continue');
        return;
      }

      // Cancel any existing request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();

      setIsLoading(true);
      setError(null);
      setProgress(null);

      try {
        const apiKey = getApiKey();
        const request = {
          data,
          prompt: prompt.trim(),
          previous_messages: session.messages,
          previous_tool_calls: session.toolCalls,
          ...(apiKey && { api_key: apiKey }),
        };

        await continueStream(
          request,
          (event: StreamEvent) => {
            switch (event.event) {
              case 'status': {
                const statusData = event.data as StatusEventData;
                setProgress({
                  stage: statusData.stage,
                  message: statusData.message,
                  attempt: statusData.attempt,
                });
                break;
              }
              case 'result': {
                const resultData = event.data as ResultEventData;
                const newResult: VisualizeResult = {
                  image: resultData.image,
                  vegaSpec: resultData.vega_spec,
                  vizType: resultData.viz_type,
                  code: resultData.code,
                  agentLog: resultData.agent_log,
                };
                setResult(newResult);
                // Store in the appropriate result bucket
                if (resultData.viz_type === 'vega_lite') {
                  setAltairResult(newResult);
                } else {
                  setMatplotlibResult(newResult);
                }
                // Update session state with new messages
                if (resultData.agent_log) {
                  setSession((prev) => prev ? {
                    ...prev,
                    messages: resultData.agent_log!.messages,
                    toolCalls: resultData.agent_log!.tool_calls,
                  } : null);
                }
                setProgress(null);
                break;
              }
              case 'error': {
                const errorData = event.data as ErrorEventData;
                setError(errorData.message);
                setProgress(null);
                break;
              }
            }
          },
          abortControllerRef.current.signal
        );
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        if (err instanceof ApiError) {
          setError(err.detail || err.message);
        } else {
          setError(`Unexpected error: ${err}`);
        }
      } finally {
        setIsLoading(false);
        setProgress(null);
        abortControllerRef.current = null;
      }
    },
    [session]
  );

  const cancelVisualization = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      setProgress(null);
    }
  }, []);

  const clearResult = useCallback(() => {
    setResult(null);
    setMatplotlibResult(null);
    setAltairResult(null);
    setError(null);
    setProgress(null);
  }, []);

  const clearSession = useCallback(() => {
    setSession(null);
  }, []);

  const restoreResults = useCallback((
    savedMatplotlib: VisualizationResult | null,
    savedAltair: VisualizationResult | null
  ) => {
    if (savedMatplotlib) {
      setMatplotlibResult({
        image: savedMatplotlib.image,
        vegaSpec: savedMatplotlib.vega_spec,
        vizType: savedMatplotlib.viz_type,
        code: savedMatplotlib.code || '',
      });
    }
    if (savedAltair) {
      setAltairResult({
        image: savedAltair.image,
        vegaSpec: savedAltair.vega_spec,
        vizType: savedAltair.viz_type,
        code: savedAltair.code || '',
      });
    }
  }, []);

  return {
    isLoading,
    error,
    result,
    matplotlibResult,
    altairResult,
    progress,
    session,
    hasActiveSession: session !== null,
    generateVisualization,
    continueVisualization,
    replayVisualization,
    convertVisualization,
    cancelVisualization,
    clearResult,
    clearSession,
    restoreResults,
  };
}
