/**
 * Unit tests for useVisualize hook.
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useVisualize } from './useVisualize';

describe('useVisualize', () => {
  describe('restoreResults', () => {
    it('restores matplotlib result from saved session data', () => {
      const { result } = renderHook(() => useVisualize());

      act(() => {
        result.current.restoreResults(
          {
            image: 'base64-image-data',
            vega_spec: undefined,
            viz_type: 'image',
            code: 'import matplotlib.pyplot as plt\nplt.show()',
          },
          null
        );
      });

      expect(result.current.matplotlibResult).toEqual({
        image: 'base64-image-data',
        vegaSpec: undefined,
        vizType: 'image',
        code: 'import matplotlib.pyplot as plt\nplt.show()',
      });
      expect(result.current.altairResult).toBeNull();
    });

    it('restores altair result from saved session data', () => {
      const { result } = renderHook(() => useVisualize());

      act(() => {
        result.current.restoreResults(
          null,
          {
            image: undefined,
            vega_spec: { mark: 'bar', encoding: { x: { field: 'a' } } },
            viz_type: 'vega_lite',
            code: 'import altair as alt\nalt.Chart()',
          }
        );
      });

      expect(result.current.altairResult).toEqual({
        image: undefined,
        vegaSpec: { mark: 'bar', encoding: { x: { field: 'a' } } },
        vizType: 'vega_lite',
        code: 'import altair as alt\nalt.Chart()',
      });
      expect(result.current.matplotlibResult).toBeNull();
    });

    it('restores both matplotlib and altair results simultaneously', () => {
      const { result } = renderHook(() => useVisualize());

      act(() => {
        result.current.restoreResults(
          {
            image: 'matplotlib-image',
            viz_type: 'image',
            code: 'plt.show()',
          },
          {
            vega_spec: { mark: 'point' },
            viz_type: 'vega_lite',
            code: 'alt.Chart()',
          }
        );
      });

      expect(result.current.matplotlibResult).not.toBeNull();
      expect(result.current.matplotlibResult?.image).toBe('matplotlib-image');
      expect(result.current.altairResult).not.toBeNull();
      expect(result.current.altairResult?.vegaSpec).toEqual({ mark: 'point' });
    });

    it('handles null values gracefully', () => {
      const { result } = renderHook(() => useVisualize());

      act(() => {
        result.current.restoreResults(null, null);
      });

      expect(result.current.matplotlibResult).toBeNull();
      expect(result.current.altairResult).toBeNull();
    });

    it('handles missing code field by defaulting to empty string', () => {
      const { result } = renderHook(() => useVisualize());

      act(() => {
        result.current.restoreResults(
          {
            image: 'image-data',
            viz_type: 'image',
            // code is undefined
          },
          null
        );
      });

      expect(result.current.matplotlibResult?.code).toBe('');
    });
  });

  describe('clearResult', () => {
    it('clears restored matplotlib and altair results', () => {
      const { result } = renderHook(() => useVisualize());

      // First restore some results
      act(() => {
        result.current.restoreResults(
          { image: 'img', viz_type: 'image', code: 'code' },
          { vega_spec: { mark: 'bar' }, viz_type: 'vega_lite', code: 'code' }
        );
      });

      expect(result.current.matplotlibResult).not.toBeNull();
      expect(result.current.altairResult).not.toBeNull();

      // Then clear
      act(() => {
        result.current.clearResult();
      });

      expect(result.current.matplotlibResult).toBeNull();
      expect(result.current.altairResult).toBeNull();
    });
  });

  describe('initial state', () => {
    it('has null results on initialization', () => {
      const { result } = renderHook(() => useVisualize());

      expect(result.current.matplotlibResult).toBeNull();
      expect(result.current.altairResult).toBeNull();
      expect(result.current.result).toBeNull();
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
      expect(result.current.hasActiveSession).toBe(false);
    });
  });
});
