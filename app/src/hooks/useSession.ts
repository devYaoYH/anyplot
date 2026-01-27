/**
 * Hook for managing session persistence.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  createSession,
  getSession,
  updateSession,
  listSessions,
  deleteSession,
  ApiError,
} from '../lib/api';
import type {
  SessionData,
  SessionMetadata,
  UpdateSessionRequest,
} from '../lib/api';

const SESSION_ID_KEY = 'sanctum_current_session_id';

export interface UseSessionReturn {
  currentSession: SessionData | null;
  sessions: SessionMetadata[];
  isLoading: boolean;
  error: string | null;
  createNewSession: (name?: string) => Promise<SessionData | null>;
  loadSession: (sessionId: string) => Promise<SessionData | null>;
  saveSession: (updates: UpdateSessionRequest) => Promise<void>;
  deleteCurrentSession: () => Promise<void>;
  refreshSessions: () => Promise<void>;
  clearError: () => void;
}

export function useSession(): UseSessionReturn {
  const [currentSession, setCurrentSession] = useState<SessionData | null>(null);
  const [sessions, setSessions] = useState<SessionMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Load sessions list and current session on mount
  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      try {
        // Load sessions list
        const sessionsList = await listSessions();
        setSessions(sessionsList);

        // Try to restore last session
        const lastSessionId = localStorage.getItem(SESSION_ID_KEY);
        if (lastSessionId) {
          try {
            const session = await getSession(lastSessionId);
            setCurrentSession(session);
          } catch {
            // Session no longer exists, clear storage
            localStorage.removeItem(SESSION_ID_KEY);
          }
        }
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.detail || err.message);
        } else {
          setError('Failed to initialize sessions');
        }
      } finally {
        setIsLoading(false);
      }
    };

    init();
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const sessionsList = await listSessions();
      setSessions(sessionsList);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail || err.message);
      }
    }
  }, []);

  const createNewSession = useCallback(async (name?: string): Promise<SessionData | null> => {
    setIsLoading(true);
    setError(null);
    try {
      const session = await createSession(name);
      setCurrentSession(session);
      localStorage.setItem(SESSION_ID_KEY, session.id);
      await refreshSessions();
      return session;
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail || err.message);
      } else {
        setError('Failed to create session');
      }
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [refreshSessions]);

  const loadSession = useCallback(async (sessionId: string): Promise<SessionData | null> => {
    setIsLoading(true);
    setError(null);
    try {
      const session = await getSession(sessionId);
      setCurrentSession(session);
      localStorage.setItem(SESSION_ID_KEY, session.id);
      return session;
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail || err.message);
      } else {
        setError('Failed to load session');
      }
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const saveSession = useCallback(async (updates: UpdateSessionRequest) => {
    if (!currentSession) {
      // Auto-create session if none exists
      const newSession = await createNewSession();
      if (!newSession) return;
    }

    const sessionId = currentSession?.id || localStorage.getItem(SESSION_ID_KEY);
    if (!sessionId) return;

    // Debounce saves
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(async () => {
      try {
        const updated = await updateSession(sessionId, updates);
        setCurrentSession(updated);
        await refreshSessions();
      } catch (err) {
        if (err instanceof ApiError) {
          console.error('Failed to save session:', err.detail || err.message);
        }
      }
    }, 500);
  }, [currentSession, createNewSession, refreshSessions]);

  const deleteCurrentSession = useCallback(async () => {
    if (!currentSession) return;

    setIsLoading(true);
    setError(null);
    try {
      await deleteSession(currentSession.id);
      localStorage.removeItem(SESSION_ID_KEY);
      setCurrentSession(null);
      await refreshSessions();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail || err.message);
      } else {
        setError('Failed to delete session');
      }
    } finally {
      setIsLoading(false);
    }
  }, [currentSession, refreshSessions]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    currentSession,
    sessions,
    isLoading,
    error,
    createNewSession,
    loadSession,
    saveSession,
    deleteCurrentSession,
    refreshSessions,
    clearError,
  };
}
