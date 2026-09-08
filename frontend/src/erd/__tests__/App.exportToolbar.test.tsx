import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

import App from '../../App';
import { listConnections, listProjects, listSnapshots } from '../../api';

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

const CONCRETE_EXPORT_NAME = /DDL|SQL|SVG|PlantUML|Mermaid|DBML|Prisma|JSON|이미지|UML|IMG|텍스트 내보내기/i;

async function openEditorToolbar() {
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('button', { name: '편집기' }));
  const toolbar = await screen.findByRole('toolbar', { name: 'ERD 캔버스 도구' });
  return { user, toolbar, toolbarQueries: within(toolbar) };
}

describe('export toolbar chooser', () => {
  it('keeps a single share-and-export control that opens the chooser dialog', async () => {
    const { user, toolbarQueries } = await openEditorToolbar();

    const chooser = toolbarQueries.getByRole('button', { name: '공유 및 내보내기' });
    expect(chooser).toBeEnabled();
    expect(toolbarQueries.getAllByRole('button', { name: '공유 및 내보내기' })).toHaveLength(1);

    for (const button of toolbarQueries.getAllByRole('button')) {
      const accessibleName = button.getAttribute('aria-label') || button.textContent || '';
      expect(accessibleName).not.toMatch(CONCRETE_EXPORT_NAME);
    }

    expect(toolbarQueries.queryByRole('button', { name: 'DDL 내보내기' })).not.toBeInTheDocument();
    expect(
      toolbarQueries.queryByRole('button', { name: '이미지/텍스트 내보내기 모달 열기' }),
    ).not.toBeInTheDocument();
    expect(toolbarQueries.queryByRole('button', { name: /JSON/i })).not.toBeInTheDocument();

    await user.click(chooser);
    const dialog = await screen.findByRole('dialog', { name: '공유 및 내보내기' });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: /JSON/i })).not.toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'SQL DDL 복사' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: '공유 및 내보내기 닫기' }));
    expect(screen.queryByRole('dialog', { name: '공유 및 내보내기' })).not.toBeInTheDocument();

    chooser.focus();
    await user.keyboard('{Enter}');
    expect(await screen.findByRole('dialog', { name: '공유 및 내보내기' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '공유 및 내보내기 닫기' }));
    chooser.focus();
    await user.keyboard(' ');
    expect(await screen.findByRole('dialog', { name: '공유 및 내보내기' })).toBeInTheDocument();
  });

  it('disables the chooser when neither share nor diagram export is possible', async () => {
    vi.mocked(listProjects).mockResolvedValueOnce([]);
    vi.mocked(listConnections).mockResolvedValueOnce([]);
    vi.mocked(listSnapshots).mockResolvedValueOnce([]);

    const { toolbarQueries } = await openEditorToolbar();
    const chooser = toolbarQueries.getByRole('button', { name: '공유 및 내보내기' });
    expect(chooser).toBeDisabled();
    expect(chooser).toHaveAttribute('title', '공유할 프로젝트나 내보낼 테이블이 없습니다');
  });
});
