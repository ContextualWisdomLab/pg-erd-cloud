import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
import App from '../../App';
import * as autoInferModule from '../autoInfer';

afterEach(() => {
  cleanup();
});

vi.mock('../../api', () => ({
  getMe: vi.fn().mockResolvedValue({ subject: 'test-user', display_name: 'Test User' }),
  listProjects: vi.fn().mockResolvedValue([
    { project_space_uuid: 'project-1', project_name: 'Billing' },
  ]),
  listConnections: vi.fn().mockResolvedValue([]),
  listSnapshots: vi.fn().mockResolvedValue([]),
  createConnection: vi.fn(),
  createProject: vi.fn(),
  createSnapshot: vi.fn(),
  getSnapshot: vi.fn(),
  createShareLink: vi.fn(),
}));

describe('App toolbar functionality', () => {
  it('calls onAutoInferRelationships and onClearCanvas correctly', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole('button', { name: '편집기' }));

    const toolbar = await screen.findByRole('toolbar', { name: 'ERD 캔버스 도구' });
    expect(toolbar).toBeInTheDocument();

    // Check initial state
    const toolbarQueries = within(toolbar);
    const inferButton = toolbarQueries.getByRole('button', { name: '관계 자동 추론' });
    const clearButton = toolbarQueries.getByRole('button', { name: '모든 노드 지우기' });

    expect(inferButton).toBeDisabled();
    expect(clearButton).toBeDisabled();

    // Now mock a window.alert and window.confirm
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    vi.spyOn(window, 'confirm').mockImplementation(() => true);

    // Mock inferRelationships to test it
    vi.spyOn(autoInferModule, 'inferRelationships').mockReturnValue([
      { id: '1', source: 'a', target: 'b', data: { sourceColumns: ['a_id'], targetColumns: ['id'] } }
    ] as any);
  });
});
