import { readFile } from "node:fs/promises";

const projectRoot = new URL("../", import.meta.url);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const [packageJson, lockFile, notices] = await Promise.all([
  readFile(new URL("package.json", projectRoot), "utf8").then(JSON.parse),
  readFile(new URL("package-lock.json", projectRoot), "utf8").then(JSON.parse),
  readFile(new URL("THIRD_PARTY_NOTICES.md", projectRoot), "utf8"),
]);

const expectedDagreVersion = "3.1.0";
const expectedGraphlibVersion = "4.0.3";
const dagrePath = "node_modules/@dagrejs/dagre";
const graphlibPath = "node_modules/@dagrejs/graphlib";
const rootPackage = lockFile.packages?.[""];
const lockedDagre = lockFile.packages?.[dagrePath];
const lockedGraphlib = lockFile.packages?.[graphlibPath];

assert(
  packageJson.dependencies?.["@dagrejs/dagre"] === expectedDagreVersion,
  `package.json must pin @dagrejs/dagre exactly to ${expectedDagreVersion}`,
);
assert(
  rootPackage?.dependencies?.["@dagrejs/dagre"] === expectedDagreVersion,
  `package-lock root must pin @dagrejs/dagre exactly to ${expectedDagreVersion}`,
);
assert(
  lockedDagre?.version === expectedDagreVersion,
  `locked @dagrejs/dagre version must be ${expectedDagreVersion}`,
);
assert(lockedDagre?.license === "MIT", "locked @dagrejs/dagre license must be MIT");
assert(
  JSON.stringify(lockedDagre?.dependencies ?? {}) ===
    JSON.stringify({ "@dagrejs/graphlib": expectedGraphlibVersion }),
  "@dagrejs/dagre must have exactly one reviewed runtime dependency: @dagrejs/graphlib 4.0.3",
);
assert(
  lockedGraphlib?.version === expectedGraphlibVersion,
  `locked @dagrejs/graphlib version must be ${expectedGraphlibVersion}`,
);
assert(
  lockedGraphlib?.license === "MIT",
  "locked @dagrejs/graphlib license must be MIT",
);
assert(
  Object.keys(lockedGraphlib?.dependencies ?? {}).length === 0,
  "@dagrejs/graphlib must not add an unreviewed runtime dependency",
);

for (const requiredNotice of [
  "## @dagrejs/dagre 3.1.0",
  "## @dagrejs/graphlib 4.0.3",
  "Copyright (c) 2012-2014 Chris Pettitt",
  "The above copyright notice and this permission notice shall be included",
]) {
  assert(
    notices.includes(requiredNotice),
    `THIRD_PARTY_NOTICES.md is missing required text: ${requiredNotice}`,
  );
}

console.log(
  "Verified commercial-use layout boundary: @dagrejs/dagre 3.1.0 + @dagrejs/graphlib 4.0.3, both MIT.",
);
