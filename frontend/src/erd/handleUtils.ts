export function sanitizeHandleId(columnName: string): string {
  // Replace invalid characters for DOM IDs/React Flow handles
  return columnName.replace(/[^a-zA-Z0-9_-]/g, '_');
}

export function sourceColumnHandleId(columnName: string): string {
  return `src-${sanitizeHandleId(columnName)}`;
}

export function targetColumnHandleId(columnName: string): string {
  return `tgt-${sanitizeHandleId(columnName)}`;
}
