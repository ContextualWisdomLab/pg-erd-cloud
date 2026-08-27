export function sanitizeTableName(name: string): string {
  // Implement whitelist validation (alphanumeric only)
  return name.replace(/[^a-zA-Z0-9_]/g, "");
}
