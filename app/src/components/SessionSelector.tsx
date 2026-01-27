/**
 * Session selector component for managing saved sessions.
 */

import { useState } from 'react';
import type { SessionData, SessionMetadata } from '../lib/api';

interface SessionSelectorProps {
  currentSession: SessionData | null;
  sessions: SessionMetadata[];
  isLoading: boolean;
  onCreateSession: (name?: string) => Promise<void>;
  onLoadSession: (sessionId: string) => Promise<void>;
  onDeleteSession: () => Promise<void>;
}

export function SessionSelector({
  currentSession,
  sessions,
  isLoading,
  onCreateSession,
  onLoadSession,
  onDeleteSession,
}: SessionSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [newSessionName, setNewSessionName] = useState('');
  const [showNewForm, setShowNewForm] = useState(false);

  const handleCreateSession = async () => {
    await onCreateSession(newSessionName || undefined);
    setNewSessionName('');
    setShowNewForm(false);
    setIsOpen(false);
  };

  const handleLoadSession = async (sessionId: string) => {
    await onLoadSession(sessionId);
    setIsOpen(false);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        className="flex items-center gap-2 px-3 py-1.5 text-sm bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
        </svg>
        <span className="max-w-[150px] truncate">
          {currentSession ? currentSession.name : 'No Session'}
        </span>
        <svg className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-white border border-gray-200 rounded-md shadow-lg z-50">
          <div className="p-2 border-b border-gray-100">
            {showNewForm ? (
              <div className="space-y-2">
                <input
                  type="text"
                  value={newSessionName}
                  onChange={(e) => setNewSessionName(e.target.value)}
                  placeholder="Session name (optional)"
                  className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleCreateSession}
                    disabled={isLoading}
                    className="flex-1 px-2 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    Create
                  </button>
                  <button
                    onClick={() => {
                      setShowNewForm(false);
                      setNewSessionName('');
                    }}
                    className="px-2 py-1 text-sm text-gray-600 hover:text-gray-800"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowNewForm(true)}
                className="w-full px-2 py-1.5 text-sm text-left text-blue-600 hover:bg-blue-50 rounded flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                New Session
              </button>
            )}
          </div>

          <div className="max-h-64 overflow-y-auto">
            {sessions.length === 0 ? (
              <div className="p-4 text-sm text-gray-500 text-center">
                No saved sessions
              </div>
            ) : (
              sessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => handleLoadSession(session.id)}
                  className={`w-full px-3 py-2 text-left hover:bg-gray-50 border-b border-gray-100 last:border-b-0 ${
                    currentSession?.id === session.id ? 'bg-blue-50' : ''
                  }`}
                >
                  <div className="text-sm font-medium text-gray-900 truncate">
                    {session.name}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {formatDate(session.updated_at)} · {session.row_count} rows · {session.snapshot_count} visualizations
                  </div>
                </button>
              ))
            )}
          </div>

          {currentSession && (
            <div className="p-2 border-t border-gray-100">
              <button
                onClick={onDeleteSession}
                disabled={isLoading}
                className="w-full px-2 py-1.5 text-sm text-left text-red-600 hover:bg-red-50 rounded flex items-center gap-2 disabled:opacity-50"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Delete Current Session
              </button>
            </div>
          )}
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}
