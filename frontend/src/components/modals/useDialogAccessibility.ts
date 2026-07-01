import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

const trackedDocuments = new WeakSet<Document>();
let lastFocusedElement: HTMLElement | null = null;
let lastInteractedElement: HTMLElement | null = null;

function isHTMLElement(ownerDocument: Document, value: EventTarget | Element | null): value is HTMLElement {
  const HTMLElementCtor = ownerDocument.defaultView?.HTMLElement ?? HTMLElement;
  return value instanceof HTMLElementCtor;
}

function ensureFocusTracking(ownerDocument: Document) {
  if (trackedDocuments.has(ownerDocument)) return;

  function rememberFocusedElement(event: Event) {
    if (isHTMLElement(ownerDocument, event.target) && event.target !== ownerDocument.body) {
      lastFocusedElement = event.target;
    }
  }

  function rememberInteractedElement(event: Event) {
    if (isHTMLElement(ownerDocument, event.target) && event.target !== ownerDocument.body) {
      lastInteractedElement = event.target;
    }
  }

  trackedDocuments.add(ownerDocument);
  ownerDocument.addEventListener("focusin", rememberFocusedElement);
  ownerDocument.addEventListener("pointerdown", rememberInteractedElement, true);
  ownerDocument.addEventListener("mousedown", rememberInteractedElement, true);
  ownerDocument.addEventListener("keydown", rememberInteractedElement, true);
}

if (typeof document !== "undefined") {
  ensureFocusTracking(document);
}

function getFocusableElements(dialog: HTMLElement): HTMLElement[] {
  return Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
    .filter((element) => element.tabIndex >= 0 && element.getAttribute("aria-hidden") !== "true");
}

export function useDialogAccessibility(
  isOpen: boolean,
  onClose: () => void,
): RefObject<HTMLDivElement | null>;
export function useDialogAccessibility<TElement extends HTMLElement>(
  isOpen: boolean,
  onClose: () => void,
): RefObject<TElement | null>;
export function useDialogAccessibility<TElement extends HTMLElement = HTMLDivElement>(
  isOpen: boolean,
  onClose: () => void,
): RefObject<TElement | null> {
  const dialogRef = useRef<TElement | null>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    const ownerDocument = dialog?.ownerDocument ?? document;
    ensureFocusTracking(ownerDocument);
    if (!isOpen) return undefined;

    const activeElement =
      isHTMLElement(ownerDocument, ownerDocument.activeElement) &&
      ownerDocument.activeElement !== ownerDocument.body &&
      (!dialog || !dialog.contains(ownerDocument.activeElement))
        ? ownerDocument.activeElement
        : null;
    const interactedElement =
      lastInteractedElement &&
      ownerDocument.contains(lastInteractedElement) &&
      (!dialog || !dialog.contains(lastInteractedElement))
        ? lastInteractedElement
        : null;
    const focusedElement =
      lastFocusedElement &&
      ownerDocument.contains(lastFocusedElement) &&
      (!dialog || !dialog.contains(lastFocusedElement))
        ? lastFocusedElement
        : null;
    const previousFocus =
      activeElement ??
      interactedElement ??
      focusedElement;

    function focusFirstElement() {
      if (!dialog) return;
      if (dialog.contains(ownerDocument.activeElement)) return;

      const focusTarget =
        dialog.querySelector<HTMLElement>("[autofocus]") ??
        getFocusableElements(dialog)[0] ??
        dialog;
      focusTarget.focus();
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (!dialog) return;

      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onCloseRef.current();
        return;
      }

      if (event.key !== "Tab") return;

      const focusableElements = getFocusableElements(dialog);
      if (focusableElements.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }

      const first = focusableElements[0];
      const last = focusableElements[focusableElements.length - 1];
      const activeElement = ownerDocument.activeElement;

      if (event.shiftKey && activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    ownerDocument.addEventListener("keydown", handleKeyDown);
    const focusTimer = window.setTimeout(focusFirstElement, 0);

    return () => {
      window.clearTimeout(focusTimer);
      ownerDocument.removeEventListener("keydown", handleKeyDown);
      if (previousFocus && ownerDocument.contains(previousFocus)) {
        previousFocus.focus();
        window.setTimeout(() => {
          if (ownerDocument.contains(previousFocus)) {
            previousFocus.focus();
          }
        }, 0);
      }
    };
  }, [isOpen]);

  return dialogRef;
}
