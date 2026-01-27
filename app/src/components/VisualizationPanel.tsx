/**
 * Visualization panel with dual-mode support (matplotlib and Vega-Lite).
 */

import { useState, useCallback } from 'react';
import type { ProgressStatus, VisualizeResult } from '../hooks/useVisualize';
import type { VizMode } from '../lib/api';
import { VegaChart } from './VegaChart';

type TabType = 'static' | 'interactive';

interface VisualizationPanelProps {
  onVisualize: (prompt: string, vizMode?: VizMode) => void;
  onContinue?: (prompt: string) => void;
  onConvert?: (targetMode: VizMode) => void;
  onCancel?: () => void;
  onNewVisualization?: () => void;
  isLoading: boolean;
  result: VisualizeResult | null;
  matplotlibResult: VisualizeResult | null;
  altairResult: VisualizeResult | null;
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
  onConvert,
  onCancel,
  onNewVisualization,
  isLoading,
  result: _result,
  matplotlibResult,
  altairResult,
  error,
  progress,
  hasActiveSession = false,
  disabled = false,
}: VisualizationPanelProps) {
  // result is passed but we use matplotlibResult/altairResult for tab-specific display
  void _result;
  const [prompt, setPrompt] = useState('');
  const [showCode, setShowCode] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('static');
  const [vizMode, setVizMode] = useState<VizMode>('matplotlib');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim() && !disabled && !isLoading) {
      if (hasActiveSession && onContinue) {
        onContinue(prompt.trim());
      } else {
        onVisualize(prompt.trim(), vizMode);
        // Switch to the appropriate tab based on mode
        setActiveTab(vizMode === 'altair' ? 'interactive' : 'static');
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

  const handleConvertToInteractive = () => {
    if (onConvert && matplotlibResult?.code) {
      onConvert('altair');
      setActiveTab('interactive');
    }
  };

  const handleConvertToStatic = () => {
    if (onConvert && altairResult?.code) {
      onConvert('matplotlib');
      setActiveTab('static');
    }
  };

  const handleExportPng = useCallback((blob: Blob) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'visualization.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, []);

  const handleModeToggle = (mode: VizMode) => {
    setVizMode(mode);
  };

  // Determine which result to show based on active tab
  const currentResult = activeTab === 'interactive' ? altairResult : matplotlibResult;
  const hasStaticResult = matplotlibResult?.image;
  const hasInteractiveResult = altairResult?.vegaSpec;
  const hasAnyResult = hasStaticResult || hasInteractiveResult;

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

      <form onSubmit={handleSubmit} className="space-y-3">
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

        {/* Mode Toggle - Only show when not in an active session */}
        {!hasActiveSession && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">Output mode:</span>
            <div className="flex rounded-lg border border-gray-300 overflow-hidden">
              <button
                type="button"
                onClick={() => handleModeToggle('matplotlib')}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  vizMode === 'matplotlib'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                Static (Python)
              </button>
              <button
                type="button"
                onClick={() => handleModeToggle('altair')}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  vizMode === 'altair'
                    ? 'bg-purple-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                Interactive
              </button>
            </div>
          </div>
        )}

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
                    : vizMode === 'altair'
                      ? 'bg-purple-600 hover:bg-purple-700'
                      : 'bg-green-600 hover:bg-green-700'
              }
            `}
          >
            {isLoading
              ? hasActiveSession ? 'Adjusting...' : 'Generating...'
              : hasActiveSession
                ? 'Send Adjustment'
                : vizMode === 'altair'
                  ? 'Generate Interactive'
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

      {hasAnyResult && (
        <div className="space-y-3">
          {/* Tab Navigation */}
          <div className="flex items-center justify-between">
            <div className="flex border-b border-gray-200">
              <button
                onClick={() => setActiveTab('static')}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'static'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } ${!hasStaticResult ? 'opacity-50' : ''}`}
              >
                Static (Python)
                {hasStaticResult && <span className="ml-1 text-green-500">*</span>}
              </button>
              <button
                onClick={() => setActiveTab('interactive')}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'interactive'
                    ? 'border-purple-600 text-purple-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } ${!hasInteractiveResult ? 'opacity-50' : ''}`}
              >
                Interactive
                {hasInteractiveResult && <span className="ml-1 text-green-500">*</span>}
              </button>
            </div>
            <button
              onClick={() => setShowCode(!showCode)}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {showCode ? 'Hide Code' : 'Show Code'}
            </button>
          </div>

          {/* Tab Content */}
          <div className="border rounded-md overflow-hidden bg-white">
            {activeTab === 'static' ? (
              hasStaticResult ? (
                <div>
                  <img
                    src={`data:image/png;base64,${matplotlibResult!.image}`}
                    alt="Generated visualization"
                    className="max-w-full h-auto"
                  />
                </div>
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <p>No static visualization yet.</p>
                  {hasInteractiveResult && onConvert && (
                    <button
                      onClick={handleConvertToStatic}
                      disabled={isLoading}
                      className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                    >
                      Convert to Python
                    </button>
                  )}
                </div>
              )
            ) : (
              hasInteractiveResult ? (
                <div className="p-4">
                  <VegaChart
                    spec={altairResult!.vegaSpec!}
                    onExportPng={handleExportPng}
                  />
                </div>
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <p>No interactive visualization yet.</p>
                  {hasStaticResult && onConvert && (
                    <button
                      onClick={handleConvertToInteractive}
                      disabled={isLoading}
                      className="mt-3 px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                    >
                      Convert to Interactive
                    </button>
                  )}
                </div>
              )
            )}
          </div>

          {/* Conversion buttons when viewing the current result */}
          {onConvert && (
            <div className="flex gap-2 justify-end">
              {activeTab === 'static' && hasStaticResult && (
                <button
                  onClick={handleConvertToInteractive}
                  disabled={isLoading}
                  className="px-3 py-1.5 text-sm bg-purple-100 text-purple-700 rounded-md hover:bg-purple-200 disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  Convert to Interactive
                </button>
              )}
              {activeTab === 'interactive' && hasInteractiveResult && (
                <button
                  onClick={handleConvertToStatic}
                  disabled={isLoading}
                  className="px-3 py-1.5 text-sm bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  Convert to Python
                </button>
              )}
            </div>
          )}

          {/* Code Display */}
          {showCode && currentResult?.code && (
            <div className="bg-gray-900 rounded-md p-4 overflow-auto">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-gray-400">
                  {activeTab === 'interactive' ? 'Altair (Python)' : 'matplotlib (Python)'}
                </span>
              </div>
              <pre className="text-sm text-gray-100 whitespace-pre-wrap">
                {currentResult.code}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
