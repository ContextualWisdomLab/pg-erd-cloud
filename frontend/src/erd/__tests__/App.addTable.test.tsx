import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
import App from '../../App';

afterEach(() => {
  cleanup();
});

vi.mock('../../api', () => ({
  getMe: vi.fn().mockResolvedValue({ subject: 'test-user', display_name: 'Test User' }),
  listProjects: vi.fn().mockResolvedValue([
    { project_space_uuid: 'project-1', project_name: 'Billing' },
  ]),
  listConnections: vi.fn().mockResolvedValue([]),
  listSnapshots: vi.fn().mockResolvedValue([
    { schema_snapshot_uuid: 'snap-1', status: 'succeeded', schema_filter: 'billing', snapshot_json: { relations: [], columns: [] } },
  ]),
  createConnection: vi.fn(),
  createProject: vi.fn(),
  createSnapshot: vi.fn(),
  getSnapshot: vi.fn().mockResolvedValue({ status: 'succeeded', snapshot_json: { relations: [], columns: [] } }),
  createShareLink: vi.fn(),
}));

describe('App add table duplicate logic', () => {
  it('alerts when adding a duplicate table name', async () => {
    const user = userEvent.setup();
    const alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {});

    render(<App />);

    // To properly initialize ReactFlow we just navigate to Editor
    await user.click(await screen.findByRole('button', { name: '편집기' }));

    // The "테이블 추가" button doesn't load until ReactFlow initializes and the state is valid.
    // However, App.editTable.test.tsx manages to just click "편집기" and find the button. Let's see what it does.
    // It doesn't have a snapshot selected, but it works?
    const toolbar = await screen.findByRole('toolbar', { name: 'ERD 캔버스 도구' });
    const addBtn = within(toolbar).getByRole('button', { name: '테이블 추가' });

    await user.click(addBtn);

    // Give it a name and save
    const titleInput = await screen.findByLabelText('테이블 이름');
    await user.clear(titleInput);
    await user.type(titleInput, 'users');

    const modal1 = screen.getByRole('dialog', { name: '테이블 추가' });
    const saveBtn1 = within(modal1).getByRole('button', { name: '저장' });
    await user.click(saveBtn1);

    expect(alertMock).not.toHaveBeenCalled();

    // Add again with duplicate name
    await user.click(within(toolbar).getByRole('button', { name: '테이블 추가' }));
    const titleInput2 = await screen.findByLabelText('테이블 이름');
    await user.clear(titleInput2);
    await user.type(titleInput2, 'users');

    const modal2 = screen.getByRole('dialog', { name: '테이블 추가' });
    const saveBtn2 = within(modal2).getByRole('button', { name: '저장' });
    await user.click(saveBtn2);

    expect(alertMock).toHaveBeenCalledWith('이미 존재하는 테이블 이름입니다.');

    alertMock.mockRestore();
  });
});
