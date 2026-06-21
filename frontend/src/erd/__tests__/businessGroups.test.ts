import { describe, expect, it, vi } from "vitest";
import {
  BUSINESS_GROUP_COLORS,
  DEFAULT_BUSINESS_GROUP_COLOR,
  normalizeBusinessGroupColor,
  buildBusinessGroupId,
  uniqueBusinessGroupId,
  BusinessGroup,
} from "../businessGroups";

describe("normalizeBusinessGroupColor", () => {
  it("should return DEFAULT_BUSINESS_GROUP_COLOR for null", () => {
    expect(normalizeBusinessGroupColor(null)).toBe(DEFAULT_BUSINESS_GROUP_COLOR);
  });

  it("should return DEFAULT_BUSINESS_GROUP_COLOR for undefined", () => {
    expect(normalizeBusinessGroupColor(undefined)).toBe(DEFAULT_BUSINESS_GROUP_COLOR);
  });

  it("should return DEFAULT_BUSINESS_GROUP_COLOR for invalid colors", () => {
    expect(normalizeBusinessGroupColor("")).toBe(DEFAULT_BUSINESS_GROUP_COLOR);
    expect(normalizeBusinessGroupColor("#ffffff")).toBe(DEFAULT_BUSINESS_GROUP_COLOR);
    expect(normalizeBusinessGroupColor("invalid")).toBe(DEFAULT_BUSINESS_GROUP_COLOR);
  });

  it("should return the exact color back for valid colors", () => {
    BUSINESS_GROUP_COLORS.forEach((color) => {
      expect(normalizeBusinessGroupColor(color)).toBe(color);
    });
  });
});

describe("buildBusinessGroupId", () => {
  it("should normalize string names", () => {
    expect(buildBusinessGroupId("Sales Team")).toBe("group_sales_team");
    expect(buildBusinessGroupId("  Marketing  ")).toBe("group_marketing");
    expect(buildBusinessGroupId("HR & Ops")).toBe("group_hr_ops");
    expect(buildBusinessGroupId("Tech-Support_1")).toBe("group_tech_support_1");
  });

  it("should support korean names", () => {
    expect(buildBusinessGroupId("개발팀")).toBe("group_개발팀");
  });

  it("should generate a fallback ID when only special chars are provided", () => {
    const mockDateNow = vi.spyOn(Date, "now").mockReturnValue(1234567890);
    expect(buildBusinessGroupId(" !@#$% ")).toBe("group_1234567890");
    mockDateNow.mockRestore();
  });
});

describe("uniqueBusinessGroupId", () => {
  it("should return the base ID when it does not exist", () => {
    const existingGroups: BusinessGroup[] = [];
    expect(uniqueBusinessGroupId("Sales", existingGroups)).toBe("group_sales");
  });

  it("should append a suffix when base ID exists", () => {
    const existingGroups: BusinessGroup[] = [
      { id: "group_sales", name: "Sales", color: "#000" },
    ];
    expect(uniqueBusinessGroupId("Sales", existingGroups)).toBe("group_sales_2");
  });

  it("should increment suffix until an available ID is found", () => {
    const existingGroups: BusinessGroup[] = [
      { id: "group_sales", name: "Sales 1", color: "#000" },
      { id: "group_sales_2", name: "Sales 2", color: "#000" },
      { id: "group_sales_3", name: "Sales 3", color: "#000" },
    ];
    expect(uniqueBusinessGroupId("Sales", existingGroups)).toBe("group_sales_4");
  });
});
