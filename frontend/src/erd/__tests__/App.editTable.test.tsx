
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
    { schema_snapshot_uuid: 'snap-1', status: 'succeeded', schema_filter: 'billing' },
    { schema_snapshot_uuid: 'snap-2', status: 'failed', schema_filter: 'hr' },
  ]),
  createConnection: vi.fn(),
  createProject: vi.fn(),
  createSnapshot: vi.fn(),
  getSnapshot: vi.fn(),
  createShareLink: vi.fn(),
}));

describe('App edit functionality', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByText('pg-erd-cloud')).toBeInTheDocument();
  });

  it('renders compact visual labels while preserving toolbar accessible names', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole('button', { name: '편집기' }));

    const toolbar = await screen.findByRole('toolbar', { name: 'ERD 캔버스 도구' });
    expect(toolbar).toBeInTheDocument();

    const toolbarQueries = within(toolbar);
    expect(toolbarQueries.getByRole('button', { name: 'ERD 자동 정렬' })).toHaveTextContent('↔');
    expect(toolbarQueries.getByRole('button', { name: '정렬 되돌리기' })).toHaveTextContent('↶');
    expect(toolbarQueries.getByRole('button', { name: '관계 자동 추론' })).toHaveTextContent('🪄');
    expect(toolbarQueries.getByRole('button', { name: '모든 노드 지우기' })).toHaveTextContent('🗑️');
    expect(toolbarQueries.getByRole('button', { name: '테이블 추가' })).toHaveTextContent('+');
    expect(toolbarQueries.getByRole('button', { name: '업무 그룹' })).toHaveTextContent('◇');
    expect(toolbarQueries.getByRole('button', { name: '인덱스 카디널리티 계산' })).toHaveTextContent('#');
    expect(toolbarQueries.getByRole('button', { name: 'DDL 내보내기' })).toHaveTextContent('SQL');
    expect(toolbarQueries.getByRole('button', { name: '공유 및 내보내기' })).toHaveTextContent('↗');
    expect(toolbarQueries.getByRole('button', { name: 'SVG 그림 내보내기' })).toHaveTextContent('IMG');
    expect(toolbarQueries.getByRole('button', { name: 'PlantUML 내보내기' })).toHaveTextContent('UML');
    expect(toolbarQueries.getByRole('button', { name: 'Mermaid 내보내기' })).toHaveTextContent('{}');
  });

  it('filters the diagram list by search text', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole('button', { name: '다이어그램' }));
    await screen.findByText('ERD_billing_1');

    await user.type(screen.getByLabelText('다이어그램 검색'), 'hr');

    expect(screen.queryByText('ERD_billing_1')).not.toBeInTheDocument();
    expect(screen.getByText('ERD_hr_2')).toBeInTheDocument();
  });
});
