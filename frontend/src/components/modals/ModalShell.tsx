import type { MouseEvent, ReactNode } from "react";

import { useDialogAccessibility } from "./useDialogAccessibility";

export type ModalShellSize =
  | "addTable"
  | "relationship"
  | "export"
  | "group"
  | "cardinality"
  | "editTable";

interface ModalShellProps {
  title: ReactNode;
  titleId: string;
  description?: ReactNode;
  descriptionId?: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  closeLabel: string;
  size: ModalShellSize;
  className?: string;
  closeOnBackdrop?: boolean;
}

export function ModalShell({
  title,
  titleId,
  description,
  descriptionId = `${titleId}-description`,
  children,
  footer,
  onClose,
  closeLabel,
  size,
  className = "",
  closeOnBackdrop = false,
}: ModalShellProps) {
  const dialogRef = useDialogAccessibility(true, onClose);

  function handleBackdropClick(event: MouseEvent<HTMLDivElement>) {
    if (closeOnBackdrop && event.target === event.currentTarget) {
      onClose();
    }
  }

  const shellClassName = [
    "modalShell",
    `modalShell--${size}`,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="modalOverlay" onClick={handleBackdropClick}>
      <div
        className={shellClassName}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="modalShell__header">
          <div>
            <h3 id={titleId}>{title}</h3>
            {description ? (
              <p className="modalShell__description" id={descriptionId}>
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            className="modalShell__close"
            aria-label={closeLabel}
            onClick={onClose}
          >
            <span aria-hidden="true">×</span>
          </button>
        </div>
        <div className="modalShell__body">{children}</div>
        {footer ? <div className="modalShell__footer">{footer}</div> : null}
      </div>
    </div>
  );
}
