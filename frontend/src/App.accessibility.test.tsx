import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import { getBillingSupportAccount, getMe } from './api';

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

vi.mock('./api', () => ({
  getMe: vi.fn().mockResolvedValue({
    subject: 'test-user',
    display_name: 'Test User',
    user_account_uuid: 'test-user-uuid',
    support_operator: false
  }),
  listProjects: vi.fn().mockResolvedValue([]),
  listConnections: vi.fn().mockResolvedValue([]),
  listSnapshots: vi.fn().mockResolvedValue([]),
  createProject: vi.fn(),
  createConnection: vi.fn(),
  createSnapshot: vi.fn(),
  createShareLink: vi.fn(),
  getBillingSupportAccount: vi.fn(),
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
    expect(nav.queryByRole('button', { name: '지원' })).not.toBeInTheDocument();

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

  it('shows read-only support diagnostics for support operators', async () => {
    const user = userEvent.setup();
    vi.mocked(getMe).mockResolvedValueOnce({
      subject: 'support-operator',
      display_name: 'Support Operator',
      user_account_uuid: 'support-user-uuid',
      support_operator: true,
    });
    vi.mocked(getBillingSupportAccount).mockResolvedValueOnce({
      subject: 'customer-owner',
      user_account_uuid: 'customer-user-uuid',
      account_status: 'active',
      license_mode: 'required',
      license_verifier: 'signed_token',
      billing_portal_url: 'https://billing.example.com',
      billing_support_url: 'https://support.example.com',
      account_reactivation_url: 'https://billing.example.com/reactivate',
      project_count: 2,
      seat_count: 5,
      connection_count: 3,
      snapshot_count: 8,
      share_link_count: 4,
      active_share_link_count: 1,
      billing_entitlement: {
        plan: 'enterprise',
        seat_count: 25,
        source_provider: 'stripe',
        source_provider_event_id: 'evt_1',
        source_event_type: 'subscription.updated',
        source_occurred_at: '2026-07-02T00:00:00Z',
      },
      llm_usage_current_month: {
        scope: 'account',
        month: '2026-07',
        request_count: 42,
        success_count: 39,
        failure_count: 3,
        quota_exceeded_count: 1,
        input_chars: 12345,
        output_chars: 6789,
      },
      recent_share_links: [
        {
          share_link_uuid: 'share-link-1',
          project_space_uuid: 'project-1',
          permission_kind: 'viewer',
          status: 'active',
          expires_at: '2026-07-09T00:00:00Z',
          created_at: '2026-07-02T00:00:00Z',
        },
      ],
      recent_billing_events: [
        {
          billing_event_uuid: 'event-1',
          provider: 'stripe',
          provider_event_id: 'evt_1',
          event_type: 'subscription.updated',
          target_plan: 'enterprise',
          status: 'recorded',
          occurred_at: '2026-07-02T00:00:00Z',
          received_at: '2026-07-02T01:00:00Z',
          metadata_summary: [
            { key: 'invoice_id', value: 'in_123' },
            { key: 'api_key', value: '[redacted]' },
          ],
        },
      ],
    });

    render(<App />);

    const navigation = await screen.findByRole('navigation', { name: '주요 화면' });
    await user.click(within(navigation).getByRole('button', { name: '지원' }));

    expect(
      await screen.findByRole('heading', { name: '지원 진단' }),
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: '지원 진단 대상 subject' }),
      'customer-owner',
    );
    await user.click(screen.getByRole('button', { name: '조회' }));

    expect(getBillingSupportAccount).toHaveBeenCalledWith('customer-owner');
    expect(await screen.findByText('customer-user-uuid')).toBeInTheDocument();
    expect(screen.getByText('서명 토큰')).toBeInTheDocument();
    expect(screen.getAllByText('enterprise')).not.toHaveLength(0);
    expect(screen.getByText('25')).toBeInTheDocument();
    expect(screen.getByText('stripe / subscription.updated')).toBeInTheDocument();
    const llmUsage = screen.getByLabelText('이번 달 LLM 사용량 지표');
    expect(within(llmUsage).getByText('2026-07')).toBeInTheDocument();
    expect(within(llmUsage).getByText('42')).toBeInTheDocument();
    expect(within(llmUsage).getByText('12,345 / 6,789')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '지원센터 열기' })).toHaveAttribute(
      'href',
      'https://support.example.com',
    );
    expect(screen.getByRole('link', { name: '결제 포털 열기' })).toHaveAttribute(
      'href',
      'https://billing.example.com',
    );
    expect(screen.getByRole('link', { name: '재활성화 열기' })).toHaveAttribute(
      'href',
      'https://billing.example.com/reactivate',
    );
    expect(screen.getByRole('table', { name: '최근 공유 링크' })).toBeInTheDocument();
    expect(screen.getByText('share-link-1')).toBeInTheDocument();
    expect(screen.getAllByText('활성')).not.toHaveLength(0);
    expect(screen.getByRole('table', { name: '최근 결제 이벤트' })).toBeInTheDocument();
    expect(screen.getByText('subscription.updated')).toBeInTheDocument();
    expect(screen.getByText(/invoice_id=in_123/)).toBeInTheDocument();
    expect(screen.getByText(/api_key=\[redacted\]/)).toBeInTheDocument();
  });
});
