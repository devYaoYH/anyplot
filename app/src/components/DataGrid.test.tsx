/**
 * Unit tests for DataGrid component.
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { DataGrid } from './DataGrid';

describe('DataGrid', () => {
  it('renders empty state when no data', () => {
    render(<DataGrid columns={[]} data={[]} />);

    expect(screen.getByText(/no data to display/i)).toBeInTheDocument();
  });

  it('renders column headers', () => {
    const columns = ['Name', 'Age', 'City'];
    const data = [['Alice', 30, 'NYC']];

    render(<DataGrid columns={columns} data={data} />);

    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Age')).toBeInTheDocument();
    expect(screen.getByText('City')).toBeInTheDocument();
  });

  it('renders data rows', () => {
    const columns = ['Name', 'Age'];
    const data = [
      ['Alice', 30],
      ['Bob', 25],
    ];

    render(<DataGrid columns={columns} data={data} />);

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText('25')).toBeInTheDocument();
  });

  it('displays row count', () => {
    const columns = ['Value'];
    const data = [[1], [2], [3]];

    render(<DataGrid columns={columns} data={data} />);

    expect(screen.getByText(/3 rows/)).toBeInTheDocument();
  });

  it('handles NULL values', () => {
    const columns = ['Value'];
    const data = [[null]];

    render(<DataGrid columns={columns} data={data} />);

    expect(screen.getByText('NULL')).toBeInTheDocument();
  });

  it('formats floating point numbers', () => {
    const columns = ['Value'];
    const data = [[3.14159]];

    render(<DataGrid columns={columns} data={data} />);

    expect(screen.getByText('3.14')).toBeInTheDocument();
  });

  it('limits displayed rows with maxRows prop', () => {
    const columns = ['Value'];
    const data = Array.from({ length: 150 }, (_, i) => [i]);

    render(<DataGrid columns={columns} data={data} maxRows={100} />);

    expect(screen.getByText(/showing first 100/)).toBeInTheDocument();
  });
});
