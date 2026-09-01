import { readFile } from "node:fs/promises";

import { noticesAreByteIdentical } from "./notice-byte-identity.mjs";

const projectRoot = new URL("../", import.meta.url);
const [sourceNotice, distributedNotice] = await Promise.all([
  readFile(new URL("THIRD_PARTY_NOTICES.md", projectRoot)),
  readFile(new URL("dist/THIRD_PARTY_NOTICES.md", projectRoot)),
]);

if (!noticesAreByteIdentical(sourceNotice, distributedNotice)) {
  throw new Error(
    "The production build must distribute the exact reviewed THIRD_PARTY_NOTICES.md file.",
  );
}

console.log(
  "Verified production distribution contains the exact reviewed third-party notices.",
);
