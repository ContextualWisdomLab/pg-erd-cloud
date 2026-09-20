import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "summary",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

const trackedDocuments = new WeakSet<Document>();
type FocusableElement = HTMLElement | SVGElement;

let lastFocusedElement: FocusableElement | null = null;
let lastInteractedElement: FocusableElement | null = null;

function isFocusableElement(
  ownerDocument: Document,
  value: EventTarget | Element | null,
): value is FocusableElement {
  /* v8 ignore next -- browser-owned documents always expose their matching window constructor */
  const HTMLElementCtor = ownerDocument.defaultView?.HTMLElement ?? HTMLElement;
  /* v8 ignore next -- browser-owned documents always expose their matching window constructor */
  const SVGElementCtor = ownerDocument.defaultView?.SVGElement ?? SVGElement;
  return value instanceof HTMLElementCtor || value instanceof SVGElementCtor;
}

function isElement(ownerDocument: Document, value: EventTarget | null): value is Element {
  /* v8 ignore next -- browser-owned documents always expose their matching window constructor */
  const ElementCtor = ownerDocument.defaultView?.Element ?? Element;
  return value instanceof ElementCtor;
}

function closestFocusableAncestor(
  ownerDocument: Document,
  target: EventTarget | null,
): FocusableElement | null {
  if (!isElement(ownerDocument, target)) return null;
  const candidate = target.closest(FOCUSABLE_SELECTOR);
  return candidate && isFocusableElement(ownerDocument, candidate) && candidate !== ownerDocument.body
    ? candidate
    : null;
}

function ensureFocusTracking(ownerDocument: Document) {
  if (trackedDocuments.has(ownerDocument)) return;

  function rememberFocusedElement(event: Event) {
    if (isFocusableElement(ownerDocument, event.target) && event.target !== ownerDocument.body) {
      lastFocusedElement = event.target;
    }
  }

  function rememberInteractedElement(event: Event) {
    lastInteractedElement = closestFocusableAncestor(ownerDocument, event.target);
  }

  trackedDocuments.add(ownerDocument);
  ownerDocument.addEventListener("focusin", rememberFocusedElement);
  ownerDocument.addEventListener("pointerdown", rememberInteractedElement, true);
  ownerDocument.addEventListener("mousedown", rememberInteractedElement, true);
  ownerDocument.addEventListener("keydown", rememberInteractedElement, true);
}

/* v8 ignore else -- this browser module is only executed where document exists */
if (typeof document !== "undefined") {
  ensureFocusTracking(document);
}

function getFocusableElements(dialog: HTMLElement): FocusableElement[] {
  return Array.from(dialog.querySelectorAll(FOCUSABLE_SELECTOR))
    .filter((element): element is FocusableElement => {
      if (!isFocusableElement(dialog.ownerDocument, element)) return false;
      if (element.tabIndex < 0 || element.closest('[hidden], [aria-hidden="true"]')) {
        return false;
      }

      const closedDetails = element.closest<HTMLDetailsElement>("details:not([open])");
      return !closedDetails || closedDetails.querySelector("summary") === element;
    });
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
      isFocusableElement(ownerDocument, ownerDocument.activeElement) &&
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

      if (!dialog.contains(activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && activeElement === first) {
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
      const restoreFocus = () => {
        const fallbackCandidate = ownerDocument.querySelector(
          "[data-dialog-focus-fallback]",
        );
        const fallbackFocus = isFocusableElement(
          ownerDocument,
          fallbackCandidate,
        )
          ? fallbackCandidate
          : null;
        const focusTarget =
          previousFocus && ownerDocument.contains(previousFocus)
            ? previousFocus
            : fallbackFocus;
        if (focusTarget && ownerDocument.contains(focusTarget)) {
          focusTarget.focus();
        }
      };

      restoreFocus();
      window.setTimeout(restoreFocus, 0);
    };
  }, [isOpen]);

  return dialogRef;
}
