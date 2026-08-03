import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DiagramViewLayout } from './types'

type ApiModule = typeof import('./api')

function response(payload: unknown, ok = true, status = ok ? 200 : 500): Response {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

async function loadApi(demo = false): Promise<ApiModule> {
  vi.resetModules()
  vi.stubEnv('VITE_DEMO_MODE', demo ? 'true' : 'false')
  vi.stubEnv('VITE_API_BASE_URL', '')
  return import('./api')
}

const initialLayout: DiagramViewLayout = {
  positions: {
    '1': { x: 12, y: 24 },
    '2': { x: 420, y: 24 },
  },
  viewport: { x: 10, y: 20, zoom: 0.8 },
}

const updatedLayout: DiagramViewLayout = {
  positions: {
    '1': { x: 80, y: 40 },
    '2': { x: 520, y: 40 },
  },
  viewport: { x: 0, y: 0, zoom: 1 },
}

describe('saved diagram-view API client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('performs credentialed list and detail reads', async () => {
    const fetchMock = vi.mocked(fetch)
    const api = await loadApi()
    const summary = {
      diagram_view_uuid: 'view-1',
      name: 'Architecture review',
      created_at: '2026-08-03T00:00:00Z',
      updated_at: '2026-08-03T01:00:00Z',
    }
    fetchMock
      .mockResolvedValueOnce(response([summary]))
      .mockResolvedValueOnce(response({ ...summary, layout_json: initialLayout }))

    await expect(api.listDiagramViews('project-1')).resolves.toEqual([summary])
    await expect(api.getDiagramView('view-1')).resolves.toEqual({
      ...summary,
      layout_json: initialLayout,
    })

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/diagram-views/by-project/project-1',
      { credentials: 'include' },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/diagram-views/view-1', {
      credentials: 'include',
    })
  })

  it('sends CSRF-protected create, update, and delete requests', async () => {
    const fetchMock = vi.mocked(fetch)
    const api = await loadApi()
    const token = () => response({ csrf_token: 'csrf-token' })
    const created = {
      diagram_view_uuid: 'view-1',
      name: 'Architecture review',
      created_at: '2026-08-03T00:00:00Z',
      updated_at: '2026-08-03T00:00:00Z',
    }
    const updated = {
      ...created,
      name: 'Operations review',
      updated_at: '2026-08-03T01:00:00Z',
    }

    fetchMock
      .mockResolvedValueOnce(token())
      .mockResolvedValueOnce(response(created))
      .mockResolvedValueOnce(token())
      .mockResolvedValueOnce(response(updated))
      .mockResolvedValueOnce(token())
      .mockResolvedValueOnce(response({ ok: true }))

    await expect(
      api.createDiagramView('project-1', 'Architecture review', initialLayout),
    ).resolves.toEqual(created)
    await expect(
      api.updateDiagramView('view-1', 'Operations review', updatedLayout),
    ).resolves.toEqual(updated)
    await expect(api.deleteDiagramView('view-1')).resolves.toBeUndefined()

    const createCall = fetchMock.mock.calls[1]!
    expect(createCall[0]).toBe('/api/diagram-views/by-project/project-1')
    expect(createCall[1]).toMatchObject({
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': 'csrf-token',
      },
      body: JSON.stringify({
        name: 'Architecture review',
        layout_json: initialLayout,
      }),
    })

    const updateCall = fetchMock.mock.calls[3]!
    expect(updateCall[0]).toBe('/api/diagram-views/view-1')
    expect(updateCall[1]).toMatchObject({
      method: 'PUT',
      credentials: 'include',
      body: JSON.stringify({
        name: 'Operations review',
        layout_json: updatedLayout,
      }),
    })

    const deleteCall = fetchMock.mock.calls[5]!
    expect(deleteCall[0]).toBe('/api/diagram-views/view-1')
    expect(deleteCall[1]).toMatchObject({
      method: 'DELETE',
      credentials: 'include',
    })
  })

  it.each([
    [
      'listDiagramViews',
      (api: ApiModule) => api.listDiagramViews('project-1'),
      'listDiagramViews failed: 403',
      false,
    ],
    [
      'getDiagramView',
      (api: ApiModule) => api.getDiagramView('view-1'),
      'getDiagramView failed: 403',
      false,
    ],
    [
      'createDiagramView',
      (api: ApiModule) =>
        api.createDiagramView('project-1', 'Review', initialLayout),
      'createDiagramView failed: 403',
      true,
    ],
    [
      'updateDiagramView',
      (api: ApiModule) =>
        api.updateDiagramView('view-1', 'Review', updatedLayout),
      'updateDiagramView failed: 403',
      true,
    ],
    [
      'deleteDiagramView',
      (api: ApiModule) => api.deleteDiagramView('view-1'),
      'deleteDiagramView failed: 403',
      true,
    ],
  ])(
    'reports %s failures with the HTTP status',
    async (_name, invoke, expectedMessage, needsCsrf) => {
      const fetchMock = vi.mocked(fetch)
      if (needsCsrf) {
        fetchMock
          .mockResolvedValueOnce(response({ csrf_token: 'csrf-token' }))
          .mockResolvedValueOnce(response({}, false, 403))
      } else {
        fetchMock.mockResolvedValueOnce(response({}, false, 403))
      }
      const api = await loadApi()
      await expect(invoke(api)).rejects.toThrow(expectedMessage)
    },
  )

  it('supports complete in-memory saved-view CRUD in demo mode', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(42)
    const api = await loadApi(true)

    await expect(api.listDiagramViews('project-1')).resolves.toEqual([])
    const created = await api.createDiagramView(
      'project-1',
      'Architecture review',
      initialLayout,
    )
    expect(created.diagram_view_uuid).toBe('demo-view-42')
    await expect(api.listDiagramViews('project-1')).resolves.toEqual([created])
    await expect(api.getDiagramView(created.diagram_view_uuid)).resolves.toEqual({
      ...created,
      layout_json: initialLayout,
    })

    const updated = await api.updateDiagramView(
      created.diagram_view_uuid,
      'Operations review',
      updatedLayout,
    )
    expect(updated).toMatchObject({
      diagram_view_uuid: created.diagram_view_uuid,
      name: 'Operations review',
    })
    await expect(api.getDiagramView(created.diagram_view_uuid)).resolves.toEqual({
      ...updated,
      layout_json: updatedLayout,
    })

    await api.deleteDiagramView(created.diagram_view_uuid)
    await expect(api.listDiagramViews('project-1')).resolves.toEqual([])
    await expect(api.getDiagramView(created.diagram_view_uuid)).rejects.toThrow(
      'getDiagramView failed: 404',
    )
    await expect(
      api.updateDiagramView(created.diagram_view_uuid, 'Missing', updatedLayout),
    ).rejects.toThrow('updateDiagramView failed: 404')
    await expect(api.deleteDiagramView(created.diagram_view_uuid)).rejects.toThrow(
      'deleteDiagramView failed: 404',
    )
  })
})
