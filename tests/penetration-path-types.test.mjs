import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

test('TASK-042 compile-time contract preserves patient space, Length and distinct semantic ID brands', () => {
  const program = ts.createProgram(
    ['tests/types/penetration-path-contract.ts'],
    {
      noEmit: true,
      strict: true,
      skipLibCheck: true,
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
    },
  );
  assert.deepEqual(
    ts
      .getPreEmitDiagnostics(program)
      .map((d) => ts.flattenDiagnosticMessageText(d.messageText, '\n')),
    [],
  );
});
