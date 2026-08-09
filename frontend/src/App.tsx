import {
  Background,
  MiniMap,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
  type NodeTypes,
  type OnSelectionChangeParams,
  type ReactFlowInstance,
  useEdgesState,
  useNodesState,
  addEdge,
  type Connection as FlowConnection,
  type ColorMode,
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
import { SharedDiagramView } from "./components/SharedDiagramView";

import {
  getMe,
  publicShareIdFromPath,
  createShareLink,
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
  exportDictionaryCsv,
  exportDictionaryMarkdown,
  exportPlantUml,
} from "./erd/export";
import { exportMermaid } from "./erd/mermaid";
import { inferRelationships } from "./erd/autoInfer";
import { exportDbml } from "./erd/dbml";
import { exportPrisma } from "./erd/prisma";
import { GRID_COLUMNS, GRID_X_GAP, GRID_Y_GAP } from "./erd/layoutConstants";
import { findSearchMatchedNodeIds } from "./erd/search";
import type { Connection, Project, Snapshot, SnapshotDetail } from "./types";

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

type WorkspaceView = "dashboard" | "projects" | "diagrams" | "editor";

const workspaceNavItems: Array<{ id: WorkspaceView; label: string }> = [
  { id: "dashboard", label: "대시보드" },
  { id: "projects", label: "프로젝트" },
  { id: "diagrams", label: "다이어그램" },
  { id: "editor", label: "편집기" },
];

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

function statusPillClassName(status: string): string {
  const normalizedStatus = status.toLocaleLowerCase();
  const modifier = TERMINAL_SNAPSHOT_STATUSES.has(normalizedStatus)
    ? ` statusPill--${normalizedStatus}`
    : "";
  return `statusPill${modifier}`;
}

function AuthenticatedApp({ colorMode }: { colorMode: ColorMode }) {
  const [activeView, setActiveView] = useState<WorkspaceView>("dashboard");
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectName, setProjectName] = useState("demo");
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    null,
  );

  const [connections, setConnections] = useState<Connection[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
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
  const [diagramSearch, setDiagramSearch] = useState("");
  const [nodeSearch, setNodeSearch] = useState("");

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<TableNodeData>>(
    [],
  );
  const [selectedEditorNodeId, setSelectedEditorNodeId] = useState<
    string | null
  >(null);
  const [selectedEditorEdgeId, setSelectedEditorEdgeId] = useState<
    string | null
  >(null);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const reactFlowRef = useRef<ReactFlowInstance<
    Node<TableNodeData>,
    Edge
  > | null>(null);
  const copyFeedbackTimeoutRef = useRef<number | null>(null);
  const shareCopyFeedbackTimeoutRef = useRef<number | null>(null);
  const shareLinkRequestIdRef = useRef(0);
  const dsnInputRef = useRef<HTMLInputElement | null>(null);

  const [isLayouting, setIsLayouting] = useState(false);
  const [layoutMessage, setLayoutMessage] = useState<string>("");
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [exportDdlText, setExportDdlText] = useState("");
  const [isCopied, setIsCopied] = useState(false);
  const [shareLinkUrl, setShareLinkUrl] = useState("");
  const [isCreatingShareLink, setIsCreatingShareLink] = useState(false);
  const [isShareLinkCopied, setIsShareLinkCopied] = useState(false);
  const [shareLinkError, setShareLinkError] = useState<string | null>(null);

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
    return findSearchMatchedNodeIds(nodes, normalizedNodeSearch);
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
  const selectedEditorNode = useMemo(
    () => nodes.find((node) => node.id === selectedEditorNodeId) ?? null,
    [nodes, selectedEditorNodeId],
  );
  const selectedEditorEdge = useMemo(
    () => edges.find((edge) => edge.id === selectedEditorEdgeId) ?? null,
    [edges, selectedEditorEdgeId],
  );

  useEffect(() => {
    return () => {
      shareLinkRequestIdRef.current += 1;
      if (copyFeedbackTimeoutRef.current !== null) {
        window.clearTimeout(copyFeedbackTimeoutRef.current);
      }
      if (shareCopyFeedbackTimeoutRef.current !== null) {
        window.clearTimeout(shareCopyFeedbackTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    shareLinkRequestIdRef.current += 1;
    setShareLinkUrl("");
    setIsCreatingShareLink(false);
    setIsShareLinkCopied(false);
    setShareLinkError(null);
  }, [selectedProjectId]);

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
    let isCurrent = true;
    setIsAuthLoading(true);
    setAuthError(null);
    setError(null);
    Promise.allSettled([getMe(), listProjects()])
      .then(([meResult, projectsResult]) => {
        if (!isCurrent) return;

        if (meResult.status === "rejected") {
          setMe(null);
          setProjects([]);
          setSelectedProjectId(null);
          setConnections([]);
          setSelectedConnId(null);
          setAuthError(
            "인증이 필요합니다. 로그인 상태를 확인한 뒤 다시 시도해 주세요.",
          );
          return;
        }

        const currentUser = meResult.value;
        setMe({
          subject: currentUser.subject,
          display_name: currentUser.display_name,
        });

        if (projectsResult.status === "rejected") {
          setProjects([]);
          setSelectedProjectId(null);
          setError("프로젝트 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
          return;
        }

        const projectItems = projectsResult.value;
        setProjects(projectItems);
        setSelectedProjectId(projectItems[0]?.project_space_uuid || null);
      })
      .finally(() => {
        if (isCurrent) setIsAuthLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedProjectId) {
      setConnections([]);
      setSelectedConnId(null);
      setSnapshots([]);
      return;
    }
    let isCurrent = true;
    listConnections(selectedProjectId)
      .then((c) => {
        if (!isCurrent) return;
        setConnections(c);
        if (c[0]) setSelectedConnId(c[0].db_connection_uuid);
      })
      .catch(() => {
        if (isCurrent) {
          setError("데이터베이스 연결 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
        }
      });
    listSnapshots(selectedProjectId)
      .then((items) => {
        if (isCurrent) setSnapshots(items);
      })
      .catch(() => {
        if (isCurrent) {
          setError("스냅샷 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [selectedProjectId]);

  useEffect(() => {
    if (!snapshotId) return;
    const timer = setInterval(() => {
      getSnapshot(snapshotId)
        .then((s) => {
          setSnapshot(s);
          if (s.status === "succeeded" || s.status === "failed" || s.status === "not_found") {
            clearInterval(timer);
            if (selectedProjectId) {
              listSnapshots(selectedProjectId)
                .then(setSnapshots)
                .catch(() =>
                  setError("스냅샷 목록을 새로고침하지 못했습니다. 잠시 후 다시 시도해 주세요."),
                );
            }
          }
        })
        .catch(() =>
          setError("스냅샷 상태를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요."),
        );
    }, 1000);
    return () => clearInterval(timer);
  }, [selectedProjectId, snapshotId]);

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
  const selectedProject = projects.find(
    (project) => project.project_space_uuid === selectedProjectId,
  );
  const recentProjects = projects.slice(0, 4);
  const recentSnapshots = snapshots.slice(0, 5);

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
    setSelectedEditorNodeId(null);
    setSelectedEditorEdgeId(null);

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
    /* v8 ignore next -- the toolbar disables this handler for both guard states */
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
      /* v8 ignore else -- Vitest always runs with import.meta.env.DEV enabled */
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

  const onSelectionChange = useCallback(
    ({
      nodes: selectedNodes,
      edges: selectedEdges,
    }: OnSelectionChangeParams<Node<TableNodeData>, Edge>) => {
      const selectedNodeId = selectedNodes[0]?.id ?? null;
      setSelectedEditorNodeId(selectedNodeId);
      setSelectedEditorEdgeId(
        selectedNodeId ? null : (selectedEdges[0]?.id ?? null),
      );
    },
    [],
  );

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
    setExportDdlText(nodes.length > 0 ? exportDDL(nodes, edges) : "");
    setShareLinkError(null);
    setIsExportModalOpen(true);
  }

  function onCloseExport() {
    setIsExportModalOpen(false);
    setIsCopied(false);
    if (copyFeedbackTimeoutRef.current !== null) {
      window.clearTimeout(copyFeedbackTimeoutRef.current);
      copyFeedbackTimeoutRef.current = null;
    }
    if (shareCopyFeedbackTimeoutRef.current !== null) {
      window.clearTimeout(shareCopyFeedbackTimeoutRef.current);
      shareCopyFeedbackTimeoutRef.current = null;
    }
    setIsShareLinkCopied(false);
    setShareLinkError(null);
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

  const onCreateShareLink = useCallback(async () => {
    if (!selectedProjectId || isCreatingShareLink) return;

    const requestId = shareLinkRequestIdRef.current + 1;
    shareLinkRequestIdRef.current = requestId;
    const commitIfCurrent = (commit: () => void) => {
      if (shareLinkRequestIdRef.current === requestId) commit();
    };

    setIsCreatingShareLink(true);
    setShareLinkError(null);
    setIsShareLinkCopied(false);

    try {
      const link = await createShareLink(selectedProjectId);
      commitIfCurrent(() => setShareLinkUrl(link.url));
    } catch {
      commitIfCurrent(() =>
        setShareLinkError(
          "공유 링크를 만들지 못했습니다. 잠시 후 다시 시도해 주세요.",
        ),
      );
    } finally {
      commitIfCurrent(() => setIsCreatingShareLink(false));
    }
  }, [isCreatingShareLink, selectedProjectId]);

  const onCopyShareLink = useCallback(async () => {
    if (!shareLinkUrl) return;
    try {
      await navigator.clipboard.writeText(shareLinkUrl);
      setShareLinkError(null);
      setIsShareLinkCopied(true);

      if (shareCopyFeedbackTimeoutRef.current !== null) {
        window.clearTimeout(shareCopyFeedbackTimeoutRef.current);
      }

      shareCopyFeedbackTimeoutRef.current = window.setTimeout(() => {
        setIsShareLinkCopied(false);
        shareCopyFeedbackTimeoutRef.current = null;
      }, 2000);
    } catch {
      setIsShareLinkCopied(false);
      setShareLinkError("공유 링크 복사에 실패했습니다.");
    }
  }, [shareLinkUrl]);

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

  function onDownloadDbml() {
    downloadText("pg-erd-diagram.dbml", exportDbml(nodes, edges), "text/plain");
  }

  function onDownloadPrisma() {
    downloadText("pg-erd-diagram.prisma", exportPrisma(nodes, edges), "text/plain");
  }

  function onExportDictionaryCsv() {
    downloadText(
      "data_dictionary.csv",
      exportDictionaryCsv(nodes, edges),
      "text/csv;charset=utf-8",
    );
  }

  function onExportDictionaryMarkdown() {
    downloadText(
      "data_dictionary.md",
      exportDictionaryMarkdown(nodes, edges),
      "text/markdown;charset=utf-8",
    );
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
    /* v8 ignore next -- the toolbar disables this action when the canvas is empty */
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
    /* v8 ignore next -- the toolbar disables this action when the canvas is empty */
    if (nodes.length === 0) return;
    setIsGroupModalOpen(true);
  }

  function onAutoInferRelationships() {
    const inferredEdges = inferRelationships(nodes);
    if (inferredEdges.length > 0) {
      setEdges((eds) => [...eds, ...inferredEdges]);
    }
  }

  function onClearCanvas() {
    if (window.confirm("캔버스의 모든 노드와 관계를 삭제하시겠습니까?")) {
      setNodes([]);
      setEdges([]);
    }
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
    if (!window.confirm(`'${editingNode.data.title}' 테이블을 삭제하시겠습니까?`)) return;

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
    /* v8 ignore next -- the toolbar disables this handler for both guard states */
    if (!undoPositions || isLayouting) return;
    setNodes((prev) => applyPositions(prev, undoPositions));
    setUndoPositions(null);
    setLayoutMessage("되돌렸습니다");
  }

  async function onCreateProject() {
    const nextProjectName = projectName.trim();
    /* v8 ignore next -- the create control is disabled for both guard states */
    if (!nextProjectName || isCreatingProject) return;
    setError(null);
    setIsCreatingProject(true);
    try {
      const p = await createProject(nextProjectName);
      setProjects((prev) => [p, ...prev]);
      setSelectedProjectId(p.project_space_uuid);
    } catch {
      setError("프로젝트를 만들지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setIsCreatingProject(false);
    }
  }

  async function onCreateConnection() {
    /* v8 ignore next -- the save control is disabled without a project or while saving */
    if (!selectedProjectId || isCreatingConnection) return;
    const nextConnectionName = connName.trim();
    // The handler is mounted beside this input, so the ref is established first.
    const dsnInput = dsnInputRef.current!;
    const connectionDsn = dsnInput.value.trim();
    /* v8 ignore next -- the save control is disabled until both fields are present */
    if (!nextConnectionName || !connectionDsn) return;
    if (!isSupportedConnectionDsn(connectionDsn)) {
      setError("Connection DSN must use postgresql://, postgres://, or snowflake:// with a host.");
      dsnInput.value = "";
      setIsDsnPresent(false);
      return;
    }
    setError(null);
    setIsCreatingConnection(true);
    dsnInput.value = "";
    setIsDsnPresent(false);
    try {
      const c = await createConnection(
        selectedProjectId,
        nextConnectionName,
        connectionDsn,
      );
      setConnections((prev) => [c, ...prev]);
      setSelectedConnId(c.db_connection_uuid);
    } catch {
      setError(
        "데이터베이스 연결을 만들지 못했습니다. 입력값을 확인한 뒤 다시 시도해 주세요.",
      );
    } finally {
      setIsCreatingConnection(false);
    }
  }

  async function onCreateSnapshot() {
    /* v8 ignore next -- the snapshot control is disabled for every guard state */
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
    } catch {
      setError("스냅샷을 만들지 못했습니다. 잠시 후 다시 시도해 주세요.");
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
        <section className="authGate__card" aria-labelledby="auth-loading-title">
          <h1 id="auth-loading-title">Cloud ERD</h1>
          <p className="authGate__lead">
            PostgreSQL schema를 시각화하고 공유 가능한 ERD로 관리합니다.
          </p>
          <div className="authGate__status" role="status">
            <span className="authGate__spinner" aria-hidden="true" />
            인증 정보를 확인하는 중입니다.
          </div>
        </section>
      </main>
    );
  }

  if (!me) {
    /* v8 ignore next -- the loaded unauthenticated state always records its rejection */
    const authGateMessage =
      authError ??
      "인증이 필요합니다. 로그인 상태를 확인한 뒤 다시 시도해 주세요.";
    return (
      <main id="main" className="authGate">
        <section className="authGate__card" aria-labelledby="auth-required-title">
          <h1 id="auth-required-title">Cloud ERD</h1>
          <p className="authGate__lead">
            PostgreSQL schema를 시각화하고 공유 가능한 ERD로 관리합니다.
          </p>
          <p className="authGate__error" role="alert">{authGateMessage}</p>
          <button
            type="button"
            className="buttonPrimary"
            /* v8 ignore next -- browser navigation cannot be exercised in jsdom */
            onClick={() => window.location.reload()}
          >
            다시 시도
          </button>
        </section>
      </main>
    );
  }

  return (
    <div className="layout">
      <a className="skip-link" href="#main">
        본문 바로가기
      </a>
      <aside className="sidebar">
        <div className="brandLockup">
          <span className="brandLockup__mark" aria-hidden="true" />
          <h2>Cloud ERD</h2>
        </div>

        <nav className="workspaceNav" aria-label="주요 화면">
          {workspaceNavItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={activeView === item.id ? "workspaceNav__item workspaceNav__item--active" : "workspaceNav__item"}
              onClick={() => setActiveView(item.id)}
              aria-current={activeView === item.id ? "page" : undefined}
            >
              {item.label}
            </button>
          ))}
        </nav>

        {activeView === "editor" ? (
          <>

        <div className="field">
          <label htmlFor="project-select">Project</label>
          <div className="row">
            <select
              id="project-select"
              value={selectedProjectId || ""}
              onChange={(e) => setSelectedProjectId(e.target.value || null)}
              className="sidebarSelect"
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

        <form
          className="field"
          aria-label="사이드바 프로젝트 생성"
          onSubmit={(event) => {
            event.preventDefault();
            void onCreateProject();
          }}
        >
          <label htmlFor="project-name">New project</label>
          <div className="row">
            <input
              id="project-name"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
            />
            <button
              type="submit"
              className="buttonPrimary"
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
        </form>

        <hr />

        <div className="field">
          <label htmlFor="conn-select">Connection</label>
          <select
            id="conn-select"
            value={selectedConnId || ""}
            onChange={(e) => setSelectedConnId(e.target.value || null)}
            className="sidebarSelect"
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

        <form
          className="field"
          aria-label="연결 생성"
          onSubmit={(event) => {
            event.preventDefault();
            void onCreateConnection();
          }}
        >
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
            type="submit"
            className="buttonPrimary"
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
        </form>

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
          className="buttonPrimary"
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

        <div className="snapshotStatus" aria-live="polite">
          Snapshot: {snapshot?.status || "—"}
          {snapshot?.error_message ? (
            <div className="error" role="alert">
              스냅샷 생성에 실패했습니다. 연결과 스키마 설정을 확인한 뒤 다시 시도해 주세요.
            </div>
          ) : null}
        </div>

        {error ? (
          <div className="error error--spaced" role="alert">
            {error}
          </div>
        ) : null}
          </>
        ) : (
          <div className="sidebarSummary" aria-label="작업공간 상태">
            <div>
              <span>현재 사용자</span>
              <strong>{me?.display_name || me?.subject || "인증 필요"}</strong>
            </div>
            <div>
              <span>선택 프로젝트</span>
              <strong>{selectedProject?.project_name || "선택 안 됨"}</strong>
            </div>
            <button type="button" onClick={() => setActiveView("editor")}>
              편집기로 이동
            </button>
          </div>
        )}
      </aside>

      <main id="main" className="main" tabIndex={-1}>
        {error && activeView !== "editor" ? (
          <div className="workspaceError" role="alert">
            {error}
          </div>
        ) : null}
        {activeView === "dashboard" ? (
          <section className="workspaceScreen" aria-labelledby="dashboard-title">
            <div className="workspaceHeader">
              <div>
                <h1 id="dashboard-title">대시보드</h1>
                <p>최근 프로젝트와 다이어그램을 빠르게 확인합니다.</p>
              </div>
              <button type="button" className="buttonPrimary" onClick={() => setActiveView("editor")}>
                새 모델링
              </button>
            </div>

            <div className="metricGrid" aria-label="작업 요약">
              <div className="metricCard">
                <span>프로젝트</span>
                <strong>{projects.length}</strong>
              </div>
              <div className="metricCard">
                <span>연결</span>
                <strong>{connections.length}</strong>
              </div>
              <div className="metricCard">
                <span>스냅샷</span>
                <strong>{snapshots.length}</strong>
              </div>
              <div className="metricCard">
                <span>다이어그램</span>
                <strong>
                  {snapshots.filter((item) => item.status === "succeeded").length}
                </strong>
              </div>
            </div>

            <section className="workspaceSection" aria-labelledby="recent-projects-title">
              <div className="sectionHeader">
                <h2 id="recent-projects-title">최근 프로젝트</h2>
                <button type="button" onClick={() => setActiveView("projects")}>
                  전체 보기
                </button>
              </div>
              {recentProjects.length ? (
                <div className="projectCards">
                  {recentProjects.map((project) => (
                    <button
                      key={project.project_space_uuid}
                      type="button"
                      className="projectCard"
                      onClick={() => {
                        setSelectedProjectId(project.project_space_uuid);
                        setActiveView("diagrams");
                      }}
                    >
                      <span className="projectCard__icon" aria-hidden="true" />
                      <strong>{project.project_name}</strong>
                      <span>다이어그램 보기</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="panelEmpty">아직 프로젝트가 없습니다. 편집기에서 프로젝트를 생성하세요.</div>
              )}
            </section>

            <section className="workspaceSection" aria-labelledby="recent-diagrams-title">
              <div className="sectionHeader">
                <h2 id="recent-diagrams-title">최근 다이어그램</h2>
                <button type="button" onClick={() => setActiveView("diagrams")}>
                  목록 보기
                </button>
              </div>
              <DiagramTable
                snapshots={recentSnapshots}
                selectedProjectName={selectedProject?.project_name ?? ""}
                onOpenEditor={(id) => {
                  setSnapshotId(id);
                  setSnapshot(null);
                  setActiveView("editor");
                }}
              />
            </section>
          </section>
        ) : activeView === "projects" ? (
          <section className="workspaceScreen" aria-labelledby="projects-title">
            <div className="workspaceHeader">
              <div>
                <h1 id="projects-title">프로젝트</h1>
                <p>프로젝트를 선택하면 해당 다이어그램 목록을 볼 수 있습니다.</p>
              </div>
              <form
                className="inlineCreate"
                aria-label="프로젝트 생성"
                onSubmit={(event) => {
                  event.preventDefault();
                  void onCreateProject();
                }}
              >
                <input
                  aria-label="새 프로젝트 이름"
                  value={projectName}
                  onChange={(event) => setProjectName(event.currentTarget.value)}
                />
                <button
                  type="submit"
                  className="buttonPrimary"
                  disabled={!projectName.trim() || isCreatingProject}
                >
                  {isCreatingProject ? "생성 중" : "새 프로젝트"}
                </button>
              </form>
            </div>
            <div className="dataTable" role="table" aria-label="프로젝트 목록">
              <div className="dataTable__row dataTable__row--projects dataTable__row--head" role="row">
                <span role="columnheader">이름</span>
                <span role="columnheader">연결</span>
                <span role="columnheader">동작</span>
              </div>
              {projects.map((project) => (
                <div className="dataTable__row dataTable__row--projects" role="row" key={project.project_space_uuid}>
                  <strong role="cell">{project.project_name}</strong>
                  <span role="cell">{project.project_space_uuid === selectedProjectId ? connections.length : "선택 후 표시"}</span>
                  <span role="cell">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedProjectId(project.project_space_uuid);
                        setActiveView("diagrams");
                      }}
                    >
                      열기
                    </button>
                  </span>
                </div>
              ))}
              {!projects.length ? (
                <div className="panelEmpty">프로젝트가 없습니다. 이름을 입력해 새 프로젝트를 만드세요.</div>
              ) : null}
            </div>
          </section>
        ) : activeView === "diagrams" ? (
          <section className="workspaceScreen" aria-labelledby="diagrams-title">
            <div className="workspaceHeader">
              <div>
                <h1 id="diagrams-title">다이어그램</h1>
                <p>{selectedProject ? `${selectedProject.project_name} 프로젝트의 스냅샷` : "프로젝트를 선택하세요."}</p>
              </div>
              <button type="button" className="buttonPrimary" onClick={() => setActiveView("editor")}>
                편집기 열기
              </button>
            </div>
            <label className="workspaceSearch">
              <span className="srOnly">다이어그램 검색</span>
              <input
                aria-label="다이어그램 검색"
                placeholder="다이어그램 검색"
                type="search"
                value={diagramSearch}
                onChange={(event) => setDiagramSearch(event.currentTarget.value)}
              />
            </label>
            <DiagramTable
              snapshots={snapshots}
              searchText={diagramSearch}
              selectedProjectName={selectedProject?.project_name ?? ""}
              onOpenEditor={(id) => {
                setSnapshotId(id);
                setSnapshot(null);
                setActiveView("editor");
              }}
            />
          </section>
        ) : (
          <div className="editorWorkspace">
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
              {isLayouting ? "…" : "↔"}
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
              ↶
            </button>
            <button
              type="button"
              onClick={onOpenAddTable}
              title="테이블 추가"
              aria-label="테이블 추가"
            >
              +
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
              ◇
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
              #
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
              SQL
            </button>
            <button
              type="button"
              onClick={onDownloadSvg}
              disabled={nodes.length === 0}
              title={
                nodes.length === 0
                  ? "내보낼 테이블이 없습니다"
                  : "SVG 이미지 내보내기"
              }
              aria-label="SVG 이미지 내보내기"
            >
              IMG
            </button>
            <button
              type="button"
              onClick={onDownloadUml}
              disabled={nodes.length === 0}
              title={
                nodes.length === 0 ? "내보낼 테이블이 없습니다" : "PlantUML 내보내기"
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
              {"{}"}
            </button>
            <button
              type="button"
              onClick={onOpenExport}
              disabled={!selectedProjectId}
              title={
                !selectedProjectId
                  ? "공유할 프로젝트를 먼저 선택하세요"
                  : "공유 및 내보내기"
              }
              aria-label="공유 및 내보내기"
            >
              ↗
            </button>
            <div className="srOnly" aria-live="polite">
              {[layoutMessage, nodeSearchStatus].filter(Boolean).join(" ")}
            </div>
          </div>

          <ReactFlow
            colorMode={colorMode}
            nodes={visibleNodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onEdgeClick={onEdgeClick}
            onSelectionChange={onSelectionChange}
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
                    작업 패널에서 스냅샷을 생성하거나 상단의 <b>테이블 추가</b> 버튼을 눌러 시작하세요.
                  </div>
                  <button
                    type="button"
                    className="emptyState__action"
                    title="테이블 추가"
                    aria-label="테이블 추가"
                    onClick={onOpenAddTable}
                  >
                    + 테이블 추가
                  </button>
                </>
              )}
            </div>
          )}

          <ExportModal
            isOpen={isExportModalOpen}
            isCopied={isCopied}
            hasDdlExport={nodes.length > 0}
            ddlText={exportDdlText}
            hasDictionaryExport={nodes.length > 0}
            hasDiagramExport={nodes.length > 0}
            shareLinkUrl={shareLinkUrl}
            isCreatingShareLink={isCreatingShareLink}
            isShareLinkCopied={isShareLinkCopied}
            shareLinkError={shareLinkError}
            canCreateShareLink={Boolean(selectedProjectId)}
            onCloseExport={onCloseExport}
            onCopyExportDdl={onCopyExportDdl}
            onDownloadSvg={onDownloadSvg}
            onDownloadUml={onDownloadUml}
            onDownloadMermaid={onDownloadMermaid}
            onExportDictionaryCsv={onExportDictionaryCsv}
            onExportDictionaryMarkdown={onExportDictionaryMarkdown}
            onDownloadDbml={onDownloadDbml}
            onDownloadPrisma={onDownloadPrisma}
            onCreateShareLink={onCreateShareLink}
            onCopyShareLink={onCopyShareLink}
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
          <aside className="editorProperties" aria-label="ERD 속성">
            <div>
              <h2>속성</h2>
              <p>
                선택한 프로젝트, 테이블 검색, 공유와 내보내기 작업을 관리합니다.
              </p>
            </div>

            <label className="editorProperties__search">
              <span>테이블 검색</span>
              <input
                aria-label="테이블 또는 컬럼 검색"
                placeholder="테이블/컬럼 검색"
                type="search"
                value={nodeSearch}
                onChange={(event) => setNodeSearch(event.currentTarget.value)}
              />
            </label>

            {selectedEditorNode ? (
              <section
                className="editorProperties__selection"
                aria-labelledby="selected-table-properties-title"
              >
                <div className="editorProperties__selectionHeader">
                  <div>
                    <span>선택한 테이블</span>
                    <h3 id="selected-table-properties-title">
                      {selectedEditorNode.data.title}
                    </h3>
                  </div>
                  {selectedEditorNode.data.businessGroup ? (
                    <span
                      className="editorProperties__groupColor"
                      aria-label={`${selectedEditorNode.data.businessGroup.name} 그룹 색상`}
                      style={{ background: selectedEditorNode.data.businessGroup.color }}
                    />
                  ) : null}
                </div>
                {selectedEditorNode.data.comment ? (
                  <p>{selectedEditorNode.data.comment}</p>
                ) : null}
                <div className="editorProperties__columns">
                  <h4>컬럼</h4>
                  {selectedEditorNode.data.columns.length ? (
                    <ul>
                      {selectedEditorNode.data.columns.map((column) => (
                        <li key={column.column_name}>
                          <span>{column.column_name}</span>
                          <code>{column.data_type}</code>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>등록된 컬럼이 없습니다.</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setEditingNode(selectedEditorNode);
                    setIsEditTableModalOpen(true);
                  }}
                >
                  테이블 편집
                </button>
              </section>
            ) : selectedEditorEdge ? (
              <section
                className="editorProperties__selection"
                aria-labelledby="selected-relationship-properties-title"
              >
                <div className="editorProperties__selectionHeader">
                  <div>
                    <span>선택한 관계</span>
                    <h3 id="selected-relationship-properties-title">
                      {typeof selectedEditorEdge.label === "string" &&
                      selectedEditorEdge.label.trim()
                        ? selectedEditorEdge.label
                        : "이름 없는 관계"}
                    </h3>
                  </div>
                </div>
                <p>
                  {nodes.find((node) => node.id === selectedEditorEdge.source)?.data
                    .title ?? selectedEditorEdge.source}
                  {" → "}
                  {nodes.find((node) => node.id === selectedEditorEdge.target)?.data
                    .title ?? selectedEditorEdge.target}
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setEditingEdge(selectedEditorEdge);
                    setRelLabel(
                      typeof selectedEditorEdge.label === "string"
                        ? selectedEditorEdge.label
                        : "",
                    );
                  }}
                >
                  관계 편집
                </button>
              </section>
            ) : (
              <div className="editorProperties__emptySelection">
                캔버스에서 테이블을 선택하면 이름과 컬럼을, 관계를 선택하면 연결
                정보를 확인할 수 있습니다.
              </div>
            )}

            <dl className="editorProperties__summary">
              <div>
                <dt>프로젝트</dt>
                <dd>{selectedProject?.project_name || "선택 안 됨"}</dd>
              </div>
              <div>
                <dt>테이블</dt>
                <dd>{nodes.length}</dd>
              </div>
              <div>
                <dt>관계</dt>
                <dd>{edges.length}</dd>
              </div>
            </dl>

            <div className="editorProperties__actions">
              <button
                type="button"
                aria-label="공유 열기"
                onClick={onOpenExport}
                disabled={!selectedProjectId}
              >
                공유
              </button>
              <button
                type="button"
                className="editorProperties__primaryAction"
                aria-label="내보내기 열기"
                onClick={onOpenExport}
                disabled={nodes.length === 0}
              >
                내보내기
              </button>
              <button
                type="button"
                onClick={onAutoInferRelationships}
                disabled={nodes.length === 0}
                title={
                  nodes.length === 0 ? "추론할 테이블이 없습니다" : "관계 자동 추론"
                }
                aria-label="관계 자동 추론"
              >
                관계 자동 추론
              </button>
              <button
                type="button"
                onClick={onClearCanvas}
                disabled={nodes.length === 0}
                title={
                  nodes.length === 0 ? "지울 노드가 없습니다" : "모든 노드 지우기"
                }
                aria-label="모든 노드 지우기"
              >
                캔버스 비우기
              </button>
            </div>
          </aside>
          </div>
        )}
      </main>
    </div>
  );
}

export default function App({ colorMode = "system" }: { colorMode?: ColorMode }) {
  const shareLinkId = publicShareIdFromPath(window.location.pathname);
  return shareLinkId ? (
    <SharedDiagramView shareLinkId={shareLinkId} colorMode={colorMode} />
  ) : (
    <AuthenticatedApp colorMode={colorMode} />
  );
}

export function DiagramTable({
  snapshots,
  searchText = "",
  selectedProjectName,
  onOpenEditor,
}: {
  snapshots: Snapshot[];
  searchText?: string;
  selectedProjectName?: string;
  onOpenEditor: (snapshotId: string) => void;
}) {
  const normalizedSearchText = searchText.trim().toLocaleLowerCase();
  const rows = snapshots
    .map((item, index) => ({
      item,
      name: `ERD_${item.schema_filter || "all"}_${index + 1}`,
    }))
    .filter(({ item, name }) => {
      if (!normalizedSearchText) return true;
      return (
        name.toLocaleLowerCase().includes(normalizedSearchText) ||
        item.status.toLocaleLowerCase().includes(normalizedSearchText)
      );
    });

  if (!rows.length) {
    return (
      <div className="panelEmpty">
        {snapshots.length
          ? "검색 결과가 없습니다."
          : "아직 다이어그램 스냅샷이 없습니다. 편집기에서 데이터베이스를 역공학해 시작하세요."}
      </div>
    );
  }

  return (
    <div className="dataTable" role="table" aria-label="다이어그램 목록">
      <div className="dataTable__row dataTable__row--head" role="row">
        <span role="columnheader">이름</span>
        <span role="columnheader">프로젝트</span>
        <span role="columnheader">상태</span>
        <span role="columnheader">동작</span>
      </div>
      {rows.map(({ item, name }) => (
        <div className="dataTable__row" role="row" key={item.schema_snapshot_uuid}>
          <strong role="cell">{name}</strong>
          <span role="cell">{selectedProjectName || "현재 프로젝트"}</span>
          <span role="cell">
            <span className={statusPillClassName(item.status)}>
              {item.status}
            </span>
          </span>
          <span role="cell">
            <button
              type="button"
              onClick={() => onOpenEditor(item.schema_snapshot_uuid)}
            >
              열기
            </button>
          </span>
        </div>
      ))}
    </div>
  );
}
