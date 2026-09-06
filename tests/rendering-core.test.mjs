import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';
import { opacity } from '../packages/rendering-core/dist/index.js';

test('TASK-045 opacity accepts endpoints and rejects invalid alpha without clamping', () => {
  for (const value of [0, 0.25, 1]) assert.equal(opacity(value), value);
  for (const value of [-0.01, 1.01, NaN, Infinity, -Infinity]) {
    assert.throws(() => opacity(value), {
      name: 'RangeError',
      message: 'Opacity must be a finite number between 0 and 1.',
    });
  }
});

test('TASK-045 presentation contracts preserve IDs, spaces and units without DOM types', () => {
  const program = ts.createProgram(['tests/types/rendering-core-contract.ts'], {
    noEmit: true,
    strict: true,
    skipLibCheck: true,
    lib: ['lib.es2022.d.ts'],
    types: [],
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
  });
  assert.deepEqual(
    ts
      .getPreEmitDiagnostics(program)
      .map((diagnostic) =>
        ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'),
      ),
    [],
  );
});
