/**
 * Unit tests for Layout component.
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Layout } from './Layout';

describe('Layout', () => {
  it('renders header with title', () => {
    render(<Layout><div>Content</div></Layout>);

    expect(screen.getByText('Sanctum')).toBeInTheDocument();
    expect(screen.getByText(/privacy-preserving/i)).toBeInTheDocument();
  });

  it('renders children in main area', () => {
    render(
      <Layout>
        <div data-testid="test-content">Test Content</div>
      </Layout>
    );

    expect(screen.getByTestId('test-content')).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });
});
