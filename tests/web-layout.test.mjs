import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const css = readFileSync(
  new URL('../apps/web/src/styles.css', import.meta.url),
  'utf8',
);

test('TASK-064 keeps narrow screens single-column and uses side-by-side layout on wide screens', () => {
  assert.match(
    css,
    /\.shell\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s,
  );
  assert.match(
    css,
    /@media \(min-width: 980px\)\s*\{[\s\S]*?\.shell\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1\.35fr\) minmax\(360px, 0\.85fr\)/,
  );
  assert.match(
    css,
    /@media \(min-width: 980px\)[\s\S]*?\.imaging__viewport\s*\{[^}]*height:\s*auto;[^}]*min-height:\s*320px/,
  );
});
