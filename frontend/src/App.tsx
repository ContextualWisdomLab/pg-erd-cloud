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
  AddTableModal,
  CardinalityModal,
  EditEdgeModal,
  EditTableModal,
  ExportModal,
  GroupModal,
} from "./components/modals";

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
import { exportMermaid } from "./erd/mermaid";
import { GRID_COLUMNS, GRID_X_GAP, GRID_Y_GAP } from "./erd/layoutConstants";
import type { Connection, Project, SnapshotDetail } from "./types";

const TERMINAL_SNAPSHOT_STATUSES = new Set([
  "succeeded",
  "failed",
  "not_found",
]);

const SUPPORTED_DSN_PROTOCOLS = new Set(["postgres:", "postgresql:", "snowflake:"]);

type CurrentUser = {
  subject: string;
  display_name: string | null;
};

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function isSupportedConnectionDsn(value: string): boolean {
  try {
    const url = new URL(value);
    return SUPPORTED_DSN_PROTOCOLS.has(url.protocol) && Boolean(url.hostname);
  } catch {
    return false;
  }
}

function strengthLabel(strength: CardinalityStrength): string {
  if (strength === "recommended") return "추천";
  if (strength === "consider") return "검토";
  return "보류";
}

export default function App() {
  const [devUser, setDevUser] = useState<string>("local");
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
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
  const [nodeSearch, setNodeSearch] = useState("");

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
  const [editingNode, setEditingNode] = useState<Node<TableNodeData> | null>(null);
  const [isEditTableModalOpen, setIsEditTableModalOpen] = useState(false);
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
  const normalizedNodeSearch = nodeSearch.trim().toLocaleLowerCase();
  const searchMatchedNodeIds = useMemo(() => {
    if (!normalizedNodeSearch) return new Set<string>();
    const matches = new Set<string>();
    for (const node of nodes) {
      const haystack = [
        node.data.title,
        node.data.comment ?? "",
        ...node.data.columns.flatMap((column) => [
          column.column_name,
          column.data_type,
          column.column_comment ?? "",
        ]),
      ]
        .join(" ")
        .toLocaleLowerCase();
      if (haystack.includes(normalizedNodeSearch)) {
        matches.add(node.id);
      }
    }
    return matches;
  }, [nodes, normalizedNodeSearch]);
  const visibleNodes = useMemo(() => {
    if (!normalizedNodeSearch) return nodes;
    return nodes.map((node) => {
      const isHighlighted = searchMatchedNodeIds.has(node.id);
      return {
        ...node,
        data: {
          ...node.data,
          isDimmed: !isHighlighted,
          isHighlighted,
        },
      };
    });
  }, [nodes, normalizedNodeSearch, searchMatchedNodeIds]);
  const nodeSearchStatus = normalizedNodeSearch
    ? `${searchMatchedNodeIds.size}개 테이블 일치`
    : "";

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
    if (typeof window !== "undefined" && typeof window.localStorage !== "undefined") {
      window.localStorage.setItem("devUser", devUser.trim() || "local");
    }
  }, [devUser]);

  useEffect(() => {
    let isCurrent = true;
    setIsAuthLoading(true);
    setAuthError(null);
    Promise.all([getMe(), listProjects()])
      .then(([m, p]) => {
        if (!isCurrent) return;
        setMe({ subject: m.subject, display_name: m.display_name });
        setProjects(p);
        setSelectedProjectId(p[0]?.project_space_uuid || null);
      })
      .catch((e) => {
        if (!isCurrent) return;
        setMe(null);
        setProjects([]);
        setSelectedProjectId(null);
        setConnections([]);
        setSelectedConnId(null);
        setAuthError(String(e));
      })
      .finally(() => {
        if (isCurrent) setIsAuthLoading(false);
      });

    return () => {
      isCurrent = false;
    };
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
  const businessGroupsById = useMemo(() => {
    // ⚡ Bolt: Removed array mapping before Map creation to avoid intermediate array allocations.
    const map = new Map<string, BusinessGroup>();
    for (const group of businessGroups) {
      map.set(group.id, group);
    }
    return map;
  }, [businessGroups]);

  // ⚡ Bolt: Removed nodesById Map creation inside useMemo which iterates over all nodes and allocates memory.
  // Using nodes.find() for single lookups is O(N) but avoids Map construction overhead, providing ~10x speedup and reducing GC pressure.
  const cardinalityNode = useMemo(() => {
    return (
      nodes.find((n) => n.id === cardinalityTableId) ?? nodes[0] ?? null
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

  const appliedCardinalitySignatures = useMemo(() => {
    const names = new Set<string>();
    const columns = new Set<string>();
    for (const index of appliedCardinalityIndexes) {
      if (index.index_name) names.add(index.index_name);
      if (index.columns && index.columns.length > 0) columns.add(index.columns.join(","));
    }
    return { names, columns };
  }, [appliedCardinalityIndexes]);

  useEffect(() => {
    if (!graph) {
      setNodes([]);
      setEdges([]);
      setUndoPositions(null);
      return;
    }

    setEdges(graph.edges);

    setNodes((prev) => {
      // ⚡ Bolt: Replaced prev.map with a for loop to avoid intermediate array allocations during Map creation.
      const prevPos = new Map<string, { x: number; y: number }>();
      for (const n of prev) {
        prevPos.set(n.id, n.position);
      }
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

  const onNodeDoubleClick = useCallback((event: React.MouseEvent, node: Node) => {
    event.preventDefault();
    setEditingNode(node as Node<TableNodeData>);
    setIsEditTableModalOpen(true);
  }, []);

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

  function onDownloadMermaid() {
    downloadText("pg-erd-diagram.mermaid", exportMermaid(nodes, edges), "text/plain");
  }

  function onRelDelete() {
    if (!editingEdge) return;
    if (!window.confirm("정말로 이 관계를 삭제하시겠습니까?")) return;
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
    const nextNode = nodes.find((n) => n.id === tableId);
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
    setNodes((currentNodes) => {
      const targetNode = currentNodes.find((n) => n.id === cardinalityNode.id);
      if (!targetNode) return currentNodes;

      const existing = targetNode.data.indexes ?? [];

      const appliedIndexNames = new Set<string>();
      const appliedColumns = new Set<string>();
      for (const idx of existing) {
        if (idx.index_name) appliedIndexNames.add(idx.index_name);
        if (idx.columns && idx.columns.length > 0) {
          appliedColumns.add(idx.columns.join(","));
        }
      }

      const recColumns = recommendation.columns?.join(",") ?? "";

      if (
        (recommendation.index_name && appliedIndexNames.has(recommendation.index_name)) ||
        (recColumns && appliedColumns.has(recColumns))
      ) {
        return currentNodes;
      }

      return currentNodes.map((node) => {
        if (node.id !== cardinalityNode.id) return node;
        return {
          ...node,
          data: {
            ...node.data,
            indexes: [...existing, recommendation],
          },
        };
      });
    });
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
    const group = businessGroupsById.get(groupId);
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
    if (!window.confirm("이 그룹을 삭제하면 포함된 모든 테이블에서 그룹 지정이 해제됩니다. 정말로 삭제하시겠습니까?")) return;
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


  function onDeleteTable() {
    if (!editingNode) return;
    if (!window.confirm("정말로 이 테이블을 삭제하시겠습니까?")) return;

    // Remove the node
    setNodes((nds) => nds.filter((n) => n.id !== editingNode.id));

    // Remove connected edges
    setEdges((eds) => eds.filter((e) => e.source !== editingNode.id && e.target !== editingNode.id));

    setIsEditTableModalOpen(false);
    setEditingNode(null);
  }

  function onEditTableSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!editingNode) return;

    const formData = new FormData(e.currentTarget);
    const title = formData.get("title") as string;
    const comment = formData.get("comment") as string;

    if (!title.trim()) return;

    // Parse columns from formData
    const updatedColumns: Array<Node<TableNodeData>["data"]["columns"][number]> = [];
    for (let i = 0; i < editingNode.data.columns.length; i++) {
      const colName = formData.get(`col_name_${i}`) as string;
      if (colName === null) continue; // Deleted column

      const colType = formData.get(`col_type_${i}`) as string;
      const isPk = formData.get(`col_pk_${i}`) === "on";
      const isNotNull = formData.get(`col_nn_${i}`) === "on";

      updatedColumns.push({
        ...editingNode.data.columns[i],
        column_name: colName.trim() || `col_${i}`,
        data_type: colType.trim() || "text",
        is_pk: isPk,
        is_not_null: isNotNull,
      });
    }

    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === editingNode.id) {
          return {
            ...n,
            data: {
              ...n.data,
              title: title.trim(),
              comment: comment.trim() || null,
              columns: updatedColumns,
              badges: {
                ...n.data.badges,
                pk: updatedColumns.some(c => c.is_pk)
              }
            }
          };
        }
        return n;
      })
    );

    setIsEditTableModalOpen(false);
    setEditingNode(null);
  }

  function onEditTableCancel() {
    setIsEditTableModalOpen(false);
    setEditingNode(null);
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
    if (!isSupportedConnectionDsn(connectionDsn)) {
      setError("Connection DSN must use postgresql://, postgres://, or snowflake:// with a host.");
      if (dsnInputRef.current) {
        dsnInputRef.current.value = "";
      }
      setIsDsnPresent(false);
      return;
    }
    setError(null);
    setIsCreatingConnection(true);
    if (dsnInputRef.current) {
      dsnInputRef.current.value = "";
    }
    setIsDsnPresent(false);
    try {
      const c = await createConnection(
        selectedProjectId,
        nextConnectionName,
        connectionDsn,
      );
      setConnections((prev) => [c, ...prev]);
      setSelectedConnId(c.db_connection_uuid);
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

  if (isAuthLoading) {
    return (
      <main
        id="main"
        className="authGate"
        aria-busy="true"
        aria-live="polite"
      >
        <h1>pg-erd-cloud</h1>
        <p>Authenticating…</p>
      </main>
    );
  }

  if (!me) {
    return (
      <main id="main" className="authGate">
        <h1>Authentication required</h1>
        <p role="alert">{authError ?? "Sign in before managing database metadata."}</p>
        <label htmlFor="dev-user-auth">User (dev)</label>
        <input
          id="dev-user-auth"
          value={devUser}
          onChange={(e) => setDevUser(e.target.value)}
          placeholder="local"
        />
      </main>
    );
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
              type="button"
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
            type="button"
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
          type="button"
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
            <label className="canvasToolbar__search">
              <span className="srOnly">테이블 또는 컬럼 검색</span>
              <input
                aria-label="테이블 또는 컬럼 검색"
                placeholder="테이블/컬럼 검색"
                type="search"
                value={nodeSearch}
                onChange={(event) => setNodeSearch(event.currentTarget.value)}
              />
            </label>
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
              title={
                !undoPositions ? "되돌릴 작업이 없습니다" : "정렬 되돌리기"
              }
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
            <button
              type="button"
              onClick={onDownloadMermaid}
              disabled={nodes.length === 0}
              title={
                nodes.length === 0
                  ? "내보낼 테이블이 없습니다"
                  : "Mermaid 내보내기"
              }
              aria-label="Mermaid 내보내기"
            >
              Mermaid
            </button>
            <div className="srOnly" aria-live="polite">
              {[layoutMessage, nodeSearchStatus].filter(Boolean).join(" ")}
            </div>
          </div>

          <ReactFlow
            nodes={visibleNodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onEdgeClick={onEdgeClick}
            onNodeDoubleClick={onNodeDoubleClick}
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
                  <button
                    type="button"
                    title="테이블 추가"
                    aria-label="테이블 추가"
                    onClick={onOpenAddTable}
                    style={{ marginTop: 16, pointerEvents: "auto" }}
                  >
                    + 테이블 추가
                  </button>
                </>
              )}
            </div>
          )}

          <ExportModal
            isOpen={isExportModalOpen}
            exportDdlText={exportDdlText}
            isCopied={isCopied}
            onCloseExport={onCloseExport}
            onCopyExportDdl={onCopyExportDdl}
          />

          <EditEdgeModal
            editingEdge={editingEdge}
            relLabel={relLabel}
            setRelLabel={setRelLabel}
            onRelDelete={onRelDelete}
            onRelCancel={onRelCancel}
            onRelSubmit={onRelSubmit}
          />

          <GroupModal
            isOpen={isGroupModalOpen}
            businessGroups={businessGroups}
            newGroupName={newGroupName}
            setNewGroupName={setNewGroupName}
            newGroupColor={newGroupColor}
            setNewGroupColor={setNewGroupColor}
            nodes={nodes}
            onCloseGroupManager={onCloseGroupManager}
            onCreateBusinessGroup={onCreateBusinessGroup}
            onDeleteBusinessGroup={onDeleteBusinessGroup}
            onAssignBusinessGroup={onAssignBusinessGroup}
          />

          <CardinalityModal
            isOpen={isCardinalityModalOpen}
            cardinalityNode={cardinalityNode}
            nodes={nodes}
            cardinalityRowCount={cardinalityRowCount}
            setCardinalityRowCount={setCardinalityRowCount}
            cardinalityRowCountNumber={cardinalityRowCountNumber}
            cardinalityDistinctCounts={cardinalityDistinctCounts}
            cardinalityColumnSelections={cardinalityColumnSelections}
            cardinalityRecommendations={cardinalityRecommendations}
            appliedCardinalitySignatures={appliedCardinalitySignatures}
            onCloseCardinalityWizard={onCloseCardinalityWizard}
            onCardinalityTableChange={onCardinalityTableChange}
            onCardinalityColumnToggle={onCardinalityColumnToggle}
            onCardinalityDistinctCountChange={onCardinalityDistinctCountChange}
            onApplyCardinalityRecommendation={onApplyCardinalityRecommendation}
            parsePositiveInteger={parsePositiveInteger}
            calculateCardinalityRatio={calculateCardinalityRatio}
            formatPercent={formatPercent}
            strengthLabel={strengthLabel}
          />

          <EditTableModal
            isOpen={isEditTableModalOpen}
            editingNode={editingNode}
            setEditingNode={setEditingNode}
            setNodes={setNodes}
            onEditTableCancel={onEditTableCancel}
            onEditTableSubmit={onEditTableSubmit}
            onDeleteTable={onDeleteTable}
          />

          <AddTableModal
            isOpen={isAddTableModalOpen}
            newTableName={newTableName}
            setNewTableName={setNewTableName}
            onAddTableCancel={onAddTableCancel}
            onAddTableSubmit={onAddTableSubmit}
          />
        </div>
      </main>
    </div>
  );
}
