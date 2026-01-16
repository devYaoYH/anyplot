/**
 * Tests for Settings component.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Settings } from './Settings';

// Mock the API module
vi.mock('../lib/api', () => ({
  getApiKey: vi.fn(),
  setApiKey: vi.fn(),
  clearApiKey: vi.fn(),
  checkConfigStatus: vi.fn(),
}));

import { getApiKey, setApiKey, clearApiKey, checkConfigStatus } from '../lib/api';

const mockGetApiKey = vi.mocked(getApiKey);
const mockSetApiKey = vi.mocked(setApiKey);
const mockClearApiKey = vi.mocked(clearApiKey);
const mockCheckConfigStatus = vi.mocked(checkConfigStatus);

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCheckConfigStatus.mockResolvedValue({ api_key_configured: false });
    mockGetApiKey.mockReturnValue(null);
  });

  it('renders settings button', () => {
    render(<Settings />);
    expect(screen.getByRole('button', { name: /settings|api key/i })).toBeInTheDocument();
  });

  it('opens settings panel when button is clicked', async () => {
    render(<Settings />);

    const button = screen.getByRole('button');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText('API Configuration')).toBeInTheDocument();
    });
  });

  it('shows server key status as not configured', async () => {
    mockCheckConfigStatus.mockResolvedValue({ api_key_configured: false });
    render(<Settings />);

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText(/Server API key:/)).toBeInTheDocument();
      expect(screen.getByText(/Not configured/)).toBeInTheDocument();
    });
  });

  it('shows server key status as configured', async () => {
    mockCheckConfigStatus.mockResolvedValue({ api_key_configured: true });
    render(<Settings />);

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText(/Configured/)).toBeInTheDocument();
    });
  });

  it('allows entering and saving an API key', async () => {
    render(<Settings />);

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByLabelText(/Anthropic API Key/i)).toBeInTheDocument();
    });

    const input = screen.getByLabelText(/Anthropic API Key/i);
    fireEvent.change(input, { target: { value: 'sk-ant-test-key' } });

    const saveButton = screen.getByRole('button', { name: /save/i });
    fireEvent.click(saveButton);

    expect(mockSetApiKey).toHaveBeenCalledWith('sk-ant-test-key');
  });

  it('shows clear button when local key is set', async () => {
    mockGetApiKey.mockReturnValue('sk-ant-existing');
    render(<Settings />);

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
    });
  });

  it('clears the API key when clear button is clicked', async () => {
    mockGetApiKey.mockReturnValue('sk-ant-existing');
    render(<Settings />);

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /clear/i }));

    expect(mockClearApiKey).toHaveBeenCalled();
  });

  it('calls onApiKeyChange when key is saved', async () => {
    const onApiKeyChange = vi.fn();
    render(<Settings onApiKeyChange={onApiKeyChange} />);

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByLabelText(/Anthropic API Key/i)).toBeInTheDocument();
    });

    const input = screen.getByLabelText(/Anthropic API Key/i);
    fireEvent.change(input, { target: { value: 'sk-ant-new-key' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    expect(onApiKeyChange).toHaveBeenCalled();
  });

  it('shows error when trying to save empty key', async () => {
    render(<Settings />);

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/Please enter an API key/i)).toBeInTheDocument();
    });
  });
});
