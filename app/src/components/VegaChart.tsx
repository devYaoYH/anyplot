/**
 * Vega-Lite chart renderer component using vega-embed.
 */

import { useEffect, useRef, useCallback } from 'react';
import embed from 'vega-embed';
import type { VisualizationSpec, Result } from 'vega-embed';

interface VegaChartProps {
  spec: object;
  onExportPng?: (blob: Blob) => void;
  className?: string;
  width?: number;
  height?: number;
}

export function VegaChart({ spec, onExportPng, className = '' }: VegaChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<Result | null>(null);

  useEffect(() => {
    if (!containerRef.current || !spec) return;

    const renderChart = async () => {
      try {
        // Clear any existing chart
        if (viewRef.current) {
          viewRef.current.finalize();
        }

        // Render the new chart
        const result = await embed(containerRef.current!, spec as VisualizationSpec, {
          actions: {
            export: true,
            source: false,
            compiled: false,
            editor: false,
          },
          renderer: 'canvas',
        });

        viewRef.current = result;
      } catch (error) {
        console.error('Failed to render Vega-Lite chart:', error);
      }
    };

    renderChart();

    // Cleanup on unmount
    return () => {
      if (viewRef.current) {
        viewRef.current.finalize();
        viewRef.current = null;
      }
    };
  }, [spec]);

  const handleExportPng = useCallback(async () => {
    if (!viewRef.current || !onExportPng) return;

    try {
      const canvas = await viewRef.current.view.toCanvas();
      canvas.toBlob((blob) => {
        if (blob) {
          onExportPng(blob);
        }
      }, 'image/png');
    } catch (error) {
      console.error('Failed to export PNG:', error);
    }
  }, [onExportPng]);

  return (
    <div className={`vega-chart-container ${className}`}>
      <div ref={containerRef} className="w-full" />
      {onExportPng && (
        <button
          onClick={handleExportPng}
          className="mt-2 px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded border border-gray-300 transition-colors"
        >
          Download PNG
        </button>
      )}
    </div>
  );
}

export default VegaChart;
