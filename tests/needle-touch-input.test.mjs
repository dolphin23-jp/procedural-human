import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const touchAdapter = readFileSync(
  new URL('../apps/web/src/needle-touch-pencil-input.ts', import.meta.url),
  'utf8',
);
const app = readFileSync(
  new URL('../apps/web/src/App.tsx', import.meta.url),
  'utf8',
);
const css = readFileSync(
  new URL('../apps/web/src/styles.css', import.meta.url),
  'utf8',
);

test('TASK-070 touch/Pencil adapter accepts touch and pen pointer input without pressure dependency', () => {
  assert.match(touchAdapter, /pointerType === 'touch'/);
  assert.match(touchAdapter, /pointerType === 'pen'/);
  assert.doesNotMatch(touchAdapter, /event\.pressure|\.pressure\b/);
  assert.match(touchAdapter, /event\.isPrimary/);
});

test('TASK-070 keeps browser input normalized and outside instrument medical state', () => {
  assert.match(touchAdapter, /needleTranslationIntent/);
  assert.match(touchAdapter, /needleRotationIntent/);
  assert.match(touchAdapter, /needleAdvanceIntent/);
  assert.match(touchAdapter, /needleRetractIntent/);
  assert.doesNotMatch(touchAdapter, /NeedleInstance|PatientState|SpatialQuery|procedure/i);
});

test('TASK-070 exposes iPad-sized mode controls for move, rotate, and advance', () => {
  assert.match(app, /\['translate', 'Move'\]/);
  assert.match(app, /\['rotate', 'Rotate'\]/);
  assert.match(app, /\['advance', 'Advance'\]/);
  assert.match(
    css,
    /\.needle-control__modes button\s*\{[^}]*min-height:\s*44px/s,
  );
  assert.match(
    css,
    /\.viewer__needle-control\s*\{[^}]*touch-action:\s*none/s,
  );
});
