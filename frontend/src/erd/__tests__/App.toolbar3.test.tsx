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

describe('App toolbar functionality 3', () => {
  it('calls onAutoInferRelationships correctly when new edges are inferred', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole('button', { name: '편집기' }));

    const toolbar = await screen.findByRole('toolbar', { name: 'ERD 캔버스 도구' });
    expect(toolbar).toBeInTheDocument();

    // Add a table to enable the buttons
    const addTableButton = within(toolbar).getByRole('button', { name: '테이블 추가' });
    await user.click(addTableButton);

    // Save table
    const dialog = screen.getByRole('dialog', { name: '테이블 추가' });
    const input = within(dialog).getByLabelText('테이블 이름');
    await user.type(input, 'test_table');
    await user.click(within(dialog).getByRole('button', { name: '저장' }));

    // Mock inferRelationships to return edges
    vi.spyOn(autoInferModule, 'inferRelationships').mockReturnValue([
      { id: '1', source: 'a', target: 'b', data: { sourceColumns: ['a_id'], targetColumns: ['id'] } }
    ] as any);

    // Now mock a window.alert
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

    const inferButton = within(toolbar).getByRole('button', { name: '관계 자동 추론' });
    await user.click(inferButton);

    expect(alertSpy).toHaveBeenCalledWith("새롭게 1개의 관계가 추가되었습니다.");
  });

  it('calls onClearCanvas correctly and accepts', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole('button', { name: '편집기' }));

    const toolbar = await screen.findByRole('toolbar', { name: 'ERD 캔버스 도구' });
    expect(toolbar).toBeInTheDocument();

    // Add a table to enable the buttons
    const addTableButton = within(toolbar).getByRole('button', { name: '테이블 추가' });
    await user.click(addTableButton);

    // Save table
    const dialog = screen.getByRole('dialog', { name: '테이블 추가' });
    const input = within(dialog).getByLabelText('테이블 이름');
    await user.type(input, 'test_table');
    await user.click(within(dialog).getByRole('button', { name: '저장' }));

    // Now mock a window.confirm to return true
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);

    const clearButton = within(toolbar).getByRole('button', { name: '모든 노드 지우기' });
    await user.click(clearButton);

    expect(confirmSpy).toHaveBeenCalled();
  });
});
