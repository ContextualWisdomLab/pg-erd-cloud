import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const sourceDirectory = dirname(fileURLToPath(import.meta.url));
const appSource = readFileSync(resolve(sourceDirectory, 'App.tsx'), 'utf8');

describe('project access-management application wiring', () => {
  it('opens the real access-management surface from the export dialog', () => {
    expect(appSource).toContain('onOpenAccessManagement={');
    expect(appSource).toContain('<AccessManagementModal');
  });

  it('uses the selected project as the member API authority', () => {
    expect(appSource).toContain('listProjectMembers(selectedProjectId');
    expect(appSource).toContain('upsertProjectMember(selectedProjectId');
  });
});
