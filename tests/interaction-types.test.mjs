import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

test('TASK-071 Interaction API preserves needle identity and Patient Space', () => {
  const program = ts.createProgram(['tests/types/interaction-contract.ts'], {
    noEmit: true,
    lib: ['lib.es2022.d.ts'],
    strict: true,
    skipLibCheck: true,
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
