import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type ColorMode,
  type NodeTypes,
} from "@xyflow/react";
import { useEffect, useMemo, useRef, useState } from "react";

import { getSharedLinkInfo, getSharedSnapshot } from "../api";
import TableNode from "../erd/TableNode";
import { snapshotToGraph } from "../erd/convert";
import type { SharedLinkInfo, SnapshotDetail } from "../types";

interface SharedDiagramViewProps {
  shareLinkId: string;
  colorMode?: ColorMode;
}

function snapshotOptionLabel(
  item: SharedLinkInfo["snapshots"][number],
  snapshots: SharedLinkInfo["snapshots"],
): string {
  const schemaLabel = item.schema_filter || "전체 스키마";
  const createdLabel = item.created_at.slice(0, 16).replace("T", " ");
  const hasDuplicateLabel = snapshots.some(
    (other) =>
      other.schema_snapshot_uuid !== item.schema_snapshot_uuid &&
      (other.schema_filter || "전체 스키마") === schemaLabel &&
      other.created_at.slice(0, 16).replace("T", " ") === createdLabel,
  );
  const shortId = hasDuplicateLabel
    ? ` · ${item.schema_snapshot_uuid.slice(0, 8)}`
    : "";
  return `${schemaLabel} · ${createdLabel}${shortId} · ${item.status}`;
}

export function SharedDiagramView({
  shareLinkId,
  colorMode = "system",
}: SharedDiagramViewProps) {
  const [shareInfo, setShareInfo] = useState<SharedLinkInfo | null>(null);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState("");
  const [snapshot, setSnapshot] = useState<SnapshotDetail | null>(null);
  const [isLoadingLink, setIsLoadingLink] = useState(true);
  const [isLoadingSnapshot, setIsLoadingSnapshot] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const loadedShareLinkIdRef = useRef<string | null>(null);
  const nodeTypes = useMemo<NodeTypes>(() => ({ tableNode: TableNode }), []);

  useEffect(() => {
    let isCurrent = true;
    setIsLoadingLink(true);
    setErrorMessage("");
    setShareInfo(null);
    setSelectedSnapshotId("");
    setSnapshot(null);
    setIsLoadingSnapshot(false);
    loadedShareLinkIdRef.current = null;

    getSharedLinkInfo(shareLinkId)
      .then((info) => {
        if (!isCurrent) return;
        const successfulSnapshots = info.snapshots.filter(
          (item) => item.status === "succeeded",
        );
        loadedShareLinkIdRef.current = shareLinkId;
        setShareInfo({ ...info, snapshots: successfulSnapshots });
        const initialSnapshot = successfulSnapshots[0];
        setSelectedSnapshotId(initialSnapshot?.schema_snapshot_uuid ?? "");
      })
      .catch(() => {
        if (!isCurrent) return;
        setShareInfo(null);
        setSelectedSnapshotId("");
        setErrorMessage(
          "공유 링크를 열 수 없습니다. 링크가 만료되었거나 삭제되었는지 확인해 주세요.",
        );
      })
      .finally(() => {
        if (isCurrent) setIsLoadingLink(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [shareLinkId]);

  useEffect(() => {
    if (
      !selectedSnapshotId ||
      loadedShareLinkIdRef.current !== shareLinkId
    ) {
      setSnapshot(null);
      setIsLoadingSnapshot(false);
      return;
    }

    let isCurrent = true;
    setIsLoadingSnapshot(true);
    setErrorMessage("");
    setSnapshot(null);
    getSharedSnapshot(shareLinkId, selectedSnapshotId)
      .then((detail) => {
        if (isCurrent) setSnapshot(detail);
      })
      .catch(() => {
        if (!isCurrent) return;
        setSnapshot(null);
        setErrorMessage(
          "공유된 다이어그램을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
        );
      })
      .finally(() => {
        if (isCurrent) setIsLoadingSnapshot(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedSnapshotId, shareLinkId]);

  const graph = useMemo(
    () =>
      snapshot?.snapshot_json
        ? snapshotToGraph(snapshot.snapshot_json)
        : { nodes: [], edges: [] },
    [snapshot?.snapshot_json],
  );
  const availableSnapshots = useMemo(
    () =>
      shareInfo?.snapshots.filter((item) => item.status === "succeeded") ?? [],
    [shareInfo?.snapshots],
  );

  return (
    <div className="sharedDiagram">
      <header className="sharedDiagram__header">
        <div className="brandLockup sharedDiagram__brand">
          <span className="brandLockup__mark" aria-hidden="true" />
          <strong>Cloud ERD</strong>
        </div>
        <span className="statusPill">읽기 전용</span>
      </header>

      <aside className="sharedDiagram__sidebar">
        <div>
          <h1>공유 ERD</h1>
          <p>공유된 스냅샷을 안전한 읽기 전용 화면으로 확인합니다.</p>
        </div>

        {availableSnapshots.length ? (
          <label className="field">
            <span>스냅샷</span>
            <select
              aria-label="공유 스냅샷"
              value={selectedSnapshotId}
              onChange={(event) => setSelectedSnapshotId(event.currentTarget.value)}
            >
              {availableSnapshots.map((item) => (
                <option
                  key={item.schema_snapshot_uuid}
                  value={item.schema_snapshot_uuid}
                >
                  {snapshotOptionLabel(item, availableSnapshots)}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {snapshot ? (
          <dl className="sharedDiagram__summary">
            <div>
              <dt>상태</dt>
              <dd>{snapshot.status}</dd>
            </div>
            <div>
              <dt>스키마</dt>
              <dd>{snapshot.schema_filter || "전체"}</dd>
            </div>
            <div>
              <dt>테이블</dt>
              <dd>{graph.nodes.length}</dd>
            </div>
          </dl>
        ) : null}

        <a className="sharedDiagram__home" href="/">
          작업공간으로 이동
        </a>
      </aside>

      <main
        className="sharedDiagram__canvas"
        aria-label="공유 ERD 캔버스"
        aria-busy={isLoadingLink || isLoadingSnapshot}
      >
        {errorMessage ? (
          <div className="sharedDiagram__message" role="alert">
            {errorMessage}
          </div>
        ) : isLoadingLink || isLoadingSnapshot ? (
          <div className="sharedDiagram__message" role="status">
            공유 다이어그램을 불러오는 중입니다.
          </div>
        ) : !selectedSnapshotId ? (
          <div className="sharedDiagram__message" role="status">
            공유된 스냅샷이 없습니다.
          </div>
        ) : snapshot?.snapshot_json === null ? (
          <div className="sharedDiagram__message" role="status">
            공유 스냅샷 데이터가 없습니다.
          </div>
        ) : (
          <ReactFlow
            colorMode={colorMode}
            nodes={graph.nodes}
            edges={graph.edges}
            nodeTypes={nodeTypes}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            nodesFocusable={false}
            edgesFocusable={false}
            ariaLabelConfig={{
              'controls.ariaLabel': '다이어그램 보기 조작',
              'controls.zoomIn.ariaLabel': '확대',
              'controls.zoomOut.ariaLabel': '축소',
              'controls.fitView.ariaLabel': '다이어그램 맞춤',
              'minimap.ariaLabel': '다이어그램 미니맵',
            }}
            fitView
          >
            <Background />
            <Controls showInteractive={false} />
            <MiniMap />
          </ReactFlow>
        )}
      </main>
    </div>
  );
}
