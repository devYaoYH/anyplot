/**
 * Hook for visualization API communication with streaming support.
 */

import { useCallback, useRef, useState } from 'react';
import {
  visualizeStream,
  ApiError,
  getApiKey,
} from '../lib/api';
import type {
  VisualizeRequest,
  VisualizeResponse,
  StreamEvent,
  StatusEventData,
  ResultEventData,
  ErrorEventData,
  AgentLog,
} from '../lib/api';

export interface ProgressStatus {
  stage: StatusEventData['stage'];
  message: string;
  attempt?: number;
}

export interface VisualizeResult extends VisualizeResponse {
  agentLog?: AgentLog;
}

export interface UseVisualizeReturn {
  isLoading: boolean;
  error: string | null;
  result: VisualizeResult | null;
  progress: ProgressStatus | null;
  generateVisualization: (data: Record<string, unknown>[], prompt: string) => Promise<void>;
  cancelVisualization: () => void;
  clearResult: () => void;
}

export function useVisualize(): UseVisualizeReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VisualizeResult | null>(null);
  const [progress, setProgress] = useState<ProgressStatus | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const generateVisualization = useCallback(
    async (data: Record<string, unknown>[], prompt: string) => {
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

      try {
        const apiKey = getApiKey();
        const request: VisualizeRequest = {
          data,
          prompt: prompt.trim(),
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
                setResult({
                  image: resultData.image,
                  code: resultData.code,
                  agentLog: resultData.agent_log,
                });
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
    setError(null);
    setProgress(null);
  }, []);

  return {
    isLoading,
    error,
    result,
    progress,
    generateVisualization,
    cancelVisualization,
    clearResult,
  };
}
