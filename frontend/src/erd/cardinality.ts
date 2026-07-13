export type CardinalityStrength = "recommended" | "consider" | "skip";

export type CardinalityColumnInput = {
  columnName: string;
  isSelected: boolean;
  distinctCount: number | null;
};

export type IndexRecommendation = {
  index_name: string;
  columns: string[];
  access_method: "btree";
  estimated_distinct: number;
  cardinality_ratio: number;
  strength: CardinalityStrength;
  reason: string;
  source: "cardinality-wizard";
};

type BuildRecommendationInput = {
  tableName: string;
  rowCount: number | null;
  columns: CardinalityColumnInput[];
};

const MAX_INDEX_NAME_LENGTH = 63;

function clampRatio(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function sanitizeIdentifierPart(value: string): string {
  const normalized = value
    .trim()
    .replace(/["']/g, "")
    .replace(/[^A-Za-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
  return normalized || "col";
}

function tableIdentifierPart(tableName: string): string {
  const parts = tableName.split(".");
  return sanitizeIdentifierPart(parts[parts.length - 1] || tableName);
}

export function buildIndexName(tableName: string, columns: string[]): string {
  const raw = `idx_${tableIdentifierPart(tableName)}_${columns
    .map(sanitizeIdentifierPart)
    .join("_")}`;
  return raw.slice(0, MAX_INDEX_NAME_LENGTH);
}

export function calculateCardinalityRatio(
  rowCount: number,
  distinctCount: number,
): number {
  if (rowCount <= 0 || distinctCount <= 0) return 0;
  return clampRatio(distinctCount / rowCount);
}

export function classifyCardinality(ratio: number): CardinalityStrength {
  if (ratio >= 0.2) return "recommended";
  if (ratio >= 0.05) return "consider";
  return "skip";
}

function reasonFor(
  strength: CardinalityStrength,
  ratio: number,
  columnCount: number,
): string {
  const percent = `${Math.round(ratio * 100)}%`;
  if (strength === "recommended") {
    return `${percent} distinct; 선택도가 높습니다.`;
  }
  if (strength === "consider") {
    return `${percent} distinct; 조건, 조인, 정렬에서 쓰일 때 검토하세요.`;
  }
  const target = columnCount > 1 ? "컬럼 조합" : "컬럼";
  return `${percent} distinct; 워크로드 근거가 없으면 단독 ${target} 인덱스는 보류하세요.`;
}

function buildRecommendation(
  tableName: string,
  columns: string[],
  rowCount: number,
  estimatedDistinct: number,
): IndexRecommendation {
  const ratio = calculateCardinalityRatio(rowCount, estimatedDistinct);
  const strength = classifyCardinality(ratio);
  return {
    index_name: buildIndexName(tableName, columns),
    columns,
    access_method: "btree",
    estimated_distinct: Math.round(estimatedDistinct),
    cardinality_ratio: ratio,
    strength,
    reason: reasonFor(strength, ratio, columns.length),
    source: "cardinality-wizard",
  };
}

export function buildIndexRecommendations({
  tableName,
  rowCount,
  columns,
}: BuildRecommendationInput): IndexRecommendation[] {
  if (rowCount === null || rowCount <= 0) return [];

  const selected = columns
    .filter(
      (column) =>
        column.isSelected &&
        column.distinctCount !== null &&
        column.distinctCount > 0,
    )
    .map((column) => ({
      ...column,
      // The filter above establishes a positive, non-null distinct count.
      distinctCount: Math.min(column.distinctCount!, rowCount),
    }));

  const recommendations = selected.map((column) =>
    buildRecommendation(
      tableName,
      [column.columnName],
      rowCount,
      column.distinctCount,
    ),
  );

  if (selected.length > 1) {
    const combinedDistinct = Math.min(
      rowCount,
      selected.reduce(
        (acc, column) => acc * Math.max(1, column.distinctCount),
        1,
      ),
    );
    recommendations.unshift(
      buildRecommendation(
        tableName,
        selected.map((column) => column.columnName),
        rowCount,
        combinedDistinct,
      ),
    );
  }

  const rank: Record<CardinalityStrength, number> = {
    recommended: 0,
    consider: 1,
    skip: 2,
  };
  return recommendations.sort((a, b) => {
    const strengthOrder = rank[a.strength] - rank[b.strength];
    if (strengthOrder !== 0) return strengthOrder;
    return b.cardinality_ratio - a.cardinality_ratio;
  });
}

export function parsePositiveInteger(value: string): number | null {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) return null;
  return parsed;
}
