import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const stylesheet = readFileSync(
  new URL('../src/styles.css', import.meta.url),
  'utf8',
);

test('focused index names reveal complete text with a visible outline', () => {
  const match = stylesheet.match(
    /\.tableNode__indexName:focus-visible\s*\{([^}]*)\}/,
  );

  assert.ok(match, 'missing .tableNode__indexName:focus-visible rule');
  const declarations = match[1];
  assert.match(declarations, /overflow:\s*visible;/);
  assert.match(declarations, /text-overflow:\s*clip;/);
  assert.match(declarations, /white-space:\s*normal;/);
  assert.match(
    declarations,
    /outline:\s*3px solid var\(--color-brand\);/,
  );
});
