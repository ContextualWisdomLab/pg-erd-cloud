import assert from "node:assert/strict";
import test from "node:test";

import { noticesAreByteIdentical } from "./notice-byte-identity.mjs";

test("rejects distinct notice bytes that decode to the same replacement characters", () => {
  const malformedUtf8 = Buffer.from([0xc0, 0x80]);
  const replacementCharacters = Buffer.from([
    0xef,
    0xbf,
    0xbd,
    0xef,
    0xbf,
    0xbd,
  ]);

  assert.equal(
    malformedUtf8.toString("utf8"),
    replacementCharacters.toString("utf8"),
  );
  assert.equal(noticesAreByteIdentical(malformedUtf8, replacementCharacters), false);
});

test("accepts only byte-identical notice buffers", () => {
  const reviewedNotice = Buffer.from("MIT notice\n", "utf8");

  assert.equal(noticesAreByteIdentical(reviewedNotice, Buffer.from(reviewedNotice)), true);
});
