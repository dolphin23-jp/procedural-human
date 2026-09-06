import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

// Compile real consumer declarations, including negative assertions. An unused
// @ts-expect-error is a failure, so widening Length/space/region types breaks CI.
test('TASK-039 public boundary contracts reject raw lengths and untagged/render positions', () => {
  const program = ts.createProgram(['tests/types/boundary-contract.ts'], {
    noEmit: true,
    strict: true,
    skipLibCheck: true,
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
  });
  const diagnostics = ts.getPreEmitDiagnostics(program);
  assert.deepEqual(
    diagnostics.map((d) =>
      ts.flattenDiagnosticMessageText(d.messageText, '\n'),
    ),
    [],
  );
});
