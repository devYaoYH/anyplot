/**
 * Visualization panel with prompt input and image display.
 */

import { useState } from 'react';
import type { ProgressStatus } from '../hooks/useVisualize';

interface VisualizationPanelProps {
  onVisualize: (prompt: string) => void;
  onContinue?: (prompt: string) => void;
  onCancel?: () => void;
  onNewVisualization?: () => void;
  isLoading: boolean;
  imageBase64: string | null;
  code: string | null;
  error: string | null;
  progress: ProgressStatus | null;
  hasActiveSession?: boolean;
  disabled?: boolean;
}

const stageLabels: Record<ProgressStatus['stage'], string> = {
  initializing: 'Initializing',
  generating: 'Generating code',
  validating: 'Validating code',
  executing: 'Executing',
  retrying: 'Retrying',
};

export function VisualizationPanel({
  onVisualize,
  onContinue,
  onCancel,
  onNewVisualization,
  isLoading,
  imageBase64,
  code,
  error,
  progress,
  hasActiveSession = false,
  disabled = false,
}: VisualizationPanelProps) {
  const [prompt, setPrompt] = useState('');
  const [showCode, setShowCode] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim() && !disabled && !isLoading) {
      if (hasActiveSession && onContinue) {
        onContinue(prompt.trim());
      } else {
        onVisualize(prompt.trim());
      }
      // Clear prompt after continuing but not after new visualization
      if (hasActiveSession) {
        setPrompt('');
      }
    }
  };

  const handleNewVisualization = () => {
    setPrompt('');
    onNewVisualization?.();
  };

  return (
    <div className="space-y-4">
      {hasActiveSession && (
        <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-md">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            <span className="text-sm text-blue-700">
              Active session - type to adjust the visualization
            </span>
          </div>
          <button
            onClick={handleNewVisualization}
            className="text-xs text-blue-600 hover:text-blue-800 underline"
          >
            Start new
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">
          {hasActiveSession ? 'Adjustment Request' : 'Visualization Prompt'}
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={
            hasActiveSession
              ? "Describe how you'd like to adjust the visualization (e.g., 'Change the colors to blue', 'Add a title')"
              : "Describe the visualization you want (e.g., 'Create a bar chart of sales by region')"
          }
          disabled={disabled || isLoading}
          rows={3}
          className={`
            w-full px-3 py-2 border rounded-md
            focus:outline-none focus:ring-2 focus:ring-blue-500
            ${disabled ? 'bg-gray-100 cursor-not-allowed' : 'bg-white'}
            ${hasActiveSession ? 'border-blue-300' : ''}
          `}
        />
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={disabled || isLoading || !prompt.trim()}
            className={`
              px-4 py-2 rounded-md text-white font-medium
              transition-colors duration-200
              ${
                disabled || isLoading || !prompt.trim()
                  ? 'bg-gray-400 cursor-not-allowed'
                  : hasActiveSession
                    ? 'bg-blue-600 hover:bg-blue-700'
                    : 'bg-green-600 hover:bg-green-700'
              }
            `}
          >
            {isLoading
              ? hasActiveSession ? 'Adjusting...' : 'Generating...'
              : hasActiveSession
                ? 'Send Adjustment'
                : 'Generate Visualization'}
          </button>
          {isLoading && onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 rounded-md text-gray-700 border border-gray-300 hover:bg-gray-50 transition-colors duration-200"
            >
              Cancel
            </button>
          )}
        </div>
      </form>

      {progress && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
          <div className="flex items-center gap-3">
            <div className="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full" />
            <div>
              <p className="text-sm font-medium text-blue-800">
                {stageLabels[progress.stage]}
                {progress.attempt && progress.attempt > 1 && (
                  <span className="text-blue-600"> (Attempt {progress.attempt})</span>
                )}
              </p>
              <p className="text-sm text-blue-600">{progress.message}</p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {imageBase64 && (
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-medium text-gray-700">Result</h3>
            <button
              onClick={() => setShowCode(!showCode)}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {showCode ? 'Hide Code' : 'Show Code'}
            </button>
          </div>
          <div className="border rounded-md overflow-hidden bg-white">
            <img
              src={`data:image/png;base64,${imageBase64}`}
              alt="Generated visualization"
              className="max-w-full h-auto"
            />
          </div>
          {showCode && code && (
            <div className="bg-gray-900 rounded-md p-4 overflow-auto">
              <pre className="text-sm text-gray-100 whitespace-pre-wrap">
                {code}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
