import {
  Background,
  MiniMap,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
  type NodeTypes,
  type ReactFlowInstance,
  useEdgesState,
  useNodesState,
  addEdge,
  type Connection as FlowConnection,
} from "@xyflow/react";
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import {
  getMe,
  createConnection,
  createProject,
  createSnapshot,
  getSnapshot,
  listConnections,
  listProjects,
  listSnapshots,
  setDevUserHeader,
} from "./api";
import TableNode from "./erd/TableNode";
import { snapshotToGraph, type TableNodeData } from "./erd/convert";
import {
  downloadText,
  exportDDL,
  exportDiagramSvg,
  exportPlantUml,
} from "./erd/export";
import { GRID_COLUMNS, GRID_X_GAP, GRID_Y_GAP } from "./erd/layoutConstants";
import type { Connection, Project, SnapshotDetail } from "./types";

export default function App() {
  const [devUser, setDevUser] = useState<string>("local");
  const [me, setMe] = useState<{
    subject: string;
    display_name: string | null;
  } | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectName, setProjectName] = useState("demo");
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    null,
  );

  const [connections, setConnections] = useState<Connection[]>([]);
  const [connName, setConnName] = useState("target-db");
  const [dsn, setDsn] = useState("");
  const [selectedConnId, setSelectedConnId] = useState<string | null>(null);
  const [schemaFilter, setSchemaFilter] = useState<string>("");

  const [snapshotId, setSnapshotId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<TableNodeData>>(
    [],
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const reactFlowRef = useRef<ReactFlowInstance<
    Node<TableNodeData>,
    Edge
  > | null>(null);
  const copyFeedbackTimeoutRef = useRef<number | null>(null);

  const [isLayouting, setIsLayouting] = useState(false);
  const [layoutMessage, setLayoutMessage] = useState<string>("");
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [exportDdlText, setExportDdlText] = useState("");
  const [isCopied, setIsCopied] = useState(false);

  const [editingEdge, setEditingEdge] = useState<Edge | null>(null);
  const [isAddTableModalOpen, setIsAddTableModalOpen] = useState(false);
  const [newTableName, setNewTableName] = useState("");
  const [relLabel, setRelLabel] = useState("");

  const [undoPositions, setUndoPositions] = useState<Map<
    string,
    { x: number; y: number }
  > | null>(null);

  const nodeTypes = useMemo<NodeTypes>(() => ({ tableNode: TableNode }), []);

  useEffect(() => {
    return () => {
      if (copyFeedbackTimeoutRef.current !== null) {
        window.clearTimeout(copyFeedbackTimeoutRef.current);
      }
    };
  }, []);

  const onConnect = useCallback(
    (params: FlowConnection) => {
      const newEdge: Edge = {
        ...params,
        id: `edge_${Date.now()}`,
        animated: false,
        label: "fk_new_relation",
      };
      // We could add it directly, but let's just add it then edit it.
      setEdges((eds) => addEdge(newEdge, eds));
      setEditingEdge(newEdge);
      setRelLabel(newEdge.label as string);
    },
    [setEdges],
  );

  useEffect(() => {
    setDevUserHeader(devUser);
    Promise.all([getMe(), listProjects()])
      .then(([m, p]) => {
        setMe({ subject: m.subject, display_name: m.display_name });
        setProjects(p);
        setSelectedProjectId(p[0]?.project_space_uuid || null);
      })
      .catch((e) => setError(String(e)));
  }, [devUser]);

  useEffect(() => {
    if (!selectedProjectId) return;
    listConnections(selectedProjectId)
      .then((c) => {
        setConnections(c);
        if (c[0]) setSelectedConnId(c[0].db_connection_uuid);
      })
      .catch((e) => setError(String(e)));
  }, [selectedProjectId]);

  useEffect(() => {
    if (!snapshotId) return;
    const timer = setInterval(() => {
      getSnapshot(snapshotId)
        .then((s) => {
          setSnapshot(s);
          if (s.status === "succeeded" || s.status === "failed" || s.status === "not_found") {
            clearInterval(timer);
          }
        })
        .catch((e) => setError(String(e)));
    }, 1000);
    return () => clearInterval(timer);
  }, [snapshotId]);

  const graph = useMemo(() => {
    return snapshot?.snapshot_json
      ? snapshotToGraph(snapshot.snapshot_json)
      : null;
  }, [snapshot?.snapshot_json]);
  const createProjectHint = projectName.trim() ? "" : "Enter project name";
  const createConnectionHint = !selectedProjectId
    ? "Select a project first"
    : !connName.trim() || !dsn.trim()
      ? "Enter connection name and DSN"
      : "";
  const createSnapshotHint =
    selectedProjectId && selectedConnId ? "" : "Select project and connection";

  useEffect(() => {
    if (!graph) {
      setNodes([]);
      setEdges([]);
      setUndoPositions(null);
      return;
    }

    setEdges(graph.edges);

    setNodes((prev) => {
      const prevPos = new Map(prev.map((n) => [n.id, n.position]));
      return graph.nodes.map((n) => {
        const position = prevPos.get(n.id);
        return position ? { ...n, position } : n;
      });
    });
  }, [graph, setEdges, setNodes]);

  function snapshotNodePositions(
    currentNodes: Array<Node<TableNodeData>>,
  ): Map<string, { x: number; y: number }> {
    const map = new Map<string, { x: number; y: number }>();
    for (const n of currentNodes)
      map.set(n.id, { x: n.position.x, y: n.position.y });
    return map;
  }

  function applyPositions(
    currentNodes: Array<Node<TableNodeData>>,
    positions: Map<string, { x: number; y: number }>,
  ): Array<Node<TableNodeData>> {
    return currentNodes.map((n) => {
      const p = positions.get(n.id);
      return p ? { ...n, position: { x: p.x, y: p.y } } : n;
    });
  }

  function computeSortedGridLayout(
    currentNodes: Array<Node<TableNodeData>>,
  ): Array<Node<TableNodeData>> {
    const sorted = [...currentNodes].sort((a, b) => {
      const aTitle = a.data?.title ?? a.id;
      const bTitle = b.data?.title ?? b.id;
      return aTitle.localeCompare(bTitle, "en");
    });

    return sorted.map((n, i) => ({
      ...n,
      position: {
        x: (i % GRID_COLUMNS) * GRID_X_GAP,
        y: Math.floor(i / GRID_COLUMNS) * GRID_Y_GAP,
      },
    }));
  }

  async function onAutoLayout() {
    if (nodes.length === 0 || isLayouting) return;
    setIsLayouting(true);
    setLayoutMessage("");

    // Capture current positions for a one-step undo.
    setUndoPositions(snapshotNodePositions(nodes));

    try {
      // Yield to the browser so the UI can reflect the loading state.
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => resolve()),
      );

      const next = computeSortedGridLayout(nodes);
      setNodes(next);

      requestAnimationFrame(() => {
        reactFlowRef.current?.fitView({ padding: 0.2, duration: 200 });
      });

      setLayoutMessage("정렬 완료");
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error("Auto-layout failed", error);
      }
      setLayoutMessage("정렬에 실패했습니다. 다시 시도해 주세요.");
    } finally {
      setIsLayouting(false);
    }
  }

  const onEdgeClick = useCallback((event: React.MouseEvent, edge: Edge) => {
    event.preventDefault();
    setEditingEdge(edge);
    setRelLabel((edge.label as string) || "");
  }, []);

  function onRelSubmit() {
    if (!editingEdge) return;
    setEdges((eds) =>
      eds.map((e) => {
        if (e.id === editingEdge.id) {
          return { ...e, label: relLabel.trim() };
        }
        return e;
      }),
    );
    setEditingEdge(null);
  }

  function onRelCancel() {
    setEditingEdge(null);
  }

  function onOpenExport() {
    const ddl = exportDDL(nodes, edges);
    setExportDdlText(ddl);
    setIsExportModalOpen(true);
  }

  function onCloseExport() {
    setIsExportModalOpen(false);
    setIsCopied(false);
    if (copyFeedbackTimeoutRef.current !== null) {
      window.clearTimeout(copyFeedbackTimeoutRef.current);
      copyFeedbackTimeoutRef.current = null;
    }
  }

  const onCopyExportDdl = useCallback(() => {
    navigator.clipboard.writeText(exportDdlText);
    setIsCopied(true);

    if (copyFeedbackTimeoutRef.current !== null) {
      window.clearTimeout(copyFeedbackTimeoutRef.current);
    }

    copyFeedbackTimeoutRef.current = window.setTimeout(() => {
      setIsCopied(false);
      copyFeedbackTimeoutRef.current = null;
    }, 2000);
  }, [exportDdlText]);

  function onDownloadSvg() {
    downloadText(
      "pg-erd-diagram.svg",
      exportDiagramSvg(nodes, edges, snapshot?.snapshot_json),
      "image/svg+xml",
    );
  }

  function onDownloadUml() {
    downloadText(
      "pg-erd-diagram.puml",
      exportPlantUml(nodes, edges, snapshot?.snapshot_json),
      "text/plain",
    );
  }

  function onRelDelete() {
    if (!editingEdge) return;
    setEdges((eds) => eds.filter((e) => e.id !== editingEdge.id));
    setEditingEdge(null);
  }

  function onOpenAddTable() {
    setNewTableName("");
    setIsAddTableModalOpen(true);
  }

  function onAddTableSubmit() {
    if (!newTableName.trim()) return;
    const newId = `new_table_${Date.now()}`;

    // Create a new node with a basic 'id' column
    const newNode: Node<TableNodeData> = {
      id: newId,
      type: "tableNode",
      position: { x: 100, y: 100 }, // Initial drop position
      data: {
        title: newTableName.trim(),
        columns: [
          {
            column_name: "id",
            data_type: "integer",
            is_not_null: true,
            is_pk: true,
          },
        ],
        badges: { pk: true, fk: false },
      },
    };

    setNodes((nds) => [...nds, newNode]);
    setIsAddTableModalOpen(false);
  }

  function onAddTableCancel() {
    setIsAddTableModalOpen(false);
  }

  function onUndoLayout() {
    if (!undoPositions || isLayouting) return;
    setNodes((prev) => applyPositions(prev, undoPositions));
    setUndoPositions(null);
    setLayoutMessage("되돌렸습니다");
  }

  async function onCreateProject() {
    setError(null);
    const p = await createProject(projectName);
    const next = [p, ...projects];
    setProjects(next);
    setSelectedProjectId(p.project_space_uuid);
  }

  async function onCreateConnection() {
    if (!selectedProjectId) return;
    setError(null);
    const c = await createConnection(selectedProjectId, connName, dsn);
    const next = [c, ...connections];
    setConnections(next);
    setSelectedConnId(c.db_connection_uuid);
  }

  async function onCreateSnapshot() {
    if (!selectedProjectId || !selectedConnId) return;
    setError(null);
    const s = await createSnapshot(
      selectedProjectId,
      selectedConnId,
      schemaFilter.trim() || undefined,
    );
    setSnapshotId(s.schema_snapshot_uuid);
    setSnapshot(null);
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
          <div style={{ fontSize: 12, color: "#4b5563" }}>
            Subject: <code>{me?.subject || "—"}</code>
          </div>
        </div>

        <div className="field">
          <label htmlFor="project-select">Project</label>
          <div className="row">
            <select
              id="project-select"
              value={selectedProjectId || ""}
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
            <input
              id="project-name"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
            />
            <button
              onClick={onCreateProject}
              disabled={!projectName.trim()}
              aria-describedby={
                createProjectHint ? "create-project-hint" : undefined
              }
            >
              Create
            </button>
          </div>
          {createProjectHint ? (
            <span id="create-project-hint" className="field-hint">
              {createProjectHint}
            </span>
          ) : null}
        </div>

        <hr />

        <div className="field">
          <label htmlFor="conn-select">Connection</label>
          <select
            id="conn-select"
            value={selectedConnId || ""}
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
          <input
            id="conn-name"
            value={connName}
            onChange={(e) => setConnName(e.target.value)}
            placeholder="name"
          />
          <input
            id="conn-dsn"
            type="password"
            value={dsn}
            onChange={(e) => setDsn(e.target.value)}
            placeholder="postgresql://..."
            aria-label="Connection DSN"
          />
          <button
            onClick={onCreateConnection}
            disabled={!selectedProjectId || !connName.trim() || !dsn.trim()}
            aria-describedby={
              createConnectionHint ? "create-connection-hint" : undefined
            }
          >
            Save connection
          </button>
          {createConnectionHint ? (
            <span id="create-connection-hint" className="field-hint">
              {createConnectionHint}
            </span>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="schema-filter">Schema filter (optional)</label>
          <input
            id="schema-filter"
            value={schemaFilter}
            onChange={(e) => setSchemaFilter(e.target.value)}
            placeholder="public"
          />
        </div>

        <button
          onClick={onCreateSnapshot}
          disabled={!selectedProjectId || !selectedConnId}
          aria-describedby={
            createSnapshotHint ? "create-snapshot-hint" : undefined
          }
        >
          Reverse engineer → snapshot
        </button>
        {createSnapshotHint ? (
          <span id="create-snapshot-hint" className="field-hint">
            {createSnapshotHint}
          </span>
        ) : null}

        <div style={{ marginTop: 12, fontSize: 13 }} aria-live="polite">
          Snapshot: {snapshot?.status || "—"}
          {snapshot?.error_message ? (
            <div className="error" role="alert">
              {String(snapshot.error_message)}
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
          <div
            className="canvasToolbar"
            role="toolbar"
            aria-label="ERD 캔버스 도구"
          >
            <button
              type="button"
              onClick={onAutoLayout}
              disabled={nodes.length === 0 || isLayouting}
              aria-label="ERD 자동 정렬"
              aria-busy={isLayouting}
              title={
                nodes.length === 0 ? "정렬할 항목이 없습니다" : "자동 정렬"
              }
            >
              {isLayouting ? "정렬 중…" : "정렬"}
            </button>
            <button
              type="button"
              onClick={onUndoLayout}
              disabled={!undoPositions || isLayouting}
              title="정렬 되돌리기"
              aria-label="정렬 되돌리기"
            >
              되돌리기
            </button>
            <button
              type="button"
              onClick={onOpenAddTable}
              title="테이블 추가"
              aria-label="테이블 추가"
            >
              테이블 추가
            </button>
            <button
              type="button"
              onClick={onOpenExport}
              disabled={nodes.length === 0}
              title={
                nodes.length === 0 ? "내보낼 테이블이 없습니다" : "DDL 내보내기"
              }
              aria-label="DDL 내보내기"
            >
              DDL
            </button>
            <button
              type="button"
              onClick={onDownloadSvg}
              disabled={nodes.length === 0}
              title={
                nodes.length === 0 ? "내보낼 테이블이 없습니다" : "SVG 내보내기"
              }
              aria-label="SVG 그림 내보내기"
            >
              SVG
            </button>
            <button
              type="button"
              onClick={onDownloadUml}
              disabled={nodes.length === 0}
              title={
                nodes.length === 0 ? "내보낼 테이블이 없습니다" : "UML 내보내기"
              }
              aria-label="PlantUML 내보내기"
            >
              UML
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
            onConnect={onConnect}
            onEdgeClick={onEdgeClick}
            nodeTypes={nodeTypes}
            fitView
            onInit={(instance) => {
              reactFlowRef.current = instance;
            }}
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>

          {isExportModalOpen && (
            <div
              className="modalOverlay"
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: "rgba(0,0,0,0.5)",
                zIndex: 100,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                className="modalContent"
                style={{
                  background: "#fff",
                  padding: 20,
                  borderRadius: 8,
                  width: 500,
                  maxWidth: "90%",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <h3>DDL 내보내기</h3>
                <textarea
                  readOnly
                  value={exportDdlText}
                  style={{
                    width: "100%",
                    height: 300,
                    fontFamily: "monospace",
                    fontSize: 12,
                    padding: 8,
                  }}
                />
                <div
                  className="row"
                  style={{ justifyContent: "flex-end", marginTop: 8 }}
                >
                  <button onClick={onCloseExport}>닫기</button>
                  <button
                    onClick={onCopyExportDdl}
                    style={{ background: "#034ea2", color: "#fff" }}
                    aria-live="polite"
                  >
                    {isCopied ? "복사 완료 ✓" : "복사하기"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {editingEdge && (
            <div
              className="modalOverlay"
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: "rgba(0,0,0,0.5)",
                zIndex: 100,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                className="modalContent"
                style={{
                  background: "#fff",
                  padding: 20,
                  borderRadius: 8,
                  width: 320,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <h3>관계 설정</h3>
                <div style={{ fontSize: 13, color: "#4b5563" }}>
                  From: {editingEdge.source} <br />
                  To: {editingEdge.target}
                </div>
                <div className="field">
                  <label htmlFor="rel-label">제약조건 이름 (Label)</label>
                  <input
                    id="rel-label"
                    value={relLabel}
                    onChange={(e) => setRelLabel(e.target.value)}
                    placeholder="fk_constraint_name"
                    autoFocus
                  />
                </div>
                <div
                  className="row"
                  style={{ justifyContent: "space-between", marginTop: 8 }}
                >
                  <button
                    onClick={onRelDelete}
                    style={{ color: "#b91c1c", borderColor: "#fca5a5" }}
                  >
                    삭제
                  </button>
                  <div className="row">
                    <button onClick={onRelCancel}>취소</button>
                    <button
                      onClick={onRelSubmit}
                      style={{ background: "#034ea2", color: "#fff" }}
                    >
                      저장
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {isAddTableModalOpen && (
            <div
              className="modalOverlay"
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: "rgba(0,0,0,0.5)",
                zIndex: 100,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                className="modalContent"
                style={{
                  background: "#fff",
                  padding: 20,
                  borderRadius: 8,
                  width: 300,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <h3>테이블 추가</h3>
                <div className="field">
                  <label htmlFor="new-table-name">테이블 이름</label>
                  <input
                    id="new-table-name"
                    value={newTableName}
                    onChange={(e) => setNewTableName(e.target.value)}
                    placeholder="users"
                    autoFocus
                  />
                </div>
                <div
                  className="row"
                  style={{ justifyContent: "flex-end", marginTop: 8 }}
                >
                  <button onClick={onAddTableCancel}>취소</button>
                  <button
                    onClick={onAddTableSubmit}
                    style={{ background: "#034ea2", color: "#fff" }}
                  >
                    저장
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
