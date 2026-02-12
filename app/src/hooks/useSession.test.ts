/**
 * Unit tests for useSession hook.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useSession } from './useSession';
import * as api from '../lib/api';

// Mock the API module
vi.mock('../lib/api', () => ({
  listSessions: vi.fn(),
  createSession: vi.fn(),
  getSession: vi.fn(),
  updateSession: vi.fn(),
  deleteSession: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    detail?: string;
    constructor(message: string, status: number, detail?: string) {
      super(message);
      this.status = status;
      this.detail = detail;
    }
  },
}));

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('useSession', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.getItem.mockReturnValue(null);
    vi.mocked(api.listSessions).mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('initialization', () => {
    it('loads sessions list on mount', async () => {
      const mockSessions = [
        { id: 'sess1', name: 'Session 1', created_at: '2024-01-01', updated_at: '2024-01-01', row_count: 10, snapshot_count: 2 },
        { id: 'sess2', name: 'Session 2', created_at: '2024-01-02', updated_at: '2024-01-02', row_count: 5, snapshot_count: 1 },
      ];
      vi.mocked(api.listSessions).mockResolvedValue(mockSessions);

      const { result } = renderHook(() => useSession());

      await waitFor(() => {
        expect(result.current.sessions).toEqual(mockSessions);
      });
    });

    it('restores last session from localStorage', async () => {
      const mockSession = {
        id: 'sess1',
        name: 'Test Session',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        raw_data: [],
        sql_query: 'SELECT * FROM data',
        log_snapshots: [],
        matplotlib_result: null,
        altair_result: null,
      };
      localStorageMock.getItem.mockReturnValue('sess1');
      vi.mocked(api.listSessions).mockResolvedValue([]);
      vi.mocked(api.getSession).mockResolvedValue(mockSession);

      const { result } = renderHook(() => useSession());

      await waitFor(() => {
        expect(result.current.currentSession).toEqual(mockSession);
      });
    });
  });

  describe('saveSession', () => {
    it('does not reorder sessions list when saving', async () => {
      const initialSessions = [
        { id: 'sess1', name: 'Session 1', created_at: '2024-01-01', updated_at: '2024-01-01', row_count: 10, snapshot_count: 2 },
        { id: 'sess2', name: 'Session 2', created_at: '2024-01-02', updated_at: '2024-01-02', row_count: 5, snapshot_count: 1 },
        { id: 'sess3', name: 'Session 3', created_at: '2024-01-03', updated_at: '2024-01-03', row_count: 3, snapshot_count: 0 },
      ];

      const currentSession = {
        id: 'sess2',
        name: 'Session 2',
        created_at: '2024-01-02',
        updated_at: '2024-01-02',
        raw_data: [{ a: 1 }],
        sql_query: 'SELECT * FROM data',
        log_snapshots: [],
        matplotlib_result: null,
        altair_result: null,
      };

      const updatedSession = {
        ...currentSession,
        updated_at: '2024-01-04T00:00:00',
        raw_data: [{ a: 1 }, { a: 2 }],
      };

      localStorageMock.getItem.mockReturnValue('sess2');
      vi.mocked(api.listSessions).mockResolvedValue(initialSessions);
      vi.mocked(api.getSession).mockResolvedValue(currentSession);
      vi.mocked(api.updateSession).mockResolvedValue(updatedSession);

      const { result } = renderHook(() => useSession());

      // Wait for initialization
      await waitFor(() => {
        expect(result.current.currentSession).toEqual(currentSession);
      });

      // Save session - this triggers debounced save
      act(() => {
        result.current.saveSession({ raw_data: [{ a: 1 }, { a: 2 }] });
      });

      // Wait for debounced save to complete (500ms + processing)
      await waitFor(() => {
        expect(api.updateSession).toHaveBeenCalledWith('sess2', { raw_data: [{ a: 1 }, { a: 2 }] });
      }, { timeout: 2000 });

      // Verify sessions list order is preserved (sess2 should still be in position 1, not moved to position 0)
      const sessionIds = result.current.sessions.map(s => s.id);
      expect(sessionIds).toEqual(['sess1', 'sess2', 'sess3']);

      // Verify the updated metadata is reflected
      const sess2 = result.current.sessions.find(s => s.id === 'sess2');
      expect(sess2?.updated_at).toBe('2024-01-04T00:00:00');
      expect(sess2?.row_count).toBe(2);
    });

    it('updates session metadata optimistically without API refetch', async () => {
      const initialSessions = [
        { id: 'sess1', name: 'Session 1', created_at: '2024-01-01', updated_at: '2024-01-01', row_count: 0, snapshot_count: 0 },
      ];

      const currentSession = {
        id: 'sess1',
        name: 'Session 1',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        raw_data: [],
        sql_query: 'SELECT * FROM data',
        log_snapshots: [],
        matplotlib_result: null,
        altair_result: null,
      };

      const updatedSession = {
        ...currentSession,
        updated_at: '2024-01-02T00:00:00',
        raw_data: [{ x: 1 }, { x: 2 }, { x: 3 }] as Record<string, unknown>[],
        log_snapshots: [
          { id: 'snap1', timestamp: '2024-01-01', sql_query: 'SELECT *', user_prompt: 'test', agent_log: null, final_code: null, success: true, error: null },
        ],
      };

      localStorageMock.getItem.mockReturnValue('sess1');
      vi.mocked(api.listSessions).mockResolvedValue(initialSessions);
      vi.mocked(api.getSession).mockResolvedValue(currentSession);
      vi.mocked(api.updateSession).mockResolvedValue(updatedSession);

      const { result } = renderHook(() => useSession());

      await waitFor(() => {
        expect(result.current.currentSession).not.toBeNull();
      });

      // Clear mock to track future calls
      vi.mocked(api.listSessions).mockClear();

      // Save session
      act(() => {
        result.current.saveSession({ raw_data: [{ x: 1 }, { x: 2 }, { x: 3 }] });
      });

      // Wait for debounced save to complete
      await waitFor(() => {
        expect(api.updateSession).toHaveBeenCalled();
      }, { timeout: 2000 });

      // Verify listSessions was NOT called (no refetch)
      expect(api.listSessions).not.toHaveBeenCalled();

      // Verify metadata was updated locally
      const sess1 = result.current.sessions.find(s => s.id === 'sess1');
      expect(sess1?.row_count).toBe(3);
      expect(sess1?.snapshot_count).toBe(1);
    });
  });

  describe('loadSession', () => {
    it('loads session data including visualization results', async () => {
      const mockSession: api.SessionData = {
        id: 'sess1',
        name: 'Test Session',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        raw_data: [{ col1: 'value1' }],
        sql_query: 'SELECT * FROM data WHERE col1 = "value1"',
        log_snapshots: [
          { id: 'snap1', timestamp: '2024-01-01', sql_query: 'SELECT *', user_prompt: 'test', agent_log: null, final_code: null, success: true, error: null },
        ],
        matplotlib_result: { image: 'base64data', viz_type: 'image' as const, code: 'plt.show()' },
        altair_result: { vega_spec: { mark: 'bar' }, viz_type: 'vega_lite' as const, code: 'alt.Chart()' },
      };

      vi.mocked(api.listSessions).mockResolvedValue([]);
      vi.mocked(api.getSession).mockResolvedValue(mockSession);

      const { result } = renderHook(() => useSession());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      let loadedSession: api.SessionData | null = null;
      await act(async () => {
        loadedSession = await result.current.loadSession('sess1');
      });

      expect(loadedSession).toEqual(mockSession);
      expect(result.current.currentSession).toEqual(mockSession);
      expect(result.current.currentSession?.matplotlib_result).toEqual(mockSession.matplotlib_result);
      expect(result.current.currentSession?.altair_result).toEqual(mockSession.altair_result);
    });

    it('stores session ID in localStorage on load', async () => {
      const mockSession = {
        id: 'sess1',
        name: 'Test',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        raw_data: [],
        sql_query: '',
        log_snapshots: [],
        matplotlib_result: null,
        altair_result: null,
      };

      vi.mocked(api.listSessions).mockResolvedValue([]);
      vi.mocked(api.getSession).mockResolvedValue(mockSession);

      const { result } = renderHook(() => useSession());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.loadSession('sess1');
      });

      expect(localStorageMock.setItem).toHaveBeenCalledWith('sanctum_current_session_id', 'sess1');
    });
  });

  describe('createNewSession', () => {
    it('creates session and refreshes list', async () => {
      const newSession = {
        id: 'new-sess',
        name: 'New Session',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        raw_data: [],
        sql_query: 'SELECT * FROM data LIMIT 100',
        log_snapshots: [],
        matplotlib_result: null,
        altair_result: null,
      };

      vi.mocked(api.listSessions).mockResolvedValue([]);
      vi.mocked(api.createSession).mockResolvedValue(newSession);

      const { result } = renderHook(() => useSession());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.createNewSession('New Session');
      });

      expect(api.createSession).toHaveBeenCalledWith('New Session');
      expect(result.current.currentSession).toEqual(newSession);
      // refreshSessions should be called after creating a new session
      expect(api.listSessions).toHaveBeenCalledTimes(2); // once on init, once after create
    });
  });

  describe('deleteCurrentSession', () => {
    it('deletes session and refreshes list', async () => {
      const currentSession = {
        id: 'sess1',
        name: 'Test',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        raw_data: [],
        sql_query: '',
        log_snapshots: [],
        matplotlib_result: null,
        altair_result: null,
      };

      localStorageMock.getItem.mockReturnValue('sess1');
      vi.mocked(api.listSessions).mockResolvedValue([{ id: 'sess1', name: 'Test', created_at: '2024-01-01', updated_at: '2024-01-01', row_count: 0, snapshot_count: 0 }]);
      vi.mocked(api.getSession).mockResolvedValue(currentSession);
      vi.mocked(api.deleteSession).mockResolvedValue(undefined);

      const { result } = renderHook(() => useSession());

      await waitFor(() => {
        expect(result.current.currentSession).toEqual(currentSession);
      });

      await act(async () => {
        await result.current.deleteCurrentSession();
      });

      expect(api.deleteSession).toHaveBeenCalledWith('sess1');
      expect(result.current.currentSession).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('sanctum_current_session_id');
      // refreshSessions should be called after deleting
      expect(api.listSessions).toHaveBeenCalledTimes(2);
    });
  });
});
