/**
 * Utilities for extracting filterable fields from Vega-Lite specs
 * and applying filters to specs.
 */

import type { DashboardFilter, FilterableFieldInfo } from '../types/dashboard';

interface VegaLiteSpec {
  $schema?: string;
  data?: {
    values?: Record<string, unknown>[];
    [key: string]: unknown;
  };
  encoding?: Record<string, { field?: string; [key: string]: unknown }>;
  mark?: string | object;
  layer?: VegaLiteSpec[];
  hconcat?: VegaLiteSpec[];
  vconcat?: VegaLiteSpec[];
  concat?: VegaLiteSpec[];
  transform?: unknown[];
  title?: string | object;
  width?: number | string;
  height?: number | string;
  [key: string]: unknown;
}

export interface ExtractedChart {
  spec: object;
  title: string;
}

/**
 * Extracts all filterable fields from a Vega-Lite spec.
 * Fields are extracted from encoding channels and inline data.
 */
export function extractFilterableFields(spec: object): string[] {
  const fields = new Set<string>();
  const vegaSpec = spec as VegaLiteSpec;

  // Extract fields from encoding
  const extractFromEncoding = (encoding: VegaLiteSpec['encoding']) => {
    if (!encoding) return;
    for (const channel of Object.values(encoding)) {
      if (channel && typeof channel === 'object' && 'field' in channel && channel.field) {
        fields.add(channel.field as string);
      }
    }
  };

  // Extract fields from data.values
  const extractFromData = (data: VegaLiteSpec['data']) => {
    if (!data?.values || !Array.isArray(data.values)) return;
    if (data.values.length > 0) {
      Object.keys(data.values[0]).forEach((key) => fields.add(key));
    }
  };

  // Recursively process spec
  const processSpec = (s: VegaLiteSpec) => {
    extractFromEncoding(s.encoding);
    extractFromData(s.data);

    // Handle layered/concatenated specs
    if (s.layer) s.layer.forEach(processSpec);
    if (s.hconcat) s.hconcat.forEach(processSpec);
    if (s.vconcat) s.vconcat.forEach(processSpec);
    if (s.concat) s.concat.forEach(processSpec);
  };

  processSpec(vegaSpec);
  return Array.from(fields);
}

/**
 * Infers field type and metadata from data values.
 */
export function inferFieldInfo(
  spec: object,
  fieldName: string
): FilterableFieldInfo {
  const vegaSpec = spec as VegaLiteSpec;
  const values: unknown[] = [];

  // Collect values from data
  const collectValues = (s: VegaLiteSpec) => {
    if (s.data?.values && Array.isArray(s.data.values)) {
      for (const row of s.data.values) {
        if (fieldName in row) {
          values.push(row[fieldName]);
        }
      }
    }
    if (s.layer) s.layer.forEach(collectValues);
    if (s.hconcat) s.hconcat.forEach(collectValues);
    if (s.vconcat) s.vconcat.forEach(collectValues);
    if (s.concat) s.concat.forEach(collectValues);
  };

  collectValues(vegaSpec);

  if (values.length === 0) {
    return { name: fieldName, type: 'unknown' };
  }

  // Infer type from first non-null value
  const firstValue = values.find((v) => v !== null && v !== undefined);

  if (typeof firstValue === 'number') {
    const numericValues = values.filter((v): v is number => typeof v === 'number');
    return {
      name: fieldName,
      type: 'numeric',
      min: Math.min(...numericValues),
      max: Math.max(...numericValues),
    };
  }

  if (firstValue instanceof Date || (typeof firstValue === 'string' && !isNaN(Date.parse(firstValue)))) {
    return { name: fieldName, type: 'date' };
  }

  // Categorical - collect unique values
  const uniqueValues = Array.from(new Set(values.filter((v) => v !== null && v !== undefined)));
  return {
    name: fieldName,
    type: 'categorical',
    uniqueValues: uniqueValues.slice(0, 100), // Limit to 100 unique values
  };
}

/**
 * Converts a filter operator and value to a Vega-Lite filter expression.
 */
function filterToExpression(filter: DashboardFilter): string {
  const { field, operator, value } = filter;
  const escapedField = `datum['${field}']`;

  switch (operator) {
    case 'equals':
      if (typeof value === 'string') {
        return `${escapedField} === '${value}'`;
      }
      return `${escapedField} === ${value}`;

    case 'contains':
      return `indexof(toString(${escapedField}), '${value}') >= 0`;

    case 'gt':
      return `${escapedField} > ${value}`;

    case 'lt':
      return `${escapedField} < ${value}`;

    case 'range':
      if (Array.isArray(value) && value.length === 2) {
        return `${escapedField} >= ${value[0]} && ${escapedField} <= ${value[1]}`;
      }
      return 'true';

    case 'in':
      if (Array.isArray(value)) {
        const valueList = value
          .map((v) => (typeof v === 'string' ? `'${v}'` : v))
          .join(', ');
        return `indexof([${valueList}], ${escapedField}) >= 0`;
      }
      return 'true';

    default:
      return 'true';
  }
}

/**
 * Applies filters to a Vega-Lite spec.
 * Only applies filters for fields that exist in the chart.
 */
