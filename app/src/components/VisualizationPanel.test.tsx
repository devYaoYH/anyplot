/**
 * Unit tests for VisualizationPanel component.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { VisualizationPanel } from './VisualizationPanel';

describe('VisualizationPanel', () => {
  const defaultProps = {
    onVisualize: vi.fn(),
    isLoading: false,
    imageBase64: null,
    code: null,
    error: null,
  };

  it('renders prompt textarea', () => {
    render(<VisualizationPanel {...defaultProps} />);

    expect(screen.getByPlaceholderText(/describe the visualization/i)).toBeInTheDocument();
  });

  it('renders generate button', () => {
    render(<VisualizationPanel {...defaultProps} />);

    expect(screen.getByRole('button', { name: /generate visualization/i })).toBeInTheDocument();
  });

  it('calls onVisualize when form submitted with prompt', () => {
    const onVisualize = vi.fn();
    render(<VisualizationPanel {...defaultProps} onVisualize={onVisualize} />);

    const textarea = screen.getByPlaceholderText(/describe the visualization/i);
    fireEvent.change(textarea, { target: { value: 'Create a bar chart' } });

    const button = screen.getByRole('button', { name: /generate visualization/i });
    fireEvent.click(button);

    expect(onVisualize).toHaveBeenCalledWith('Create a bar chart');
  });

  it('disables button when disabled prop is true', () => {
    render(<VisualizationPanel {...defaultProps} disabled={true} />);

    const button = screen.getByRole('button', { name: /generate visualization/i });
    expect(button).toBeDisabled();
  });

  it('shows loading state', () => {
    render(<VisualizationPanel {...defaultProps} isLoading={true} />);

    expect(screen.getByRole('button', { name: /generating/i })).toBeInTheDocument();
  });

  it('displays error message', () => {
    render(<VisualizationPanel {...defaultProps} error="Something went wrong" />);

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('displays generated image', () => {
    const imageBase64 = 'iVBORw0KGgoAAAANS';
    render(<VisualizationPanel {...defaultProps} imageBase64={imageBase64} />);

    const img = screen.getByAltText(/generated visualization/i);
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', `data:image/png;base64,${imageBase64}`);
  });

  it('shows code when Show Code is clicked', () => {
    const code = 'plt.plot([1, 2, 3])';
    render(<VisualizationPanel {...defaultProps} imageBase64="abc" code={code} />);

    // Code should be hidden initially
    expect(screen.queryByText(code)).not.toBeInTheDocument();

    // Click Show Code
    fireEvent.click(screen.getByText('Show Code'));

    // Code should now be visible
    expect(screen.getByText(code)).toBeInTheDocument();
  });
});
