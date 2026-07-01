import { describe, expect, it } from "vitest";

import {
  buildIndexName,
  buildIndexRecommendations,
  calculateCardinalityRatio,
  classifyCardinality,
  parsePositiveInteger,
} from "../cardinality";

describe("calculateCardinalityRatio", () => {
  it("calculates normal ratios", () => {
    expect(calculateCardinalityRatio(100, 20)).toBe(0.2);
    expect(calculateCardinalityRatio(100, 50)).toBe(0.5);
    expect(calculateCardinalityRatio(100, 100)).toBe(1);
  });

  it("returns 0 for zero, negative, and non-finite inputs", () => {
    expect(calculateCardinalityRatio(0, 10)).toBe(0);
    expect(calculateCardinalityRatio(100, 0)).toBe(0);
    expect(calculateCardinalityRatio(-100, 10)).toBe(0);
    expect(calculateCardinalityRatio(100, -10)).toBe(0);
    expect(calculateCardinalityRatio(Infinity, 10)).toBe(0);
    expect(calculateCardinalityRatio(10, Infinity)).toBe(0);
    expect(calculateCardinalityRatio(10, Number.NaN)).toBe(0);
  });

  it("clamps ratios greater than 1", () => {
    expect(calculateCardinalityRatio(100, 150)).toBe(1);
  });
});

describe("classifyCardinality", () => {
  it("classifies recommended ratios", () => {
    expect(classifyCardinality(0.2)).toBe("recommended");
    expect(classifyCardinality(0.5)).toBe("recommended");
    expect(classifyCardinality(1)).toBe("recommended");
  });

  it("classifies ratios that should be considered", () => {
    expect(classifyCardinality(0.05)).toBe("consider");
    expect(classifyCardinality(0.1)).toBe("consider");
    expect(classifyCardinality(0.199)).toBe("consider");
  });

  it("classifies low ratios as skip", () => {
    expect(classifyCardinality(0.049)).toBe("skip");
    expect(classifyCardinality(0.01)).toBe("skip");
    expect(classifyCardinality(0)).toBe("skip");
  });
});

describe("buildIndexName", () => {
  it("builds deterministic names from table and column identifiers", () => {
    expect(buildIndexName("users", ["email"])).toBe("idx_users_email");
    expect(buildIndexName("public.users", ["first_name", "last_name"])).toBe(
      "idx_users_first_name_last_name",
    );
  });

  it("sanitizes empty and unsafe identifier parts", () => {
    expect(buildIndexName("", [])).toBe("idx_col_");
    expect(buildIndexName(".", ["col"])).toBe("idx_col_col");
    expect(buildIndexName("!!", ["$$"])).toBe("idx_col_col");
    expect(buildIndexName("my-table", ["my-col!"])).toBe("idx_my_table_my_col");
    expect(buildIndexName('table"', ["'col'"])).toBe("idx_table_col");
  });

  it("truncates names to the PostgreSQL identifier limit", () => {
    const indexName = buildIndexName(
      "this_is_a_very_long_table_name_that_exceeds_the_limit",
      ["and_this_is_a_very_long_column_name_that_also_exceeds_the_limit"],
    );

    expect(indexName.length).toBeLessThanOrEqual(63);
    expect(indexName).toBe(
      "idx_this_is_a_very_long_table_name_that_exceeds_the_limit_and_t",
    );
  });
});

describe("parsePositiveInteger", () => {
  it("parses positive integers", () => {
    expect(parsePositiveInteger("123")).toBe(123);
    expect(parsePositiveInteger("1")).toBe(1);
  });

  it("handles spaces and leading zeros", () => {
    expect(parsePositiveInteger("   123   ")).toBe(123);
    expect(parsePositiveInteger("0123")).toBe(123);
  });

  it("rejects invalid, fractional, and non-positive values", () => {
    expect(parsePositiveInteger("0")).toBeNull();
    expect(parsePositiveInteger("-5")).toBeNull();
    expect(parsePositiveInteger("12.3")).toBeNull();
    expect(parsePositiveInteger("abc")).toBeNull();
    expect(parsePositiveInteger("")).toBeNull();
    expect(parsePositiveInteger("   ")).toBeNull();
  });

  it("rejects NaN and Infinity", () => {
    expect(parsePositiveInteger("NaN")).toBeNull();
    expect(parsePositiveInteger("Infinity")).toBeNull();
    expect(parsePositiveInteger("-Infinity")).toBeNull();
  });

  it("parses valid scientific notation as positive integers", () => {
    expect(parsePositiveInteger("1e3")).toBe(1000);
  });

  it("rejects strings mixing numbers and characters", () => {
    expect(parsePositiveInteger("123abc")).toBeNull();
    expect(parsePositiveInteger("abc123")).toBeNull();
    expect(parsePositiveInteger("123 456")).toBeNull();
  });
});

