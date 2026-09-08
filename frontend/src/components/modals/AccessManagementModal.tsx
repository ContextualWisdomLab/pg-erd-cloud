import { useEffect, useMemo, useState, type FormEvent } from 'react';

import type { MutableProjectMemberRole, ProjectMember } from '../../types';
import { useDialogAccessibility } from './useDialogAccessibility';

type AccessLoadError = {
  kind: 'permission' | 'error';
  message: string;
};

interface AccessManagementModalProps {
  isOpen: boolean;
  projectName: string;
  currentSubject: string;
  members: ProjectMember[];
  isLoading: boolean;
  loadError: AccessLoadError | null;
  isSaving: boolean;
  saveError: string | null;
  onClose: () => void;
  onSaveMember: (memberSubject: string, projectRole: MutableProjectMemberRole) => Promise<void>;
}

export function AccessManagementModal({
  isOpen,
  projectName,
  currentSubject,
  members,
  isLoading,
  loadError,
  isSaving,
  saveError,
  onClose,
  onSaveMember,
}: AccessManagementModalProps) {
  const dialogRef = useDialogAccessibility(isOpen, onClose);
  const [memberSubject, setMemberSubject] = useState('');
  const [projectRole, setProjectRole] = useState<MutableProjectMemberRole>('viewer');

  const currentMember = useMemo(
    () => members.find((member) => member.member_subject === currentSubject) ?? null,
    [currentSubject, members],
  );
  const canManageMembers = currentMember?.project_role === 'owner';

  useEffect(() => {
    if (!isOpen) {
      setMemberSubject('');
      setProjectRole('viewer');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const subject = memberSubject.trim();
    if (!subject || /\s/.test(subject) || isSaving) return;
    await onSaveMember(subject, projectRole);
  }

  function beginRoleUpdate(member: ProjectMember) {
    if (member.project_role === 'owner') return;
    setMemberSubject(member.member_subject);
    setProjectRole(member.project_role);
  }

  return (
    <div className="modalOverlay">
      <div
        className="modalContent accessManagement"
        role="dialog"
        aria-modal="true"
        aria-labelledby="access-management-title"
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="modalHeader">
          <div>
            <h3 id="access-management-title">접근 관리</h3>
            <p className="modalLead">
              {projectName} 프로젝트 멤버의 편집 권한을 관리합니다.
            </p>
          </div>
          <button type="button" aria-label="접근 관리 닫기" onClick={onClose}>
            X
          </button>
        </div>

        <p className="accessManagement__boundary">
          프로젝트 멤버십은 로그인한 사용자의 프로젝트 권한입니다. 이미 공유한 링크는 별도의 bearer 링크이며,
          링크를 가진 사람은 로그인 없이 공유 스냅샷을 읽을 수 있습니다.
        </p>

        {isLoading ? (
          <div className="accessManagement__state" role="status" aria-live="polite">
            멤버를 불러오는 중입니다.
          </div>
        ) : loadError ? (
          <div className="accessManagement__state accessManagement__state--error" role="alert">
            {loadError.kind === 'permission'
              ? '프로젝트 멤버 목록은 편집자 또는 소유자만 볼 수 있습니다.'
              : loadError.message}
          </div>
        ) : (
          <>
            <section aria-labelledby="project-members-title">
              <div className="accessManagement__sectionHeader">
                <h4 id="project-members-title">프로젝트 멤버</h4>
                <span>{members.length}명</span>
              </div>

              {members.length === 0 ? (
                <p className="accessManagement__state">등록된 멤버가 없습니다.</p>
              ) : (
                <ul className="accessManagement__members">
                  {members.map((member) => (
                    <li key={member.user_account_uuid}>
                      <div>
                        <strong className="accessManagement__subject">{member.member_subject}</strong>
                        <span>{member.project_role}</span>
                      </div>
                      {canManageMembers && member.project_role !== 'owner' ? (
                        <button type="button" onClick={() => beginRoleUpdate(member)}>
                          역할 변경
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {canManageMembers ? (
              <form className="accessManagement__form" onSubmit={handleSubmit}>
                <h4>멤버 추가 또는 역할 변경</h4>
                <label htmlFor="access-member-subject">OIDC subject</label>
                <input
                  id="access-member-subject"
                  value={memberSubject}
                  maxLength={128}
                  autoComplete="off"
                  onChange={(event) => setMemberSubject(event.target.value)}
                  aria-describedby="access-member-subject-hint"
                  required
                />
                <span id="access-member-subject-hint" className="field-hint">
                  공백 없는 OIDC subject를 입력합니다. 기존 멤버의 subject를 입력하면 역할을 갱신합니다.
                </span>

                <label htmlFor="access-member-role">프로젝트 역할</label>
                <select
                  id="access-member-role"
                  value={projectRole}
                  onChange={(event) => setProjectRole(event.target.value as MutableProjectMemberRole)}
                >
                  <option value="viewer">viewer</option>
                  <option value="editor">editor</option>
                </select>

                {saveError ? <p className="accessManagement__saveError" role="alert">{saveError}</p> : null}

                <div className="accessManagement__formActions">
                  <button
                    type="submit"
                    disabled={!memberSubject.trim() || /\s/.test(memberSubject) || isSaving}
                    aria-busy={isSaving}
                  >
                    {isSaving ? '저장 중...' : '멤버 저장'}
                  </button>
                </div>
              </form>
            ) : (
              <p className="accessManagement__state">
                멤버 역할 변경은 프로젝트 소유자만 할 수 있습니다.
              </p>
            )}
          </>
        )}

        <div className="exportModal__footer">
          <button type="button" onClick={onClose}>닫기</button>
        </div>
      </div>
    </div>
  );
}
