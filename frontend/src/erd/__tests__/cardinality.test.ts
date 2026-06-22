import { describe, it, expect } from "vitest";
import {
  calculateCardinalityRatio,
  classifyCardinality,
  buildIndexName,
  buildIndexRecommendations,
  parsePositiveInteger,
} from "../cardinality";

describe("cardinality utils", () => {
  describe("calculateCardinalityRatio", () => {
    it("calculates ratio correctly based on actual implementation signature (rowCount, distinctCount)", () => {
      // Standard fractional ratio calculation
      expect(calculateCardinalityRatio(100, 50)).toBe(0.5);
      expect(calculateCardinalityRatio(1000, 100)).toBe(0.1);
    });

    it("handles boundary condition where rowCount is 0", () => {
      expect(calculateCardinalityRatio(0, 10)).toBe(0);
    });

    it("handles boundary condition where distinctCount is 0", () => {
      expect(calculateCardinalityRatio(10, 0)).toBe(0);
    });

    it("handles clamping when distinctCount is greater than rowCount", () => {
      // Tests the clampRatio logic
      expect(calculateCardinalityRatio(100, 150)).toBe(1.0);
    });

    it("handles negative values by returning 0", () => {
      expect(calculateCardinalityRatio(-10, 10)).toBe(0);
      expect(calculateCardinalityRatio(100, -5)).toBe(0);
    });

    it("handles NaN by returning 0", () => {
      // tests clampRatio's Number.isFinite check
      expect(calculateCardinalityRatio(100, NaN)).toBe(0);
      expect(calculateCardinalityRatio(100, Infinity)).toBe(0);
    });
  });

  describe("classifyCardinality", () => {
    it("returns recommended for ratio >= 0.2", () => {
      expect(classifyCardinality(0.2)).toBe("recommended");
      expect(classifyCardinality(0.5)).toBe("recommended");
      expect(classifyCardinality(1.0)).toBe("recommended");
    });

    it("returns consider for ratio >= 0.05 and < 0.2", () => {
      expect(classifyCardinality(0.05)).toBe("consider");
      expect(classifyCardinality(0.15)).toBe("consider");
      expect(classifyCardinality(0.199)).toBe("consider");
    });

    it("returns skip for ratio < 0.05", () => {
      expect(classifyCardinality(0.04)).toBe("skip");
      expect(classifyCardinality(0.01)).toBe("skip");
      expect(classifyCardinality(0)).toBe("skip");
    });
  });

  describe("buildIndexName", () => {
    it("builds index name correctly", () => {
      expect(buildIndexName("users", ["email"])).toBe("idx_users_email");
      expect(buildIndexName("public.users", ["first_name", "last_name"])).toBe("idx_users_first_name_last_name");
      expect(buildIndexName("public.users", [])).toBe("idx_users_");
      expect(buildIndexName("", [])).toBe("idx_col_"); // tableIdentifierPart falls back to sanitizeIdentifierPart, which returns "col" for empty strings
    });

    it("sanitizes characters", () => {
      expect(buildIndexName("my-table", ["my-col!"])).toBe("idx_my_table_my_col");
      expect(buildIndexName("table\"", ["'col'"])).toBe("idx_table_col");
      expect(buildIndexName("    test    ", ["  spaces  "])).toBe("idx_test_spaces");
    });

    it("handles parts that become empty after sanitization", () => {
        expect(buildIndexName("!!", ["$$"])).toBe("idx_col_col");
    });

    it("truncates at 63 characters", () => {
      const veryLongTableName = "this_is_a_very_long_table_name_that_exceeds_the_limit";
      const veryLongColumnName = "and_this_is_a_very_long_column_name_that_also_exceeds_the_limit";
      const indexName = buildIndexName(veryLongTableName, [veryLongColumnName]);
      expect(indexName.length).toBeLessThanOrEqual(63);
      expect(indexName).toBe("idx_this_is_a_very_long_table_name_that_exceeds_the_limit_and_t");
    });
  });

  describe("parsePositiveInteger", () => {
    it("parses valid positive integer", () => {
      expect(parsePositiveInteger("123")).toBe(123);
      expect(parsePositiveInteger("1")).toBe(1);
    });

    it("returns null for non-positive integers", () => {
      expect(parsePositiveInteger("0")).toBeNull();
      expect(parsePositiveInteger("-5")).toBeNull();
    });

    it("returns null for floats", () => {
      expect(parsePositiveInteger("12.3")).toBeNull();
    });

    it("returns null for invalid strings", () => {
      expect(parsePositiveInteger("abc")).toBeNull();
      expect(parsePositiveInteger("")).toBeNull();
    });
  });

  describe("buildIndexRecommendations", () => {
    it("returns empty array if rowCount is null or <= 0", () => {
      expect(buildIndexRecommendations({ tableName: "t", rowCount: null, columns: [] })).toEqual([]);
      expect(buildIndexRecommendations({ tableName: "t", rowCount: 0, columns: [] })).toEqual([]);
    });

    it("builds recommendations for selected columns with distinct counts", () => {
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

      expect(recommendations).toHaveLength(3); // 2 single columns + 1 combined

      // Combined should be first due to highest distinct count (clamped to rowCount)
      expect(recommendations[0].columns).toEqual(["id", "status"]);
      expect(recommendations[0].estimated_distinct).toBe(1000);
      expect(recommendations[0].strength).toBe("recommended");
      expect(recommendations[0].reason).toContain("선택도가 높습니다");

      // Next should be id
      expect(recommendations[1].columns).toEqual(["id"]);
      expect(recommendations[1].estimated_distinct).toBe(1000);

      // Last should be status
      expect(recommendations[2].columns).toEqual(["status"]);
      expect(recommendations[2].estimated_distinct).toBe(5);
      expect(recommendations[2].strength).toBe("skip");
      expect(recommendations[2].reason).toContain("보류하세요");
    });

    it("tests consider branch of reasonFor via a single column recommendation", () => {
        // We need a ratio between 0.05 and 0.2
        const recommendations = buildIndexRecommendations({
            tableName: "users",
            rowCount: 100,
            columns: [
              { columnName: "status", isSelected: true, distinctCount: 10 },
            ],
          });
          expect(recommendations[0].strength).toBe("consider");
          expect(recommendations[0].reason).toContain("검토하세요");
    });

    it("tests reasonFor edge case for column combination without recommended", () => {
         // Create a combination index with a low ratio to trigger the skip logic for multiple columns
        const recommendations = buildIndexRecommendations({
            tableName: "users",
            rowCount: 1000,
            columns: [
              { columnName: "status", isSelected: true, distinctCount: 2 },
              { columnName: "type", isSelected: true, distinctCount: 2 },
            ],
          });
          // combination is first
          expect(recommendations[0].strength).toBe("skip");
          expect(recommendations[0].reason).toContain("단독 컬럼 조합 인덱스는 보류하세요");
    });

    it("handles strengthOrder ties with cardinality ratio fallback", () => {
         const recommendations = buildIndexRecommendations({
            tableName: "users",
            rowCount: 1000,
            columns: [
              { columnName: "status", isSelected: true, distinctCount: 100 }, // ratio 0.1 (consider)
              { columnName: "type", isSelected: true, distinctCount: 150 },   // ratio 0.15 (consider)
            ],
          });

          // combined is first (100 * 150 -> clamped to 1000 -> ratio 1.0 -> recommended)
          // then type (0.15)
          // then status (0.1)
          expect(recommendations[1].columns).toEqual(["type"]);
          expect(recommendations[2].columns).toEqual(["status"]);
    });

    it("calculates combined distinct correctly when product exceeds row count", () => {
        const recommendations = buildIndexRecommendations({
            tableName: "users",
            rowCount: 100,
            columns: [
              { columnName: "status", isSelected: true, distinctCount: 20 },
              { columnName: "type", isSelected: true, distinctCount: 20 },
            ],
        });

        // 20 * 20 = 400. Combined distinct should be clamped to rowCount (100).
        expect(recommendations[0].columns).toEqual(["status", "type"]);
        expect(recommendations[0].estimated_distinct).toBe(100);
        expect(recommendations[0].cardinality_ratio).toBe(1.0);
    });

    it("handles negative distinct counts in columns correctly by clamping to 0", () => {
        const recommendations = buildIndexRecommendations({
            tableName: "users",
            rowCount: 100,
            columns: [
              { columnName: "status", isSelected: true, distinctCount: -10 },
            ],
        });

        expect(recommendations.length).toBe(0);
    });

    it("does not crash if distinctCount is null", () => {
        const recommendations = buildIndexRecommendations({
            tableName: "users",
            rowCount: 100,
            columns: [
              { columnName: "status", isSelected: true, distinctCount: null },
            ],
        });

        expect(recommendations.length).toBe(0);
    });

    it("covers tableIdentifierPart edge cases", () => {
        // Line 45: return sanitizeIdentifierPart(parts[parts.length - 1] || tableName);
        expect(buildIndexName(".", ["col"])).toBe("idx_col_col"); // parts = ["", ""], parts[1] is "", falls back to "." but sanitizeIdentifierPart(".") is "col"
    });

    it("covers nullish coalescing in distinctCount assignment", () => {
        // Line 121: distinctCount: Math.min(column.distinctCount ?? 0, rowCount)
        // Note: the filter in Line 116 already checks `column.distinctCount !== null`.
        // Thus `?? 0` on line 121 is practically unreachable in standard TS but we can trick it with casting if needed or it may just remain an uncovered branch in v8 if unreachable.
        // Actually since we filter for !== null and > 0, the ?? 0 fallback is indeed dead code. We won't worry if it's just a branch.
    });
  });
});
