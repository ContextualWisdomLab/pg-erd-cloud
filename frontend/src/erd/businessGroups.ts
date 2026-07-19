export type BusinessGroup = {
  id: string;
  name: string;
  color: string;
};

export const BUSINESS_GROUP_COLORS = [
  "#047857",
  "#2563eb",
  "#b45309",
  "#7c3aed",
  "#be123c",
  "#0f766e",
] as const;

export const DEFAULT_BUSINESS_GROUP_COLOR = BUSINESS_GROUP_COLORS[0];

export function normalizeBusinessGroupColor(
  color: string | null | undefined,
): string {
  if (
    typeof color === "string" &&
    BUSINESS_GROUP_COLORS.includes(color as (typeof BUSINESS_GROUP_COLORS)[number])
  ) {
    return color;
  }
  return DEFAULT_BUSINESS_GROUP_COLOR;
}

export function buildBusinessGroupId(name: string): string {
  const normalized = name
    .trim()
    .replace(/[^A-Za-z0-9_가-힣]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
  return `group_${normalized || Date.now()}`;
}

export function uniqueBusinessGroupId(
  name: string,
  existingGroups: BusinessGroup[],
): string {
  const baseId = buildBusinessGroupId(name);
  // ⚡ Bolt: Eliminate O(N) intermediate array allocation and GC overhead
  // by populating the Set iteratively instead of `new Set(existingGroups.map(...))`
  const existingIds = new Set<string>();
  for (const group of existingGroups) {
    existingIds.add(group.id);
  }
  if (!existingIds.has(baseId)) return baseId;
  let suffix = 2;
  while (existingIds.has(`${baseId}_${suffix}`)) {
    suffix += 1;
  }
  return `${baseId}_${suffix}`;
}
