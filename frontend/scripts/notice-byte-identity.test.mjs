import { describe, expect, it } from "vitest";

import { noticesAreByteIdentical } from "./notice-byte-identity.mjs";

describe("third-party notice byte identity", () => {
  it("rejects distinct notice bytes that decode to the same replacement characters", () => {
    const malformedUtf8 = Buffer.from([0xc0, 0x80]);
    const replacementCharacters = Buffer.from([
      0xef,
      0xbf,
      0xbd,
      0xef,
      0xbf,
      0xbd,
    ]);

    expect(malformedUtf8.toString("utf8")).toBe(
      replacementCharacters.toString("utf8"),
    );
    expect(noticesAreByteIdentical(malformedUtf8, replacementCharacters)).toBe(false);
  });

  it("accepts only byte-identical notice buffers", () => {
    const reviewedNotice = Buffer.from("MIT notice\n", "utf8");

    expect(noticesAreByteIdentical(reviewedNotice, Buffer.from(reviewedNotice))).toBe(true);
  });
});
