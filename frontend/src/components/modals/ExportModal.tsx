import React from 'react';

interface ExportModalProps {
  isOpen: boolean;
  exportDdlText: string;
  isCopied: boolean;
  onCloseExport: () => void;
  onCopyExportDdl: () => void;
}

export function ExportModal({
  isOpen,
  exportDdlText,
  isCopied,
  onCloseExport,
  onCopyExportDdl,
}: ExportModalProps) {
  if (!isOpen) return null;

  return (
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
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-ddl-title"
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
        <h3 id="export-ddl-title">DDL 내보내기</h3>
        <textarea
          readOnly
          aria-label="DDL Export"
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
          <button type="button" onClick={onCloseExport}>닫기</button>
          <button
            type="button"
            onClick={onCopyExportDdl}
            style={{ background: "#034ea2", color: "#fff" }}
            aria-live="polite"
          >
            {isCopied ? "복사 완료 ✓" : "복사하기"}
          </button>
        </div>
      </div>
    </div>
  );
}
