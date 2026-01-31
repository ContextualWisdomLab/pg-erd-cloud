import { Background, Controls, ReactFlow, type NodeTypes } from '@xyflow/react'
import { useEffect, useMemo, useState } from 'react'
import {
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

  const nodeTypes = useMemo<NodeTypes>(() => ({ tableNode: TableNode }), [])

  useEffect(() => {
    listProjects()
      .then((p) => {
        setProjects(p)
        if (p[0]) setSelectedProjectId(p[0].project_space_uuid)
      })
      .catch((e) => setError(String(e)))
  }, [])

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

  const graph = useMemo(() => {
    if (!snapshot?.snapshot_json) return { nodes: [], edges: [] }
    return snapshotToGraph(snapshot.snapshot_json)
  }, [snapshot])

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
        <ReactFlow nodes={graph.nodes} edges={graph.edges} nodeTypes={nodeTypes} fitView>
          <Background />
          <Controls />
        </ReactFlow>
      </main>
    </div>
  )
}
