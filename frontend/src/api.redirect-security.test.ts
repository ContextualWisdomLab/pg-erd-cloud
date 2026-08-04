import { afterEach, expect, it, vi } from 'vitest'

type ApiModule = typeof import('./api')

function response(payload: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

async function loadApi(): Promise<ApiModule> {
  vi.resetModules()
  vi.stubEnv('VITE_DEMO_MODE', 'false')
  vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test')
  return import('./api')
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

it('fails closed instead of forwarding database credentials through redirects', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(response({ csrf_token: 'csrf-token' }))
    .mockResolvedValueOnce(response({ db_connection_uuid: 'connection-uuid', conn_name: 'Warehouse' }))
  vi.stubGlobal('fetch', fetchMock)
  const api = await loadApi()
  const fixtureDsn = ['postgresql', '://', 'fixture-user', ':', 'fixture-password', '@db.example.test/app'].join('')

  await api.createConnection('project-uuid', 'Warehouse', fixtureDsn)

  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    'https://api.example.test/api/connections/by-project/project-uuid',
    expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      redirect: 'error',
    }),
  )
})
