/**
 * Hook for visualization API communication.
 */

import { useCallback, useState } from 'react';
import { visualize, ApiError, getApiKey } from '../lib/api';
import type { VisualizeRequest, VisualizeResponse } from '../lib/api';

export interface UseVisualizeReturn {
  isLoading: boolean;
  error: string | null;
  result: VisualizeResponse | null;
  generateVisualization: (data: Record<string, unknown>[], prompt: string) => Promise<void>;
  clearResult: () => void;
}

export function useVisualize(): UseVisualizeReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VisualizeResponse | null>(null);

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

      setIsLoading(true);
      setError(null);

      try {
        const apiKey = getApiKey();
        const request: VisualizeRequest = {
          data,
          prompt: prompt.trim(),
          ...(apiKey && { api_key: apiKey }),
        };

        const response = await visualize(request);
        setResult(response);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.detail || err.message);
        } else {
          setError(`Unexpected error: ${err}`);
        }
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const clearResult = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return {
    isLoading,
    error,
    result,
    generateVisualization,
    clearResult,
  };
}
