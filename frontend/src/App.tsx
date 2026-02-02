import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
  type NodeTypes,
  type ReactFlowInstance,
  useEdgesState,
  useNodesState
} from '@xyflow/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  getMe,
  createConnection,
  createProject,
  createSnapshot,
  getSnapshot,
  listConnections,
  listProjects,
  listSnapshots
} from './api'
import TableNode from './erd/TableNode'
import { snapshotToGraph } from './erd/convert'
import type { Connection, Project, SnapshotDetail } from './types'

export default function App() {
  const [devUser, setDevUser] = useState<string>(() => localStorage.getItem('devUser') || 'local')
  const [me, setMe] = useState<{ subject: string; display_name: string | null } | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [projectName, setProjectName] = useState('demo')
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)

  const [connections, setConnections] = useState<Connection[]>([])
  const [connName, setConnName] = useState('target-db')
  const [dsn, setDsn] = useState('postgresql://postgres:postgres@localhost:5432/postgres')
  const [selectedConnId, setSelectedConnId] = useState<string | null>(null)
  const [schemaFilter, setSchemaFilter] = useState<string>('')

  const [snapshotId, setSnapshotId] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<SnapshotDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const reactFlowRef = useRef<ReactFlowInstance | null>(null)

  const [isLayouting, setIsLayouting] = useState(false)
  const [layoutMessage, setLayoutMessage] = useState<string>('')
  const [undoPositions, setUndoPositions] = useState<Map<string, { x: number; y: number }> | null>(null)

  const nodeTypes = useMemo<NodeTypes>(() => ({ tableNode: TableNode }), [])

  useEffect(() => {
    localStorage.setItem('devUser', devUser)
    Promise.all([getMe(), listProjects()])
      .then(([m, p]) => {
        setMe({ subject: m.subject, display_name: m.display_name })
        setProjects(p)
        setSelectedProjectId(p[0]?.project_space_uuid || null)
      })
      .catch((e) => setError(String(e)))
  }, [devUser])

  useEffect(() => {
    if (!selectedProjectId) return
    listConnections(selectedProjectId)
      .then((c) => {
        setConnections(c)
        if (c[0]) setSelectedConnId(c[0].db_connection_uuid)
      })
      .catch((e) => setError(String(e)))
  }, [selectedProjectId])

  useEffect(() => {
    if (!snapshotId) return
    const timer = setInterval(() => {
      getSnapshot(snapshotId)
        .then((s) => setSnapshot(s))
        .catch((e) => setError(String(e)))
    }, 1000)
    return () => clearInterval(timer)
  }, [snapshotId])

  useEffect(() => {
    if (!snapshot?.snapshot_json) {
      setNodes([])
      setEdges([])
      setUndoPositions(null)
      return
    }

    const graph = snapshotToGraph(snapshot.snapshot_json)
    setEdges(graph.edges)

    setNodes((prev) => {
      const prevPos = new Map(prev.map((n) => [n.id, n.position]))
      return graph.nodes.map((n) => {
        const position = prevPos.get(n.id)
        return position ? { ...n, position } : n
      })
    })
  }, [snapshot?.snapshot_json, setEdges, setNodes])

  function snapshotNodePositions(currentNodes: Node[]): Map<string, { x: number; y: number }> {
    const map = new Map<string, { x: number; y: number }>()
    for (const n of currentNodes) map.set(n.id, { x: n.position.x, y: n.position.y })
    return map
  }

  function applyPositions(currentNodes: Node[], positions: Map<string, { x: number; y: number }>): Node[] {
    return currentNodes.map((n) => {
      const p = positions.get(n.id)
      return p ? { ...n, position: { x: p.x, y: p.y } } : n
    })
  }

  function computeSortedGridLayout(currentNodes: Node[]): Node[] {
    const columns = 4
    const xGap = 320
    const yGap = 220

    const sorted = [...currentNodes].sort((a, b) => {
      const aTitle = String((a.data as any)?.title ?? a.id)
      const bTitle = String((b.data as any)?.title ?? b.id)
      return aTitle.localeCompare(bTitle)
    })

    return sorted.map((n, i) => ({
      ...n,
      position: { x: (i % columns) * xGap, y: Math.floor(i / columns) * yGap }
    }))
  }

  async function onAutoLayout() {
    if (nodes.length === 0 || isLayouting) return
    setIsLayouting(true)
    setLayoutMessage('')

    // Capture current positions for a one-step undo.
    setUndoPositions(snapshotNodePositions(nodes))

    try {
      // Yield to the browser so the UI can reflect the loading state.
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))

      const next = computeSortedGridLayout(nodes)
      setNodes(next)

      requestAnimationFrame(() => {
        reactFlowRef.current?.fitView({ padding: 0.2, duration: 200 })
      })

      setLayoutMessage('정렬 완료')
    } catch {
      setLayoutMessage('정렬에 실패했습니다. 다시 시도해 주세요.')
    } finally {
      setIsLayouting(false)
    }
  }

  function onUndoLayout() {
    if (!undoPositions || isLayouting) return
    setNodes((prev) => applyPositions(prev, undoPositions))
    setUndoPositions(null)
    setLayoutMessage('되돌렸습니다')
  }

  async function onCreateProject() {
    setError(null)
    const p = await createProject(projectName)
    const next = [p, ...projects]
    setProjects(next)
    setSelectedProjectId(p.project_space_uuid)
  }

  async function onCreateConnection() {
    if (!selectedProjectId) return
    setError(null)
    const c = await createConnection(selectedProjectId, connName, dsn)
    const next = [c, ...connections]
    setConnections(next)
    setSelectedConnId(c.db_connection_uuid)
  }

  async function onCreateSnapshot() {
    if (!selectedProjectId || !selectedConnId) return
    setError(null)
    const s = await createSnapshot(selectedProjectId, selectedConnId, schemaFilter.trim() || undefined)
    setSnapshotId(s.schema_snapshot_uuid)
    setSnapshot(null)
  }

  return (
    <div className="layout">
      <a className="skip-link" href="#main">
        본문 바로가기
      </a>
      <aside className="sidebar">
        <h2>pg-erd-cloud</h2>

        <div className="field">
          <label htmlFor="dev-user">User (dev)</label>
          <input
            id="dev-user"
            value={devUser}
            onChange={(e) => setDevUser(e.target.value)}
            placeholder="local"
          />
          <div style={{ fontSize: 12, color: '#4b5563' }}>
            Subject: <code>{me?.subject || '—'}</code>
          </div>
        </div>

        <div className="field">
          <label htmlFor="project-select">Project</label>
          <div className="row">
            <select
              id="project-select"
              value={selectedProjectId || ''}
              onChange={(e) => setSelectedProjectId(e.target.value || null)}
              style={{ flex: 1, padding: 8 }}
            >
              <option value="" disabled>
                Select…
              </option>
              {projects.map((p) => (
                <option key={p.project_space_uuid} value={p.project_space_uuid}>
                  {p.project_name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="field">
          <label htmlFor="project-name">New project</label>
          <div className="row">
            <input id="project-name" value={projectName} onChange={(e) => setProjectName(e.target.value)} />
            <button onClick={onCreateProject}>Create</button>
          </div>
        </div>

        <hr />

        <div className="field">
          <label htmlFor="conn-select">Connection</label>
          <select
            id="conn-select"
            value={selectedConnId || ''}
            onChange={(e) => setSelectedConnId(e.target.value || null)}
            style={{ padding: 8 }}
          >
            <option value="" disabled>
              Select…
            </option>
            {connections.map((c) => (
              <option key={c.db_connection_uuid} value={c.db_connection_uuid}>
                {c.conn_name}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="conn-name">New connection (DSN)</label>
          <input id="conn-name" value={connName} onChange={(e) => setConnName(e.target.value)} placeholder="name" />
          <input id="conn-dsn" value={dsn} onChange={(e) => setDsn(e.target.value)} placeholder="postgresql://..." />
          <button onClick={onCreateConnection}>Save connection</button>
        </div>

        <div className="field">
          <label htmlFor="schema-filter">Schema filter (optional)</label>
          <input id="schema-filter" value={schemaFilter} onChange={(e) => setSchemaFilter(e.target.value)} placeholder="public" />
        </div>

        <button onClick={onCreateSnapshot}>Reverse engineer → snapshot</button>

        <div style={{ marginTop: 12, fontSize: 13 }} aria-live="polite">
          Snapshot: {snapshot?.status || '—'}
          {snapshot?.error_message ? (
            <div className="error" role="alert">
              {snapshot.error_message}
            </div>
          ) : null}
        </div>

        {error ? (
          <div className="error" role="alert" style={{ marginTop: 10 }}>
            {error}
          </div>
        ) : null}
      </aside>

      <main id="main" className="main" tabIndex={-1}>
        <div className="canvas">
          <div className="canvasToolbar" role="toolbar" aria-label="ERD 캔버스 도구">
            <button
              onClick={onAutoLayout}
              disabled={nodes.length === 0 || isLayouting}
              aria-label="ERD 자동 정렬"
              aria-busy={isLayouting}
              title={nodes.length === 0 ? '정렬할 항목이 없습니다' : '자동 정렬'}
            >
              {isLayouting ? '정렬 중…' : '정렬'}
            </button>
            <button onClick={onUndoLayout} disabled={!undoPositions || isLayouting} title="정렬 되돌리기">
              되돌리기
            </button>
            <div className="srOnly" aria-live="polite">
              {layoutMessage}
            </div>
          </div>

          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            onInit={(instance) => {
              reactFlowRef.current = instance
            }}
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
      </main>
    </div>
  )
}
