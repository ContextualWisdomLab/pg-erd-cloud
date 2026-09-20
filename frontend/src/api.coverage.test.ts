import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type ApiModule = typeof import('./api')

function response(payload: unknown, ok = true, status = ok ? 200 : 500): Response {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

async function loadApi(options?: { demo?: boolean; baseUrl?: string }): Promise<ApiModule> {
  vi.resetModules()
  vi.stubEnv('VITE_DEMO_MODE', options?.demo ? 'true' : 'false')
  vi.stubEnv('VITE_API_BASE_URL', options?.baseUrl ?? '')
  return import('./api')
}

describe('API client coverage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('covers successful credentialed reads and response conversion', async () => {
    const fetchMock = vi.mocked(fetch)
    const api = await loadApi()
    const project = { project_space_uuid: 'p1', project_name: 'Project' }
    const connection = { db_connection_uuid: 'c1', conn_name: 'DB' }
    const snapshot = { schema_snapshot_uuid: 's1', status: 'queued', schema_filter: null }

    fetchMock
      .mockResolvedValueOnce(response({ subject: 'u', display_name: null, user_account_uuid: 'a' }))
      .mockResolvedValueOnce(response([project]))
      .mockResolvedValueOnce(response([connection]))
      .mockResolvedValueOnce(response([snapshot]))
      .mockResolvedValueOnce(
        response({
          schema_snapshot_uuid: 's1',
          status: 'succeeded',
          schema_filter: null,
          error_message: null,
          snapshot_json: null,
        }),
      )
      .mockResolvedValueOnce(
        response({
          project_space_uuid: 'p1',
          permission_kind: 'viewer',
          snapshots: [],
        }),
      )
      .mockResolvedValueOnce(
        response({
          schema_snapshot_uuid: 's1',
          status: 'succeeded',
          schema_filter: null,
          error_message: null,
          snapshot_json: null,
        }),
      )

    await expect(api.getMe()).resolves.toEqual({
      subject: 'u',
      display_name: null,
      user_account_uuid: 'a',
    })
    await expect(api.listProjects()).resolves.toEqual([project])
    await expect(api.listConnections('p1')).resolves.toEqual([connection])
    await expect(api.listSnapshots('p1')).resolves.toEqual([snapshot])
    await expect(api.getSnapshot('s1')).resolves.toMatchObject({
      schema_snapshot_uuid: 's1',
      status: 'succeeded',
    })
    await expect(api.getSharedLinkInfo('share')).resolves.toMatchObject({
      permission_kind: 'viewer',
    })
    await expect(api.getSharedSnapshot('share', 's1')).resolves.toMatchObject({
      schema_snapshot_uuid: 's1',
    })
    expect(fetchMock).toHaveBeenCalledTimes(7)
  })

  it('encodes public-share path segments and normalizes snapshot diagnostics', async () => {
    const fetchMock = vi.mocked(fetch)
    const api = await loadApi({ baseUrl: 'https://api.example.test' })
    fetchMock
      .mockResolvedValueOnce(
        response({
          project_space_uuid: 'p1',
          permission_kind: 'viewer',
          snapshots: [],
        }),
      )
      .mockResolvedValueOnce(
        response({
          schema_snapshot_uuid: 'snapshot/one',
          status: 'failed',
          schema_filter: null,
          error_message: 'bad\u0000message',
          snapshot_json: null,
        }),
      )

    await expect(api.getSharedLinkInfo('team/blue')).resolves.toMatchObject({
      project_space_uuid: 'p1',
    })
    await expect(api.getSharedSnapshot('team/blue', 'snapshot/one')).resolves.toMatchObject({
      schema_snapshot_uuid: 'snapshot/one',
      error_message: 'bad message',
    })
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'https://api.example.test/api/share/team%2Fblue',
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'https://api.example.test/api/share/team%2Fblue/snapshots/snapshot%2Fone',
    )
  })

  it.each([
    ['getMe', (api: ApiModule) => api.getMe(), 'getMe failed: 401'],
    ['listProjects', (api: ApiModule) => api.listProjects(), 'listProjects failed: 401'],
    ['listConnections', (api: ApiModule) => api.listConnections('p'), 'listConnections failed: 401'],
    ['listSnapshots', (api: ApiModule) => api.listSnapshots('p'), 'listSnapshots failed: 401'],
    ['getSnapshot', (api: ApiModule) => api.getSnapshot('s'), 'getSnapshot failed: 401'],
    ['getSharedLinkInfo', (api: ApiModule) => api.getSharedLinkInfo('share'), 'getSharedLinkInfo failed: 401'],
    ['getSharedSnapshot', (api: ApiModule) => api.getSharedSnapshot('share', 's'), 'getSharedSnapshot failed: 401'],
  ])('reports %s read failures with the HTTP status', async (_name, invoke, message) => {
    vi.mocked(fetch).mockResolvedValue(response({}, false, 401))
    const api = await loadApi()
    await expect(invoke(api)).rejects.toThrow(message)
  })

  it('sends CSRF-protected project, connection, snapshot, and share writes', async () => {
    const fetchMock = vi.mocked(fetch)
    const api = await loadApi({ baseUrl: 'https://api.example.test' })
    const token = () => response({ csrf_token: 'csrf' })

    fetchMock
      .mockResolvedValueOnce(token())
      .mockResolvedValueOnce(response({ project_space_uuid: 'p', project_name: 'Name' }))
      .mockResolvedValueOnce(token())
      .mockResolvedValueOnce(response({ db_connection_uuid: 'c', conn_name: 'Conn' }))
      .mockResolvedValueOnce(token())
      .mockResolvedValueOnce(response({ schema_snapshot_uuid: 's', status: 'queued', schema_filter: null }))
      .mockResolvedValueOnce(token())
      .mockResolvedValueOnce(
        response({
          share_link_uuid: 'share',
          permission_kind: 'read',
          url_path: '/api/share/share',
        }),
      )

    await api.createProject('Name')
    await api.createConnection('p', 'Conn', 'postgres://secret')
    await api.createSnapshot('p', 'c', '')
    await expect(api.createShareLink('p')).resolves.toMatchObject({
      share_link_uuid: 'share',
      url: expect.stringContaining('/share/share'),
    })

    const writes = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(writes).toHaveLength(4)
    for (const [, init] of writes) {
      expect(init?.headers).toMatchObject({ 'X-CSRF-Token': 'csrf' })
      expect(init?.credentials).toBe('include')
    }
    expect(writes[2]?.[1]?.body).toBe(JSON.stringify({ db_connection_uuid: 'c', schema_filter: null }))
  })

  it('preserves a non-empty snapshot schema filter', async () => {
    const fetchMock = vi.mocked(fetch)
    const api = await loadApi()
    fetchMock
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockResolvedValueOnce(response({ schema_snapshot_uuid: 's', status: 'queued', schema_filter: 'sales' }))

    await api.createSnapshot('p', 'c', 'sales')
    expect(fetchMock.mock.calls[1]?.[1]?.body).toBe(
      JSON.stringify({ db_connection_uuid: 'c', schema_filter: 'sales' }),
    )
  })

  it.each([
    ['createProject', (api: ApiModule) => api.createProject('p'), 'createProject failed: 409'],
    [
      'createConnection',
      (api: ApiModule) => api.createConnection('p', 'c', 'postgres://dsn'),
      'createConnection failed: 409',
    ],
    ['createSnapshot', (api: ApiModule) => api.createSnapshot('p', 'c'), 'createSnapshot failed: 409'],
    ['createShareLink', (api: ApiModule) => api.createShareLink('p'), 'createShareLink failed: 409'],
  ])('reports %s write failures with the HTTP status', async (_name, invoke, message) => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
      .mockResolvedValueOnce(response({}, false, 409))
    const api = await loadApi()
    await expect(invoke(api)).rejects.toThrow(message)
  })

  it('fails closed for CSRF transport and token errors', async () => {
    const fetchMock = vi.mocked(fetch)
    const api = await loadApi()

    fetchMock.mockResolvedValueOnce(response({}, false, 503))
    await expect(api.createProject('p')).rejects.toThrow('csrfToken failed: 503')

    fetchMock.mockResolvedValueOnce(response({ csrf_token: '' }))
    await expect(api.createProject('p')).rejects.toThrow('csrfToken failed: invalid token response')

    fetchMock.mockResolvedValueOnce(response({ csrf_token: 123 }))
    await expect(api.createProject('p')).rejects.toThrow('csrfToken failed: invalid token response')
  })

  it('rejects insecure credential transport outside local development hosts', async () => {
    const api = await loadApi({ baseUrl: 'http://db.example.test' })
    await expect(api.createConnection('p', 'c', 'dsn')).rejects.toThrow(
      'createConnection requires HTTPS for credential transport',
    )
    expect(fetch).not.toHaveBeenCalled()
  })

  it.each(['http://localhost:8080', 'http://127.0.0.1:8080', 'http://[::1]:8080'])(
    'permits credential transport to local development host %s',
    async (baseUrl) => {
      const fetchMock = vi.mocked(fetch)
      fetchMock
        .mockResolvedValueOnce(response({ csrf_token: 'csrf' }))
        .mockResolvedValueOnce(response({ db_connection_uuid: 'c', conn_name: 'Conn' }))
      const api = await loadApi({ baseUrl })
      await expect(api.createConnection('p', 'Conn', 'dsn')).resolves.toMatchObject({
        db_connection_uuid: 'c',
      })
    },
  )

  it('exercises the complete in-memory demo workflow', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(42)
    const api = await loadApi({ demo: true })

    await expect(api.getMe()).resolves.toEqual({
      subject: 'local',
      display_name: 'Local Designer',
      user_account_uuid: 'demo-user',
    })
    expect((await api.listProjects()).length).toBeGreaterThan(0)
    await expect(api.listConnections('missing')).resolves.toEqual([])
    await expect(api.listSnapshots('missing')).resolves.toEqual([])
    await api.createConnection('uninitialized-project', 'First DB', 'ignored')
    await api.createSnapshot('uninitialized-project', 'first-db')

    const project = await api.createProject('Demo')
    const connection = await api.createConnection(project.project_space_uuid, 'Demo DB', 'ignored')
    const snapshot = await api.createSnapshot(
      project.project_space_uuid,
      connection.db_connection_uuid,
      undefined,
    )
    expect((await api.listProjects())[0]).toEqual(project)
    expect(await api.listConnections(project.project_space_uuid)).toContainEqual(connection)
    expect(await api.listSnapshots(project.project_space_uuid)).toContainEqual(snapshot)
    await expect(api.getSnapshot(snapshot.schema_snapshot_uuid)).resolves.toMatchObject({
      status: 'succeeded',
      snapshot_json: { relations: expect.any(Array) },
    })
    const shareLink = await api.createShareLink(project.project_space_uuid)
    expect(shareLink).toMatchObject({
      permission_kind: 'read',
      url_path: `/api/share/demo-${project.project_space_uuid}`,
    })
    await expect(api.getSharedLinkInfo(shareLink.share_link_uuid)).resolves.toMatchObject({
      project_space_uuid: project.project_space_uuid,
    })
    await expect(api.getSharedLinkInfo('unlisted-project')).resolves.toEqual({
      project_space_uuid: 'unlisted-project',
      permission_kind: 'read',
      snapshots: [],
    })
    await expect(
      api.getSharedSnapshot(shareLink.share_link_uuid, snapshot.schema_snapshot_uuid),
    ).resolves.toMatchObject({ status: 'succeeded' })
  })

  it('resolves prefixed and direct public shares in demo mode', async () => {
    const api = await loadApi({ demo: true })

    await expect(api.getSharedLinkInfo('demo-demo-shopping')).resolves.toEqual({
      project_space_uuid: 'demo-shopping',
      permission_kind: 'read',
      snapshots: [
        {
          schema_snapshot_uuid: 'demo-shopping-snapshot',
          status: 'succeeded',
          schema_filter: 'public',
          created_at: '1970-01-01T00:00:00.000Z',
        },
      ],
    })
    await expect(api.getSharedLinkInfo('external-project')).resolves.toEqual({
      project_space_uuid: 'external-project',
      permission_kind: 'read',
      snapshots: [],
    })
    await expect(api.getSharedSnapshot('ignored-share', 'snapshot-direct')).resolves.toMatchObject({
      schema_snapshot_uuid: 'snapshot-direct',
      status: 'succeeded',
      snapshot_json: { relations: expect.any(Array) },
    })
    expect(fetch).not.toHaveBeenCalled()
  })

  it('validates share-link response paths', async () => {
    const api = await loadApi()
    expect(() => api.shareLinkUrlFromPath(null)).toThrow('invalid share URL path')
    expect(() => api.shareLinkUrlFromPath('/unrelated')).toThrow('invalid share URL path')
    expect(api.shareLinkUrlFromPath('/api/share/ok')).toContain('/share/ok')
  })
})
