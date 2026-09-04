import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';

const api = vi.hoisted(() => ({
  getMe: vi.fn(),
  listProjects: vi.fn(),
  listConnections: vi.fn(),
  listSnapshots: vi.fn(),
  createProject: vi.fn(),
  createConnection: vi.fn(),
  createSnapshot: vi.fn(),
  getSnapshot: vi.fn(),
  createShareLink: vi.fn(),
}));

vi.mock('../../api', () => api);

import App from '../../App';

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

beforeEach(() => {
  vi.clearAllMocks();
  api.getMe.mockResolvedValue({ subject: 'test-user', display_name: 'Test User' });
  api.listProjects.mockResolvedValue([
    { project_space_uuid: 'project-1', project_name: 'Billing' },
  ]);
  api.listConnections.mockResolvedValue([]);
  api.listSnapshots.mockResolvedValue([]);
  api.createProject.mockResolvedValue({
    project_space_uuid: 'project-2',
    project_name: 'Keyboard project',
  });
  api.createConnection.mockResolvedValue({
    db_connection_uuid: 'connection-2',
    conn_name: 'Primary',
  });
});

afterEach(() => {
  cleanup();
});

async function openEditor() {
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('button', { name: '편집기' }));
  return user;
}

describe('editor native form submission', () => {
  it('creates a project exactly once when Enter submits the project-name input', async () => {
    const user = await openEditor();

    await user.type(screen.getByLabelText('New project'), '  Keyboard project  {Enter}');

    await waitFor(() => {
      expect(api.createProject).toHaveBeenCalledTimes(1);
      expect(api.createProject).toHaveBeenCalledWith('Keyboard project');
    });
  });

  it('creates a connection exactly once when Enter submits a valid DSN', async () => {
    const user = await openEditor();

    await user.type(screen.getByLabelText('New connection (DSN)'), 'Primary');
    await user.type(
      screen.getByLabelText('Connection DSN'),
      'postgresql://db.example/test{Enter}',
    );

    await waitFor(() => {
      expect(api.createConnection).toHaveBeenCalledTimes(1);
      expect(api.createConnection).toHaveBeenCalledWith(
        'project-1',
        'Primary',
        'postgresql://db.example/test',
      );
    });
  });

  it('blocks duplicate Enter submission while connection creation is in flight', async () => {
    let resolveConnection!: (value: { db_connection_uuid: string; conn_name: string }) => void;
    api.createConnection.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveConnection = resolve;
      }),
    );
    const user = await openEditor();

    await user.type(screen.getByLabelText('New connection (DSN)'), 'Primary');
    const dsn = screen.getByLabelText('Connection DSN');
    await user.type(dsn, 'postgresql://db.example/first{Enter}');
    await waitFor(() => expect(api.createConnection).toHaveBeenCalledTimes(1));

    await user.type(dsn, 'postgresql://db.example/second{Enter}');
    expect(api.createConnection).toHaveBeenCalledTimes(1);

    resolveConnection({ db_connection_uuid: 'connection-2', conn_name: 'Primary' });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save connection' })).not.toBeDisabled());
  });

  it('does not create resources when Enter submits an invalid form state', async () => {
    const user = await openEditor();

    await user.type(screen.getByLabelText('New project'), '{Enter}');
    await user.type(screen.getByLabelText('Connection DSN'), 'postgresql://db.example/test{Enter}');

    expect(api.createProject).not.toHaveBeenCalled();
    expect(api.createConnection).not.toHaveBeenCalled();
  });
});
