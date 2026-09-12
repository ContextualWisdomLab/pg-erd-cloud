import appSource from './App.tsx?raw';
import { describe, expect, it } from 'vitest';

describe('project access-management application wiring', () => {
  it('opens the real access-management surface from the export dialog', () => {
    expect(appSource).toContain('onOpenAccessManagement={');
    expect(appSource).toContain('<AccessManagementModal');
  });

  it('uses the selected project as the member API authority', () => {
    expect(appSource).toContain('const projectId = selectedProjectId;');
    expect(appSource).toContain('upsertProjectMember(projectId');
    expect(appSource).toContain('listProjectMembers(projectId');
    expect(appSource).toContain('accessRequestRef.current !== requestId');
  });
});
