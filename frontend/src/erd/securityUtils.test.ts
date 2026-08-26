import { describe, it, expect } from "vitest";
import { sanitizeTableName } from "./securityUtils";

describe("sanitizeTableName", () => {
  it("should keep alphanumeric characters and underscores", () => {
    expect(sanitizeTableName("Users_Table_123")).toBe("Users_Table_123");
  });

  it("should remove spaces", () => {
    expect(sanitizeTableName("My Table Name")).toBe("MyTableName");
  });

  it("should remove special characters", () => {
    expect(sanitizeTableName("Table!@#$%^&*()-=Name")).toBe("TableName");
    expect(sanitizeTableName("Drop Table;--")).toBe("DropTable");
    expect(sanitizeTableName("<script>alert(1)</script>")).toBe("scriptalert1script");
  });

  it("should remove unicode/emojis", () => {
    expect(sanitizeTableName("Table_🌟")).toBe("Table_");
    expect(sanitizeTableName("사용자")).toBe("");
  });

  it("should handle empty strings", () => {
    expect(sanitizeTableName("")).toBe("");
  });

  it("should handle strings with only special characters", () => {
    expect(sanitizeTableName("!!!***@@@")).toBe("");
  });
});
