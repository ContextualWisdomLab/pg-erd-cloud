import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

vi.mock('./api', () => ({
  getMe: vi.fn().mockResolvedValue({ subject: 'test-user', display_name: 'Test User' }),
  listProjects: vi.fn().mockResolvedValue([]),
  listConnections: vi.fn().mockResolvedValue([]),
  listSnapshots: vi.fn().mockResolvedValue([]),
  createProject: vi.fn(),
  createConnection: vi.fn(),
  createSnapshot: vi.fn(),
  createShareLink: vi.fn(),
  getSnapshot: vi.fn(),
}));

afterEach(cleanup);

describe('App accessibility smoke', () => {
  it('exposes navigation, skip link, main landmark, and editor toolbar names', async () => {
    const user = userEvent.setup();
    render(<App />);

    const navigation = await screen.findByRole('navigation', { name: '주요 화면' });
    const skipLink = screen.getByRole('link', { name: '본문 바로가기' });
    expect(skipLink).toHaveAttribute('href', '#main');
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main');

    const nav = within(navigation);
    expect(nav.getByRole('button', { name: '대시보드' })).toHaveAttribute(
      'aria-current',
      'page',
    );

    await user.click(nav.getByRole('button', { name: '편집기' }));

    const toolbar = await screen.findByRole('toolbar', { name: 'ERD 캔버스 도구' });
    const toolbarQueries = within(toolbar);
    expect(
      toolbarQueries.getByRole('searchbox', { name: '테이블 또는 컬럼 검색' }),
    ).toBeInTheDocument();
    expect(
      toolbarQueries.getByRole('button', { name: 'ERD 자동 정렬' }),
    ).toBeInTheDocument();
    expect(
      toolbarQueries.getByRole('button', { name: '공유 및 내보내기' }),
    ).toBeInTheDocument();
  });
});