describe("buildIndexRecommendations", () => {
  it("returns no recommendations without a positive row count", () => {
    expect(
      buildIndexRecommendations({
        tableName: "t",
        rowCount: null,
        columns: [],
      }),
    ).toEqual([]);
    expect(
      buildIndexRecommendations({ tableName: "t", rowCount: 0, columns: [] }),
    ).toEqual([]);
  });

  it("builds sorted recommendations for selected columns", () => {
    const recommendations = buildIndexRecommendations({
      tableName: "users",
      rowCount: 1000,
      columns: [
        { columnName: "id", isSelected: true, distinctCount: 1000 },
        { columnName: "status", isSelected: true, distinctCount: 5 },
        { columnName: "unselected", isSelected: false, distinctCount: 100 },
        { columnName: "null_distinct", isSelected: true, distinctCount: null },
      ],
    });

    expect(recommendations).toHaveLength(3);
    expect(recommendations[0]).toMatchObject({
      columns: ["id", "status"],
      estimated_distinct: 1000,
      cardinality_ratio: 1,
      strength: "recommended",
    });
    expect(recommendations[1]).toMatchObject({
      columns: ["id"],
      estimated_distinct: 1000,
    });
    expect(recommendations[2]).toMatchObject({
      columns: ["status"],
      estimated_distinct: 5,
      strength: "skip",
    });
  });

  it("covers consider and skip recommendation reasons", () => {
    const consider = buildIndexRecommendations({
      tableName: "users",
      rowCount: 100,
      columns: [{ columnName: "status", isSelected: true, distinctCount: 10 }],
    });
    const skipCombination = buildIndexRecommendations({
      tableName: "users",
      rowCount: 1000,
      columns: [
        { columnName: "status", isSelected: true, distinctCount: 2 },
        { columnName: "type", isSelected: true, distinctCount: 2 },
      ],
    });

    expect(consider[0].strength).toBe("consider");
    expect(consider[0].reason).toContain("검토하세요");
    expect(skipCombination[0].strength).toBe("skip");
    expect(skipCombination[0].reason).toContain(
      "단독 컬럼 조합 인덱스는 보류하세요",
    );
  });

  it("uses cardinality ratio as a fallback sort key within the same strength", () => {
    const recommendations = buildIndexRecommendations({
      tableName: "users",
      rowCount: 1000,
      columns: [
        { columnName: "status", isSelected: true, distinctCount: 100 },
        { columnName: "type", isSelected: true, distinctCount: 150 },
      ],
    });

    expect(recommendations[1].columns).toEqual(["type"]);
    expect(recommendations[2].columns).toEqual(["status"]);
  });

  it("clamps combined distinct estimates to the row count", () => {
    const recommendations = buildIndexRecommendations({
      tableName: "users",
      rowCount: 100,
      columns: [
        { columnName: "status", isSelected: true, distinctCount: 20 },
        { columnName: "type", isSelected: true, distinctCount: 20 },
      ],
    });

    expect(recommendations[0]).toMatchObject({
      columns: ["status", "type"],
      estimated_distinct: 100,
      cardinality_ratio: 1,
    });
  });

  it("ignores columns without usable distinct counts", () => {
    expect(
      buildIndexRecommendations({
        tableName: "users",
        rowCount: 100,
        columns: [
          { columnName: "negative", isSelected: true, distinctCount: -10 },
          { columnName: "missing", isSelected: true, distinctCount: null },
        ],
      }),
    ).toEqual([]);
  });
});
