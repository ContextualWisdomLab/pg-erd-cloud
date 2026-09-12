import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AccessManagementModal } from './AccessManagementModal';

const owner = {
  user_account_uuid: 'owner-1',
  member_subject: 'oidc|owner',
  project_role: 'owner' as const,
};
const editor = {
  user_account_uuid: 'editor-1',
  member_subject: 'oidc|editor',
  project_role: 'editor' as const,
};

const baseProps = {
  isOpen: true,
  projectName: '결제 데이터 모델',
  currentSubject: owner.member_subject,
  members: [owner, editor],
  isLoading: false,
  loadError: null,
  isSaving: false,
  saveError: null,
  onClose: vi.fn(),
  onSaveMember: vi.fn(async () => undefined),
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('AccessManagementModal', () => {
  it('renders a loading state without advertising mutation', () => {
    render(<AccessManagementModal {...baseProps} members={[]} isLoading />);

    expect(screen.getByRole('status')).toHaveTextContent('멤버를 불러오는 중입니다.');
    expect(screen.queryByRole('button', { name: '멤버 저장' })).not.toBeInTheDocument();
  });

  it('renders permission denied separately from bearer-share semantics', () => {
    render(
      <AccessManagementModal
        {...baseProps}
        members={[]}
        loadError={{ kind: 'permission', message: 'listProjectMembers failed: 403' }}
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('편집자 또는 소유자만');
    expect(screen.getByText(/링크를 가진 사람은 로그인 없이 공유 스냅샷을 읽을 수 있습니다/)).toBeInTheDocument();
  });

  it('lets an owner add or update only viewer/editor roles', async () => {
    const onSaveMember = vi.fn(async () => undefined);
    render(<AccessManagementModal {...baseProps} onSaveMember={onSaveMember} />);

    expect(screen.getByText(owner.member_subject)).toBeInTheDocument();
    expect(screen.getByText(editor.member_subject)).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'owner' })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('OIDC subject'), { target: { value: 'oidc|viewer' } });
    fireEvent.change(screen.getByLabelText('프로젝트 역할'), { target: { value: 'viewer' } });
    fireEvent.click(screen.getByRole('button', { name: '멤버 저장' }));

    await waitFor(() => expect(onSaveMember).toHaveBeenCalledWith('oidc|viewer', 'viewer'));
  });

  it('keeps editors read-only even though they can list members', () => {
    render(
      <AccessManagementModal
        {...baseProps}
        currentSubject={editor.member_subject}
      />,
    );

    expect(screen.getByText('멤버 역할 변경은 프로젝트 소유자만 할 수 있습니다.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '멤버 저장' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '역할 변경' })).not.toBeInTheDocument();
  });

  it('preloads a non-owner member when the owner chooses role change', () => {
    render(<AccessManagementModal {...baseProps} />);

    fireEvent.click(screen.getByRole('button', { name: '역할 변경' }));
    expect(screen.getByLabelText('OIDC subject')).toHaveValue(editor.member_subject);
    expect(screen.getByLabelText('프로젝트 역할')).toHaveValue('editor');
  });
});
