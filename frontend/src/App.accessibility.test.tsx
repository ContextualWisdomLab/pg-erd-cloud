import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import { getMe } from './api';

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

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

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

  it('explains account deactivation with reactivation and support links', async () => {
    vi.mocked(getMe).mockRejectedValueOnce(
      Object.assign(new Error('getMe failed: 403'), {
        status: 403,
        accountStatus: 'deactivated',
        accountReactivationUrl: 'https://billing.example.com/reactivate',
        billingSupportUrl: 'https://support.example.com',
      }),
    );

    render(<App />);

    expect(
      await screen.findByRole('heading', {
        name: '계정이 비활성화되었습니다',
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('결제 또는 계약 상태');
    expect(screen.getByRole('link', { name: '계정 재활성화' })).toHaveAttribute(
      'href',
      'https://billing.example.com/reactivate',
    );
    expect(screen.getByRole('link', { name: '지원팀에 문의' })).toHaveAttribute(
      'href',
      'https://support.example.com',
    );
  });
});
