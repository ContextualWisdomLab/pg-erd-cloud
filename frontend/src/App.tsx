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
} from "./api";
import TableNode from "./erd/TableNode";
import {
  BUSINESS_GROUP_COLORS,
  DEFAULT_BUSINESS_GROUP_COLOR,
  uniqueBusinessGroupId,
  type BusinessGroup,
} from "./erd/businessGroups";
import {
  buildIndexRecommendations,
  calculateCardinalityRatio,
  parsePositiveInteger,
  type CardinalityColumnInput,
  type CardinalityStrength,
  type IndexRecommendation,
} from "./erd/cardinality";
import { snapshotToGraph, type TableNodeData } from "./erd/convert";
import {
  downloadText,
  exportDDL,
  exportDiagramSvg,
  exportPlantUml,
} from "./erd/export";
import { GRID_COLUMNS, GRID_X_GAP, GRID_Y_GAP } from "./erd/layoutConstants";
import type { Connection, Project, SnapshotDetail } from "./types";

const TERMINAL_SNAPSHOT_STATUSES = new Set([
  "succeeded",
  "failed",
  "not_found",
]);

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function strengthLabel(strength: CardinalityStrength): string {
  if (strength === "recommended") return "추천";
  if (strength === "consider") return "검토";
  return "보류";
}

