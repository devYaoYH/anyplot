/**
 * Visualization panel with prompt input and image display.
 */

import { useState } from 'react';

interface VisualizationPanelProps {
  onVisualize: (prompt: string) => void;
  isLoading: boolean;
  imageBase64: string | null;
  code: string | null;
  error: string | null;
  disabled?: boolean;
}

export function VisualizationPanel({
  onVisualize,
  isLoading,
  imageBase64,
  code,
  error,
  disabled = false,
}: VisualizationPanelProps) {
  const [prompt, setPrompt] = useState('');
  const [showCode, setShowCode] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim() && !disabled && !isLoading) {
      onVisualize(prompt.trim());
    }
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">
          Visualization Prompt
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe the visualization you want (e.g., 'Create a bar chart of sales by region')"
          disabled={disabled || isLoading}
          rows={3}
          className={`
            w-full px-3 py-2 border rounded-md
            focus:outline-none focus:ring-2 focus:ring-blue-500
            ${disabled ? 'bg-gray-100 cursor-not-allowed' : 'bg-white'}
          `}
        />
        <button
          type="submit"
          disabled={disabled || isLoading || !prompt.trim()}
          className={`
            px-4 py-2 rounded-md text-white font-medium
            transition-colors duration-200
            ${
              disabled || isLoading || !prompt.trim()
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-green-600 hover:bg-green-700'
            }
          `}
        >
          {isLoading ? 'Generating...' : 'Generate Visualization'}
        </button>
      </form>

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
