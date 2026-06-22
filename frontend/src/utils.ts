import DOMPurify from "dompurify";

export function sanitizeInput(input: string | undefined | null): string {
  if (!input) return "";
  return DOMPurify.sanitize(input, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
}
