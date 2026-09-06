import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

test('TASK-043 compile-time public Spatial API preserves patient space and semantic IDs', () => {
  const program = ts.createProgram(
    ['tests/types/spatial-public-api-contract.ts'],
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
      .map((diagnostic) =>
        ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'),
      ),
    [],
  );
});
