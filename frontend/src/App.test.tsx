
import { describe, test, vi, beforeEach, expect } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
expect.extend(matchers);
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from './App';

vi.mock('./api', () => ({
  getMe: vi.fn().mockResolvedValue({ subject: 'test', display_name: 'Test User' }),
  listProjects: vi.fn().mockResolvedValue([{ project_space_uuid: '1', project_name: 'Test Project' }]),
  createProject: vi.fn(),
  listSnapshots: vi.fn().mockResolvedValue([]),
  createReverseSnapshot: vi.fn(),
  getSnapshotDetail: vi.fn(),
  createShareLink: vi.fn(),
  listConnections: vi.fn().mockResolvedValue([]),
}));


// mock resize observer
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

if (typeof globalThis.DOMMatrixReadOnly === 'undefined') {
  globalThis.DOMMatrixReadOnly = class DOMMatrixReadOnly {
    m22 = 1;
  } as any;
}

describe('App', () => {

  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
  });

  test('can render and interact with modals', async () => {
    render(<App />);

    // Add table
    await waitFor(() => {
       const btn = screen.getAllByRole('button', { name: '테이블 추가' })[0];
       expect(btn).not.toBeNull();
    });

    const addBtns = screen.getAllByRole('button', { name: '테이블 추가' });
    fireEvent.click(addBtns[0]);

    const titleInput = screen.getByLabelText('테이블 이름');
    fireEvent.change(titleInput, { target: { value: 'my_table' } });

    const saveBtns = screen.getAllByRole('button', { name: '저장' });
    fireEvent.click(saveBtns[saveBtns.length - 1]);

    // We can't easily click the node without a proper ReactFlow environment,
    // but we can check if it rendered the node inside ReactFlow.
    // The text 'my_table' will be somewhere in the DOM.
    await waitFor(() => {
       expect(screen.queryAllByText('my_table').length).toBeGreaterThan(0);
    });
  });
});
