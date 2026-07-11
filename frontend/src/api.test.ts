import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import * as api from './api'
import { shareLinkUrlFromPath } from './api'

describe('shareLinkUrlFromPath', () => {
  it('builds an absolute share URL from the backend path', () => {
    const url = new URL(shareLinkUrlFromPath('/api/share/share-123'))
    expect(url.pathname).toBe('/api/share/share-123')
  })

  it('rejects missing or unrelated paths', () => {
    expect(() => shareLinkUrlFromPath(undefined as any)).toThrow('invalid share URL path')
    expect(() => shareLinkUrlFromPath('/api/projects/p/share-links')).toThrow(
      'invalid share URL path',
    )
  })
})

describe('api functions', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    // Mock csrf endpoint to succeed
    (global.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/csrf-token') {
        return Promise.resolve({ ok: true, json: async () => ({ csrf_token: 'fake_token' }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('getMe fetches user data', async () => {
    (global.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/me') return Promise.resolve({ ok: true, json: async () => ({ id: 1, email: 'test@example.com' }) });
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
    const res = await api.getMe();
    expect(res).toEqual({ id: 1, email: 'test@example.com' });
  });

  it('listProjects fetches projects', async () => {
    (global.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/projects') return Promise.resolve({ ok: true, json: async () => ([]) });
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
    const res = await api.listProjects();
    expect(res).toEqual([]);
  });

  it('listConnections fetches connections', async () => {
    (global.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/connections/by-project/proj_1') return Promise.resolve({ ok: true, json: async () => ([]) });
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
    const res = await api.listConnections('proj_1');
    expect(res).toEqual([]);
  });

  it('listSnapshots fetches snapshots', async () => {
    (global.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/snapshots/by-project/proj_1') return Promise.resolve({ ok: true, json: async () => ([]) });
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
    const res = await api.listSnapshots('proj_1');
    expect(res).toEqual([]);
  });
});
