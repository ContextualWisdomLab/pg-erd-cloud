
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
import App from '../../App';

vi.mock('../../api', () => ({
  getMe: vi.fn().mockResolvedValue({ subject: 'test-user', display_name: 'Test User' }),
  listProjects: vi.fn().mockResolvedValue([]),
  listConnections: vi.fn().mockResolvedValue([]),
  listSnapshots: vi.fn().mockResolvedValue([]),
  createShareLink: vi.fn(),
}));

afterEach(cleanup);

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
        expect(toolbarQueries.getByRole('button', { name: '테이블 추가' })).toHaveTextContent('+');
        expect(toolbarQueries.getByRole('button', { name: '업무 그룹' })).toHaveTextContent('◇');
        expect(toolbarQueries.getByRole('button', { name: '인덱스 카디널리티 계산' })).toHaveTextContent('#');
        expect(toolbarQueries.getByRole('button', { name: 'DDL 내보내기' })).toHaveTextContent('SQL');
        expect(toolbarQueries.getByRole('button', { name: '공유 및 내보내기' })).toHaveTextContent('↗');
        const exportButtons = toolbarQueries.getAllByRole('button', { name: '이미지/텍스트 내보내기 모달 열기' });
        expect(exportButtons).toHaveLength(3);
        expect(exportButtons[0]).toHaveTextContent('IMG');
        expect(exportButtons[1]).toHaveTextContent('UML');
        expect(exportButtons[2]).toHaveTextContent('{}');
    });
});
