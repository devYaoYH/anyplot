/**
 * Hook for managing the multi-chart dashboard state.
 */

import { useState, useCallback, useMemo } from 'react';
import type { Layout } from 'react-grid-layout';
import type { DashboardChart, DashboardFilter } from '../types/dashboard';
import {
  extractFilterableFields,
  applyFiltersToSpec,
  collectAllFilterableFields,
  getApplicableFilters,
} from '../lib/vegaFilters';

const GRID_CONFIG = {
  cols: 12,
  rowHeight: 100,
  defaultSize: { w: 6, h: 4 },
  minSize: { w: 3, h: 2 },
};

export interface UseDashboardReturn {
  charts: DashboardChart[];
  filters: DashboardFilter[];
  allFilterableFields: string[];
  addChart: (vegaSpec: object, code: string, title?: string) => void;
  removeChart: (id: string) => void;
  updateLayout: (layouts: Layout[]) => void;
  addFilter: (filter: Omit<DashboardFilter, 'id'>) => void;
  removeFilter: (id: string) => void;
  updateFilter: (id: string, updates: Partial<Omit<DashboardFilter, 'id'>>) => void;
  clearFilters: () => void;
  getFilteredSpec: (chart: DashboardChart) => object;
  getApplicableFiltersForChart: (chart: DashboardChart) => DashboardFilter[];
  clearDashboard: () => void;
}

export function useDashboard(): UseDashboardReturn {
  const [charts, setCharts] = useState<DashboardChart[]>([]);
  const [filters, setFilters] = useState<DashboardFilter[]>([]);

  // Collect all filterable fields from all charts
  const allFilterableFields = useMemo(
    () => collectAllFilterableFields(charts),
    [charts]
  );

  // Calculate next available position in grid
  const getNextPosition = useCallback((existingCharts: DashboardChart[]) => {
    if (existingCharts.length === 0) {
      return { x: 0, y: 0 };
    }

    // Find the bottom-most row
    let maxY = 0;
    let maxYHeight = 0;
    existingCharts.forEach((chart) => {
      const bottom = chart.layout.y + chart.layout.h;
      if (bottom > maxY) {
        maxY = chart.layout.y;
        maxYHeight = chart.layout.h;
      }
    });

    // Find available x position in the bottom row
    const bottomRowCharts = existingCharts.filter(
      (chart) => chart.layout.y === maxY
    );
    const occupiedWidth = bottomRowCharts.reduce(
      (sum, chart) => sum + chart.layout.w,
      0
    );

    if (occupiedWidth + GRID_CONFIG.defaultSize.w <= GRID_CONFIG.cols) {
      // Fits in current row
      return { x: occupiedWidth, y: maxY };
    }

    // Start new row
    return { x: 0, y: maxY + maxYHeight };
  }, []);

  const addChart = useCallback(
    (vegaSpec: object, code: string, title?: string) => {
      const id = crypto.randomUUID().slice(0, 8);
      const filterableFields = extractFilterableFields(vegaSpec);
      const position = getNextPosition(charts);

      const newChart: DashboardChart = {
        id,
        title: title || `Chart ${charts.length + 1}`,
        vegaSpec,
        code,
        createdAt: new Date(),
        filterableFields,
        layout: {
          i: id,
          x: position.x,
          y: position.y,
          w: GRID_CONFIG.defaultSize.w,
          h: GRID_CONFIG.defaultSize.h,
          minW: GRID_CONFIG.minSize.w,
          minH: GRID_CONFIG.minSize.h,
        },
      };

      setCharts((prev) => [...prev, newChart]);
    },
    [charts, getNextPosition]
  );

  const removeChart = useCallback((id: string) => {
    setCharts((prev) => prev.filter((chart) => chart.id !== id));
  }, []);

  const updateLayout = useCallback((layouts: Layout[]) => {
    setCharts((prev) =>
      prev.map((chart) => {
        const newLayout = layouts.find((l) => l.i === chart.id);
        if (newLayout) {
          return { ...chart, layout: newLayout };
        }
        return chart;
      })
    );
  }, []);

  const addFilter = useCallback(
    (filter: Omit<DashboardFilter, 'id'>) => {
      const id = crypto.randomUUID().slice(0, 8);
      setFilters((prev) => [...prev, { ...filter, id }]);
    },
    []
  );

  const removeFilter = useCallback((id: string) => {
    setFilters((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const updateFilter = useCallback(
    (id: string, updates: Partial<Omit<DashboardFilter, 'id'>>) => {
      setFilters((prev) =>
        prev.map((f) => (f.id === id ? { ...f, ...updates } : f))
      );
    },
    []
  );

  const clearFilters = useCallback(() => {
    setFilters([]);
  }, []);

  const getFilteredSpec = useCallback(
    (chart: DashboardChart) => {
      return applyFiltersToSpec(chart.vegaSpec, filters, chart.filterableFields);
    },
    [filters]
  );

  const getApplicableFiltersForChart = useCallback(
    (chart: DashboardChart) => {
      return getApplicableFilters(filters, chart.filterableFields);
    },
    [filters]
  );

  const clearDashboard = useCallback(() => {
    setCharts([]);
    setFilters([]);
  }, []);

  return {
    charts,
    filters,
    allFilterableFields,
    addChart,
    removeChart,
    updateLayout,
    addFilter,
    removeFilter,
    updateFilter,
    clearFilters,
    getFilteredSpec,
    getApplicableFiltersForChart,
    clearDashboard,
  };
}
