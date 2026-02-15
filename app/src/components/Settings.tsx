/**
 * Settings component for API key configuration.
 */

import { useCallback, useEffect, useState } from 'react';
import { getApiKey, setApiKey, clearApiKey, checkConfigStatus } from '../lib/api';

interface SettingsProps {
  onApiKeyChange?: () => void;
}

export function Settings({ onApiKeyChange }: SettingsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [hasServerKey, setHasServerKey] = useState<boolean | null>(null);
  const [hasLocalKey, setHasLocalKey] = useState(false);
  const [claudeCodeAvailable, setClaudeCodeAvailable] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Check server config status on mount
  useEffect(() => {
    checkConfigStatus()
      .then((status) => {
        setHasServerKey(status.api_key_configured);
        setClaudeCodeAvailable(status.claude_code_available);
      })
      .catch(() => setHasServerKey(false));

    const localKey = getApiKey();
    setHasLocalKey(!!localKey);
  }, []);

  const handleSave = useCallback(() => {
    if (!apiKeyInput.trim()) {
      setMessage({ type: 'error', text: 'Please enter an API key' });
      return;
    }

    setIsSaving(true);
    try {
      setApiKey(apiKeyInput.trim());
      setHasLocalKey(true);
      setApiKeyInput('');
      setMessage({ type: 'success', text: 'API key saved' });
      onApiKeyChange?.();
      setTimeout(() => setMessage(null), 2000);
    } catch {
      setMessage({ type: 'error', text: 'Failed to save API key' });
    } finally {
      setIsSaving(false);
    }
  }, [apiKeyInput, onApiKeyChange]);

  const handleClear = useCallback(() => {
    clearApiKey();
    setHasLocalKey(false);
    setMessage({ type: 'success', text: 'API key cleared' });
    onApiKeyChange?.();
    setTimeout(() => setMessage(null), 2000);
  }, [onApiKeyChange]);

  const needsApiKey = hasServerKey === false && !hasLocalKey && !claudeCodeAvailable;

  return (
    <div className="relative">
      {/* Settings button with indicator */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`p-2 rounded-md transition-colors ${
          needsApiKey
            ? 'text-amber-600 hover:bg-amber-50'
            : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'
        }`}
        title={needsApiKey ? 'API key required' : 'Settings'}
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
        {needsApiKey && (
          <span className="absolute top-0 right-0 w-2 h-2 bg-amber-500 rounded-full" />
        )}
      </button>

      {/* Settings panel */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Panel */}
          <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-20">
            <div className="p-4">
              <h3 className="text-sm font-medium text-gray-900 mb-3">
                API Configuration
              </h3>

              {/* Status indicator */}
              <div className="mb-4 p-3 bg-gray-50 rounded-md text-sm">
                {claudeCodeAvailable && (
                  <div className="flex items-center gap-2 mb-2 p-2 bg-green-50 rounded border border-green-200">
                    <span className="w-2 h-2 rounded-full bg-green-500" />
                    <span className="text-green-700 font-medium">
                      Claude Code subscription detected
                    </span>
                  </div>
                )}
                {claudeCodeAvailable && !hasServerKey && !hasLocalKey && (
                  <p className="text-xs text-green-600 mb-2">
                    Using Claude Code authentication — no API key required.
                  </p>
                )}
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      hasServerKey ? 'bg-green-500' : 'bg-gray-300'
                    }`}
                  />
                  <span className="text-gray-600">
                    Server API key: {hasServerKey ? 'Configured' : 'Not configured'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      hasLocalKey ? 'bg-green-500' : 'bg-gray-300'
                    }`}
                  />
                  <span className="text-gray-600">
                    Local API key: {hasLocalKey ? 'Set' : 'Not set'}
                  </span>
                </div>
              </div>

              {/* API key input */}
              <div className="space-y-3">
                <div>
                  <label
                    htmlFor="api-key"
                    className="block text-sm text-gray-600 mb-1"
                  >
                    Anthropic API Key
                  </label>
                  <input
                    id="api-key"
                    type="password"
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder={hasLocalKey ? '••••••••' : 'sk-ant-...'}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSave();
                    }}
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Your key is stored locally in your browser.
                  </p>
                </div>

                {/* Message */}
                {message && (
                  <div
                    className={`text-sm p-2 rounded ${
                      message.type === 'success'
                        ? 'bg-green-50 text-green-700'
                        : 'bg-red-50 text-red-700'
                    }`}
                  >
                    {message.text}
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="flex-1 px-3 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                  >
                    {isSaving ? 'Saving...' : 'Save'}
                  </button>
                  {hasLocalKey && (
                    <button
                      onClick={handleClear}
                      className="px-3 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50"
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