function isSameIndexRecommendation(
  a: IndexRecommendation,
  b: IndexRecommendation,
): boolean {
  return (
    a.index_name === b.index_name ||
    (a.columns.length === b.columns.length &&
      a.columns.every((column, index) => column === b.columns[index]))
  );
}

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
  const [isDsnPresent, setIsDsnPresent] = useState(false);
  const [selectedConnId, setSelectedConnId] = useState<string | null>(null);
  const [schemaFilter, setSchemaFilter] = useState<string>("");

  const [snapshotId, setSnapshotId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [isCreatingConnection, setIsCreatingConnection] = useState(false);
  const [isCreatingSnapshot, setIsCreatingSnapshot] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<TableNodeData>>(
    [],
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const reactFlowRef = useRef<ReactFlowInstance<
    Node<TableNodeData>,
    Edge
  > | null>(null);
  const copyFeedbackTimeoutRef = useRef<number | null>(null);
  const dsnInputRef = useRef<HTMLInputElement | null>(null);

  const [isLayouting, setIsLayouting] = useState(false);
  const [layoutMessage, setLayoutMessage] = useState<string>("");
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [exportDdlText, setExportDdlText] = useState("");
  const [isCopied, setIsCopied] = useState(false);

  const [editingEdge, setEditingEdge] = useState<Edge | null>(null);
  const [isAddTableModalOpen, setIsAddTableModalOpen] = useState(false);
  const [newTableName, setNewTableName] = useState("");
  const [relLabel, setRelLabel] = useState("");
  const [isCardinalityModalOpen, setIsCardinalityModalOpen] = useState(false);
  const [cardinalityTableId, setCardinalityTableId] = useState("");
  const [cardinalityRowCount, setCardinalityRowCount] = useState("100000");
  const [cardinalityDistinctCounts, setCardinalityDistinctCounts] = useState<
    Record<string, string>
  >({});
  const [cardinalityColumnSelections, setCardinalityColumnSelections] =
    useState<Record<string, boolean>>({});
  const [businessGroups, setBusinessGroups] = useState<BusinessGroup[]>([]);
  const [isGroupModalOpen, setIsGroupModalOpen] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupColor, setNewGroupColor] = useState<string>(
    DEFAULT_BUSINESS_GROUP_COLOR,
  );

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
    : !connName.trim() || !isDsnPresent
      ? "Enter connection name and DSN"
      : "";
  const createSnapshotHint =
    selectedProjectId && selectedConnId ? "" : "Select project and connection";
  const isSnapshotPending =
    isCreatingSnapshot ||
    Boolean(snapshotId && !snapshot) ||
    Boolean(
      snapshot?.status && !TERMINAL_SNAPSHOT_STATUSES.has(snapshot.status),
    );
  const cardinalityRowCountNumber = useMemo(
    () => parsePositiveInteger(cardinalityRowCount),
    [cardinalityRowCount],
  );
  const cardinalityNode = useMemo(() => {
    return (
      nodes.find((node) => node.id === cardinalityTableId) ?? nodes[0] ?? null
    );
  }, [cardinalityTableId, nodes]);
  const cardinalityColumns = useMemo<CardinalityColumnInput[]>(() => {
    if (!cardinalityNode) return [];
    return cardinalityNode.data.columns.map((column) => ({
      columnName: column.column_name,
      isSelected: cardinalityColumnSelections[column.column_name] ?? false,
      distinctCount: parsePositiveInteger(
        cardinalityDistinctCounts[column.column_name] ?? "",
      ),
    }));
  }, [
    cardinalityColumnSelections,
    cardinalityDistinctCounts,
    cardinalityNode,
  ]);
  const cardinalityRecommendations = useMemo(
    () =>
      buildIndexRecommendations({
        tableName: cardinalityNode?.data.title ?? "",
        rowCount: cardinalityRowCountNumber,
        columns: cardinalityColumns,
      }),
    [cardinalityColumns, cardinalityNode?.data.title, cardinalityRowCountNumber],
  );
  const appliedCardinalityIndexes = useMemo(
    () => cardinalityNode?.data.indexes ?? [],
    [cardinalityNode?.data.indexes],
  );

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

  function initializeCardinalityInputs(node: Node<TableNodeData>) {
    const selections: Record<string, boolean> = {};
    const distinctCounts: Record<string, string> = {};
    for (const column of node.data.columns) {
      selections[column.column_name] = !column.is_pk;
      distinctCounts[column.column_name] = "";
    }
    setCardinalityColumnSelections(selections);
    setCardinalityDistinctCounts(distinctCounts);
  }

  function onOpenCardinalityWizard() {
    const firstNode = nodes[0];
    if (!firstNode) return;
    setCardinalityTableId(firstNode.id);
    setCardinalityRowCount("100000");
    initializeCardinalityInputs(firstNode);
    setIsCardinalityModalOpen(true);
  }

  function onCardinalityTableChange(tableId: string) {
    const nextNode = nodes.find((node) => node.id === tableId);
    if (!nextNode) return;
    setCardinalityTableId(tableId);
    initializeCardinalityInputs(nextNode);
  }

  function onCardinalityColumnToggle(columnName: string, isSelected: boolean) {
    setCardinalityColumnSelections((prev) => ({
      ...prev,
      [columnName]: isSelected,
    }));
  }

  function onCardinalityDistinctCountChange(
    columnName: string,
    value: string,
  ) {
    if (!/^\d*$/.test(value)) return;
    setCardinalityDistinctCounts((prev) => ({
      ...prev,
      [columnName]: value,
    }));
  }

  function onApplyCardinalityRecommendation(
    recommendation: IndexRecommendation,
  ) {
    if (!cardinalityNode || recommendation.strength === "skip") return;
    setNodes((currentNodes) =>
      currentNodes.map((node) => {
        if (node.id !== cardinalityNode.id) return node;
        const existing = node.data.indexes ?? [];
        if (
          existing.some((index) =>
            isSameIndexRecommendation(index, recommendation),
          )
        ) {
          return node;
        }
        return {
          ...node,
          data: {
            ...node.data,
            indexes: [...existing, recommendation],
          },
        };
      }),
    );
  }

  function onCloseCardinalityWizard() {
    setIsCardinalityModalOpen(false);
  }

  function onOpenGroupManager() {
    if (nodes.length === 0) return;
    setIsGroupModalOpen(true);
  }

  function onCloseGroupManager() {
    setIsGroupModalOpen(false);
  }

  function onCreateBusinessGroup() {
    const name = newGroupName.trim();
    if (!name) return;
    const nextGroup: BusinessGroup = {
      id: uniqueBusinessGroupId(name, businessGroups),
      name,
      color: newGroupColor,
    };
    setBusinessGroups((groups) => [...groups, nextGroup]);
    setNewGroupName("");
  }

  function onAssignBusinessGroup(nodeId: string, groupId: string) {
    const group = businessGroups.find((candidate) => candidate.id === groupId);
    setNodes((currentNodes) =>
      currentNodes.map((node) =>
        node.id === nodeId
          ? {
              ...node,
              data: {
                ...node.data,
                businessGroup: group ?? null,
              },
            }
          : node,
      ),
    );
  }

  function onDeleteBusinessGroup(groupId: string) {
    setBusinessGroups((groups) =>
      groups.filter((group) => group.id !== groupId),
    );
    setNodes((currentNodes) =>
      currentNodes.map((node) =>
        node.data.businessGroup?.id === groupId
          ? {
              ...node,
              data: {
                ...node.data,
                businessGroup: null,
              },
            }
          : node,
      ),
    );
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
    const nextProjectName = projectName.trim();
    if (!nextProjectName || isCreatingProject) return;
    setError(null);
    setIsCreatingProject(true);
    try {
      const p = await createProject(nextProjectName);
      setProjects((prev) => [p, ...prev]);
      setSelectedProjectId(p.project_space_uuid);
    } finally {
      setIsCreatingProject(false);
    }
  }

  async function onCreateConnection() {
    if (!selectedProjectId || isCreatingConnection) return;
    const nextConnectionName = connName.trim();
    const connectionDsn = dsnInputRef.current?.value.trim() ?? "";
    if (!nextConnectionName || !connectionDsn) return;
    setError(null);
    setIsCreatingConnection(true);
    try {
      const c = await createConnection(
        selectedProjectId,
        nextConnectionName,
        connectionDsn,
      );
      setConnections((prev) => [c, ...prev]);
      setSelectedConnId(c.db_connection_uuid);
      if (dsnInputRef.current) {
        dsnInputRef.current.value = "";
      }
      setIsDsnPresent(false);
    } finally {
      setIsCreatingConnection(false);
    }
  }

  async function onCreateSnapshot() {
    if (!selectedProjectId || !selectedConnId || isCreatingSnapshot) return;
    setError(null);
    setIsCreatingSnapshot(true);
    try {
      const s = await createSnapshot(
        selectedProjectId,
        selectedConnId,
        schemaFilter.trim() || undefined,
      );
      setSnapshotId(s.schema_snapshot_uuid);
      setSnapshot(null);
    } finally {
      setIsCreatingSnapshot(false);
    }
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
              disabled={!projectName.trim() || isCreatingProject}
              aria-busy={isCreatingProject}
              aria-describedby={
                createProjectHint ? "create-project-hint" : undefined
              }
            >
              {isCreatingProject ? "Creating…" : "Create"}
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
            ref={dsnInputRef}
            onChange={(e) =>
              setIsDsnPresent(Boolean(e.currentTarget.value.trim()))
            }
            placeholder="postgresql://... or snowflake://..."
            aria-label="Connection DSN"
          />
          <button
            onClick={onCreateConnection}
            disabled={
              !selectedProjectId ||
              !connName.trim() ||
              !isDsnPresent ||
              isCreatingConnection
            }
            aria-busy={isCreatingConnection}
            aria-describedby={
              createConnectionHint ? "create-connection-hint" : undefined
            }
          >
            {isCreatingConnection ? "Saving…" : "Save connection"}
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
          disabled={!selectedProjectId || !selectedConnId || isCreatingSnapshot}
          aria-busy={isCreatingSnapshot}
          aria-describedby={
            createSnapshotHint ? "create-snapshot-hint" : undefined
          }
        >
          {isCreatingSnapshot ? "Starting…" : "Reverse engineer → snapshot"}
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
              onClick={onOpenGroupManager}
              disabled={nodes.length === 0}
              title={
                nodes.length === 0 ? "묶을 테이블이 없습니다" : "업무 그룹"
              }
              aria-label="업무 그룹"
            >
              그룹
            </button>
            <button
              type="button"
              onClick={onOpenCardinalityWizard}
              disabled={nodes.length === 0}
              title={
                nodes.length === 0
                  ? "계산할 테이블이 없습니다"
                  : "인덱스 카디널리티 계산"
              }
              aria-label="인덱스 카디널리티 계산"
            >
              카디널리티
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

          {nodes.length === 0 && (
            <div className="emptyState" role="status" aria-live="polite">
              {isSnapshotPending ? (
                <>
                  <div
                    className="emptyState__mark emptyState__mark--busy"
                    aria-hidden="true"
                  />
                  <div className="emptyState__title">스냅샷 생성 중...</div>
                  <div className="emptyState__desc">
                    데이터베이스에서 스키마를 가져오고 있습니다. 잠시만 기다려주세요.
                  </div>
                </>
              ) : (
                <>
                  <div className="emptyState__mark" aria-hidden="true" />
                  <div className="emptyState__title">ERD 캔버스가 비어 있습니다</div>
                  <div className="emptyState__desc">
                    좌측 패널에서 스냅샷을 생성하거나 상단의 <b>테이블 추가</b> 버튼을 눌러 시작하세요.
                  </div>
                </>
              )}
            </div>
          )}

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

          {isGroupModalOpen && (
            <div className="modalOverlay">
              <div
                className="modalContent groupManager"
                role="dialog"
                aria-modal="true"
                aria-labelledby="group-manager-title"
              >
                <div className="modalHeader">
                  <h3 id="group-manager-title">업무 그룹</h3>
                  <button
                    type="button"
                    onClick={onCloseGroupManager}
                    aria-label="업무 그룹 닫기"
                  >
                    닫기
                  </button>
                </div>

                <div className="groupManager__create">
                  <div className="field">
                    <label htmlFor="business-group-name">그룹 이름</label>
                    <input
                      id="business-group-name"
                      value={newGroupName}
                      onChange={(event) => setNewGroupName(event.target.value)}
                      placeholder="Billing"
                    />
                  </div>
                  <div
                    className="groupManager__swatches"
                    role="radiogroup"
                    aria-label="그룹 색상"
                  >
                    {BUSINESS_GROUP_COLORS.map((color) => (
                      <button
                        type="button"
                        aria-label={`색상 ${color}`}
                        aria-pressed={newGroupColor === color}
                        className="groupManager__swatch"
                        key={color}
                        onClick={() => setNewGroupColor(color)}
                        style={{ background: color }}
                      />
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={onCreateBusinessGroup}
                    disabled={!newGroupName.trim()}
                  >
                    추가
                  </button>
                </div>

                <div className="groupManager__section">
                  <h4>그룹</h4>
                  {businessGroups.length === 0 ? (
                    <div className="field-hint">등록된 그룹이 없습니다.</div>
                  ) : (
                    <div className="groupManager__list">
                      {businessGroups.map((group) => (
                        <div className="groupManager__group" key={group.id}>
                          <span
                            className="groupManager__dot"
                            style={{ background: group.color }}
                          />
                          <strong>{group.name}</strong>
                          <button
                            type="button"
                            onClick={() => onDeleteBusinessGroup(group.id)}
                          >
                            삭제
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="groupManager__section">
                  <h4>테이블 배정</h4>
                  <div className="groupManager__assignments">
                    {nodes.map((node) => (
                      <label className="groupManager__assignment" key={node.id}>
                        <span>{node.data.title}</span>
                        <select
                          value={node.data.businessGroup?.id ?? ""}
                          onChange={(event) =>
                            onAssignBusinessGroup(node.id, event.target.value)
                          }
                        >
                          <option value="">없음</option>
                          {businessGroups.map((group) => (
                            <option key={group.id} value={group.id}>
                              {group.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {isCardinalityModalOpen && cardinalityNode && (
            <div className="modalOverlay">
              <div
                className="modalContent cardinalityWizard"
                role="dialog"
                aria-modal="true"
                aria-labelledby="cardinality-title"
              >
                <div className="modalHeader">
                  <h3 id="cardinality-title">인덱스 카디널리티</h3>
                  <button
                    type="button"
                    onClick={onCloseCardinalityWizard}
                    aria-label="카디널리티 계산 닫기"
                  >
                    닫기
                  </button>
                </div>

                <div className="cardinalityWizard__controls">
                  <div className="field">
                    <label htmlFor="cardinality-table">테이블</label>
                    <select
                      id="cardinality-table"
                      value={cardinalityNode.id}
                      onChange={(event) =>
                        onCardinalityTableChange(event.target.value)
                      }
                    >
                      {nodes.map((node) => (
                        <option key={node.id} value={node.id}>
                          {node.data.title}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="cardinality-row-count">행 수</label>
                    <input
                      id="cardinality-row-count"
                      inputMode="numeric"
                      min="1"
                      type="number"
                      value={cardinalityRowCount}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (/^\d*$/.test(value)) {
                          setCardinalityRowCount(value);
                        }
                      }}
                    />
                  </div>
                </div>

                <div className="cardinalityWizard__columns">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">사용</th>
                        <th scope="col">컬럼</th>
                        <th scope="col">Distinct</th>
                        <th scope="col">비율</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cardinalityNode.data.columns.map((column, index) => {
                        const distinctCount = parsePositiveInteger(
                          cardinalityDistinctCounts[column.column_name] ?? "",
                        );
                        const ratio =
                          cardinalityRowCountNumber !== null &&
                          distinctCount !== null
                            ? calculateCardinalityRatio(
                                cardinalityRowCountNumber,
                                distinctCount,
                              )
                            : null;
                        const inputId = `cardinality-${index}`;
                        return (
                          <tr key={column.column_name}>
                            <td>
                              <input
                                aria-label={`${column.column_name} 사용`}
                                checked={
                                  cardinalityColumnSelections[
                                    column.column_name
                                  ] ?? false
                                }
                                onChange={(event) =>
                                  onCardinalityColumnToggle(
                                    column.column_name,
                                    event.target.checked,
                                  )
                                }
                                type="checkbox"
                              />
                            </td>
                            <td>
                              <span className="cardinalityWizard__columnIdentity">
                                <label htmlFor={inputId}>
                                  {column.column_name}
                                </label>
                                <span>{column.data_type}</span>
                              </span>
                            </td>
                            <td>
                              <input
                                id={inputId}
                                inputMode="numeric"
                                min="1"
                                type="number"
                                value={
                                  cardinalityDistinctCounts[
                                    column.column_name
                                  ] ?? ""
                                }
                                onChange={(event) =>
                                  onCardinalityDistinctCountChange(
                                    column.column_name,
                                    event.target.value,
                                  )
                                }
                              />
                            </td>
                            <td>{ratio === null ? "—" : formatPercent(ratio)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="cardinalityWizard__recommendations">
                  <h4>추천 결과</h4>
                  {cardinalityRowCountNumber === null ? (
                    <div className="field-hint">Rows 값을 입력하세요.</div>
                  ) : null}
                  {cardinalityRowCountNumber !== null &&
                  cardinalityRecommendations.length === 0 ? (
                    <div className="field-hint">
                      사용할 컬럼과 distinct 값을 선택하세요.
                    </div>
                  ) : null}
                  {cardinalityRecommendations.map((recommendation) => {
                    const isApplied = appliedCardinalityIndexes.some((index) =>
                      isSameIndexRecommendation(index, recommendation),
                    );
                    return (
                      <div
                        className={`cardinalityRecommendation cardinalityRecommendation--${recommendation.strength}`}
                        key={`${recommendation.index_name}-${recommendation.columns.join("-")}`}
                      >
                        <div>
                          <div className="cardinalityRecommendation__title">
                            <span>{strengthLabel(recommendation.strength)}</span>
                            <strong>{recommendation.index_name}</strong>
                          </div>
                          <div className="field-hint">
                            {recommendation.columns.join(", ")} ·{" "}
                            {formatPercent(recommendation.cardinality_ratio)} ·{" "}
                            {recommendation.reason}
                          </div>
                        </div>
                        <button
                          type="button"
                          disabled={
                            recommendation.strength === "skip" || isApplied
                          }
                          onClick={() =>
                            onApplyCardinalityRecommendation(recommendation)
                          }
                        >
                          {isApplied ? "적용됨" : "적용"}
                        </button>
                      </div>
                    );
                  })}
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
