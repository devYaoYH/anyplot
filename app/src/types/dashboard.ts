/**
 * Type definitions for the multi-chart dashboard feature.
 */

import type { Layout } from 'react-grid-layout';

export interface DashboardChart {
  id: string;
  title?: string;
  vegaSpec: object;
  code: string;
  createdAt: Date;
  filterableFields: string[];
  layout: Layout;
}

export interface DashboardFilter {
  id: string;
  field: string;
  operator: 'equals' | 'contains' | 'gt' | 'lt' | 'range' | 'in';
  value: unknown;
}

export type FilterOperator = DashboardFilter['operator'];

export interface FilterableFieldInfo {
  name: string;
  type: 'numeric' | 'categorical' | 'date' | 'unknown';
  uniqueValues?: unknown[];
  min?: number;
  max?: number;
}
