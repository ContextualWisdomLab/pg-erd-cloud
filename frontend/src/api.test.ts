import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import * as api from './api'
import { SnapshotDetailResponse } from './types'

// Mock environment variables to match what api.ts expects.
vi.mock('./types', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./types')>()
  return {
    ...actual,
    snapshotDetailFromResponse: vi.fn().mockImplementation((res) => ({ ...res, converted: true }))
  }
})

describe('api', () => {
  let fetchMock: any
  let localStorageMock: any

  beforeEach(() => {
    fetchMock = vi.fn()
    globalThis.fetch = fetchMock

    localStorageMock = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    }
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mockOkResponse = (data: any) => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => data
    })
  }

  const mockErrorResponse = (status: number) => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status
    })
  }

  describe('csrfToken logic (internal)', () => {
    it('throws if csrf token fetch fails', async () => {
      mockErrorResponse(500)
      await expect(api.createProject('test')).rejects.toThrow('csrfToken failed: 500')
    })

    it('throws if csrf token response is invalid', async () => {
      mockOkResponse({ not_a_token: 123 })
      await expect(api.createProject('test')).rejects.toThrow('csrfToken failed: invalid token response')
    })
  })

  describe('devHeaders', () => {
    it('includes X-Dev-User if present in localStorage', async () => {
      localStorageMock.getItem.mockReturnValue('test-dev-user')
      mockOkResponse({ subject: 'sub', display_name: 'dn', user_account_uuid: 'uuid' })

      await api.getMe()

      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/me'), expect.objectContaining({
        headers: { 'X-Dev-User': 'test-dev-user' }
      }))
    })

    it('does not include X-Dev-User if not in localStorage', async () => {
      localStorageMock.getItem.mockReturnValue(null)
      mockOkResponse({ subject: 'sub', display_name: 'dn', user_account_uuid: 'uuid' })

      await api.getMe()

      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/me'), expect.objectContaining({
        headers: {}
      }))
    })
  })

  describe('getMe', () => {
    it('returns user data on success', async () => {
      const expected = { subject: 'sub', display_name: 'dn', user_account_uuid: 'uuid' }
      mockOkResponse(expected)

      const result = await api.getMe()
      expect(result).toEqual(expected)
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/me'), expect.objectContaining({ credentials: 'include' }))
    })

    it('throws on error', async () => {
      mockErrorResponse(401)
      await expect(api.getMe()).rejects.toThrow('getMe failed: 401')
    })
  })

  describe('listProjects', () => {
    it('returns list of projects', async () => {
      const expected = [{ project_name: 'p1' }]
      mockOkResponse(expected)

      const result = await api.listProjects()
      expect(result).toEqual(expected)
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/projects'), expect.any(Object))
    })

    it('throws on error', async () => {
      mockErrorResponse(500)
      await expect(api.listProjects()).rejects.toThrow('listProjects failed: 500')
    })
  })

  describe('createProject', () => {
    it('posts to create a project with json and csrf headers', async () => {
      mockOkResponse({ csrf_token: 'token123' }) // csrf fetch
      const expected = { project_name: 'p1' }
      mockOkResponse(expected) // actual fetch

      const result = await api.createProject('p1')
      expect(result).toEqual(expected)

      expect(fetchMock).toHaveBeenCalledTimes(2)
      expect(fetchMock).toHaveBeenNthCalledWith(1, expect.stringContaining('/api/csrf-token'), expect.any(Object))
      expect(fetchMock).toHaveBeenNthCalledWith(2, expect.stringContaining('/api/projects'), expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': 'token123'
        },
        body: JSON.stringify({ project_name: 'p1' })
      }))
    })

    it('throws on error', async () => {
      mockOkResponse({ csrf_token: 'token123' }) // csrf fetch
      mockErrorResponse(400) // actual fetch
      await expect(api.createProject('p1')).rejects.toThrow('createProject failed: 400')
    })
  })

  describe('listConnections', () => {
    it('returns connections for a project', async () => {
      const expected = [{ conn_name: 'c1' }]
      mockOkResponse(expected)

      const result = await api.listConnections('proj1')
      expect(result).toEqual(expected)
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/connections/by-project/proj1'), expect.any(Object))
    })

    it('throws on error', async () => {
      mockErrorResponse(500)
      await expect(api.listConnections('proj1')).rejects.toThrow('listConnections failed: 500')
    })
  })

  describe('createConnection', () => {
    it('posts a new connection', async () => {
      mockOkResponse({ csrf_token: 'token123' })
      const expected = { conn_name: 'c1' }
      mockOkResponse(expected)

      const result = await api.createConnection('proj1', 'c1', 'db://test')
      expect(result).toEqual(expected)

      expect(fetchMock).toHaveBeenNthCalledWith(2, expect.stringContaining('/api/connections/by-project/proj1'), expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ conn_name: 'c1', dsn: 'db://test' })
      }))
    })

    it('throws on error', async () => {
      mockOkResponse({ csrf_token: 'token123' }) // csrf fetch
      mockErrorResponse(400) // actual fetch
      await expect(api.createConnection('proj1', 'c1', 'db://test')).rejects.toThrow('createConnection failed: 400')
    })
  })

  describe('listSnapshots', () => {
    it('returns snapshots for a project', async () => {
      const expected = [{ snapshot_uuid: 's1' }]
      mockOkResponse(expected)

      const result = await api.listSnapshots('proj1')
      expect(result).toEqual(expected)
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/snapshots/by-project/proj1'), expect.any(Object))
    })

    it('throws on error', async () => {
      mockErrorResponse(500)
      await expect(api.listSnapshots('proj1')).rejects.toThrow('listSnapshots failed: 500')
    })
  })

  describe('createSnapshot', () => {
    it('posts a new snapshot', async () => {
      mockOkResponse({ csrf_token: 'token123' })
      const expected = { snapshot_uuid: 's1' }
      mockOkResponse(expected)

      const result = await api.createSnapshot('proj1', 'conn1', 'schema_test')
      expect(result).toEqual(expected)

      expect(fetchMock).toHaveBeenNthCalledWith(2, expect.stringContaining('/api/snapshots/by-project/proj1'), expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ db_connection_uuid: 'conn1', schema_filter: 'schema_test' })
      }))
    })

    it('posts a new snapshot with null schema_filter if not provided', async () => {
      mockOkResponse({ csrf_token: 'token123' })
      const expected = { snapshot_uuid: 's1' }
      mockOkResponse(expected)

      const result = await api.createSnapshot('proj1', 'conn1')
      expect(result).toEqual(expected)

      expect(fetchMock).toHaveBeenNthCalledWith(2, expect.stringContaining('/api/snapshots/by-project/proj1'), expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ db_connection_uuid: 'conn1', schema_filter: null })
      }))
    })

    it('throws on error', async () => {
      mockOkResponse({ csrf_token: 'token123' }) // csrf fetch
      mockErrorResponse(400) // actual fetch
      await expect(api.createSnapshot('proj1', 'conn1')).rejects.toThrow('createSnapshot failed: 400')
    })
  })

  describe('getSnapshot', () => {
    it('gets a snapshot and transforms it', async () => {
      const mockResponse = { snapshot_uuid: 's1' }
      mockOkResponse(mockResponse)

      const result = await api.getSnapshot('snap1')
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/snapshots/snap1'), expect.any(Object))
      expect(result).toEqual({ snapshot_uuid: 's1', converted: true })
    })

    it('throws on error', async () => {
      mockErrorResponse(404)
      await expect(api.getSnapshot('snap1')).rejects.toThrow('getSnapshot failed: 404')
    })
  })
})
// Trigger CI retry