export function applyFiltersToSpec(
  spec: object,
  filters: DashboardFilter[],
  chartFields: string[]
): object {
  const applicableFilters = filters.filter((f) => chartFields.includes(f.field));

  if (applicableFilters.length === 0) {
    return spec;
  }

  const vegaSpec = spec as VegaLiteSpec;
  const existingTransforms = Array.isArray(vegaSpec.transform) ? vegaSpec.transform : [];

  const filterTransforms = applicableFilters.map((filter) => ({
    filter: filterToExpression(filter),
  }));

  return {
    ...vegaSpec,
    transform: [...existingTransforms, ...filterTransforms],
  };
}

/**
 * Gets the list of filters that apply to a specific chart based on its fields.
 */
export function getApplicableFilters(
  filters: DashboardFilter[],
  chartFields: string[]
): DashboardFilter[] {
  return filters.filter((f) => chartFields.includes(f.field));
}

/**
 * Collects all unique filterable fields from multiple charts.
 */
export function collectAllFilterableFields(
  charts: { filterableFields: string[] }[]
): string[] {
  const allFields = new Set<string>();
  charts.forEach((chart) => {
    chart.filterableFields.forEach((field) => allFields.add(field));
  });
  return Array.from(allFields).sort();
}

/**
 * Checks if a Vega-Lite spec is a composite spec (contains multiple charts).
 */
export function isCompositeSpec(spec: object): boolean {
  const vegaSpec = spec as VegaLiteSpec;
  return !!(
    vegaSpec.hconcat ||
    vegaSpec.vconcat ||
    vegaSpec.concat ||
    (vegaSpec.layer && vegaSpec.layer.length > 1)
  );
}

/**
 * Gets the title from a Vega-Lite spec or sub-spec.
 */
function getSpecTitle(spec: VegaLiteSpec, index: number, prefix: string): string {
  if (spec.title) {
    if (typeof spec.title === 'string') {
      return spec.title;
    }
    if (typeof spec.title === 'object' && 'text' in spec.title) {
      return String(spec.title.text);
    }
  }
  return `${prefix} ${index + 1}`;
}

/**
 * Creates a standalone spec from a sub-spec, inheriting shared properties.
 */
function createStandaloneSpec(
  subSpec: VegaLiteSpec,
  parentSpec: VegaLiteSpec
): object {
  const standalone: VegaLiteSpec = { ...subSpec };

  // Inherit $schema if not present
  if (!standalone.$schema && parentSpec.$schema) {
    standalone.$schema = parentSpec.$schema;
  }

  // Inherit data if sub-spec doesn't have its own
  if (!standalone.data && parentSpec.data) {
    standalone.data = parentSpec.data;
  }

  // Inherit transform if sub-spec doesn't have its own
  if (!standalone.transform && parentSpec.transform) {
    standalone.transform = parentSpec.transform;
  }

  return standalone;
}

/**
 * Extracts individual charts from a composite Vega-Lite spec.
 * Returns an array of standalone specs with titles.
 * If the spec is not composite, returns the original spec in an array.
 */
export function extractIndividualCharts(spec: object): ExtractedChart[] {
  const vegaSpec = spec as VegaLiteSpec;
  const charts: ExtractedChart[] = [];

  // Handle horizontal concatenation
  if (vegaSpec.hconcat && vegaSpec.hconcat.length > 0) {
    vegaSpec.hconcat.forEach((subSpec, index) => {
      charts.push({
        spec: createStandaloneSpec(subSpec, vegaSpec),
        title: getSpecTitle(subSpec, index, 'Chart'),
      });
    });
    return charts;
  }

  // Handle vertical concatenation
  if (vegaSpec.vconcat && vegaSpec.vconcat.length > 0) {
    vegaSpec.vconcat.forEach((subSpec, index) => {
      charts.push({
        spec: createStandaloneSpec(subSpec, vegaSpec),
        title: getSpecTitle(subSpec, index, 'Chart'),
      });
    });
    return charts;
  }

  // Handle generic concatenation
  if (vegaSpec.concat && vegaSpec.concat.length > 0) {
    vegaSpec.concat.forEach((subSpec, index) => {
      charts.push({
        spec: createStandaloneSpec(subSpec, vegaSpec),
        title: getSpecTitle(subSpec, index, 'Chart'),
      });
    });
    return charts;
  }

  // Handle layers - each layer becomes a separate chart
  if (vegaSpec.layer && vegaSpec.layer.length > 1) {
    vegaSpec.layer.forEach((subSpec, index) => {
      charts.push({
        spec: createStandaloneSpec(subSpec, vegaSpec),
        title: getSpecTitle(subSpec, index, 'Layer'),
      });
    });
    return charts;
  }

  // Not composite - return as single chart
  const title = getSpecTitle(vegaSpec, 0, 'Chart');
  return [{ spec, title }];
}

/**
 * Counts the number of individual charts in a spec.
 */
export function countChartsInSpec(spec: object): number {
  const vegaSpec = spec as VegaLiteSpec;

  if (vegaSpec.hconcat) return vegaSpec.hconcat.length;
  if (vegaSpec.vconcat) return vegaSpec.vconcat.length;
  if (vegaSpec.concat) return vegaSpec.concat.length;
  if (vegaSpec.layer && vegaSpec.layer.length > 1) return vegaSpec.layer.length;

  return 1;
}
