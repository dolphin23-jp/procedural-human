import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

test('TASK-056/057 imaging contracts enforce spaces, units and directions without DOM or adapter types', () => {
  const program = ts.createProgram(['tests/types/imaging-contract.ts'], {
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
      .map((d) => ts.flattenDiagnosticMessageText(d.messageText, '\n')),
    [],
  );
  const paths = program.getSourceFiles().map((f) => f.fileName);
  assert.equal(
    paths.some((p) =>
      /cornerstone|rendering-three|@types\/react|lib\.dom/.test(p),
    ),
    false,
  );
});
