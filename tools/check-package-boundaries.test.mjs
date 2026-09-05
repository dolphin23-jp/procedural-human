import assert from 'node:assert/strict';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { checkPackageBoundaries } from './check-package-boundaries.mjs';

test('the repository has no package-boundary violations', async () => {
  const violations = await checkPackageBoundaries(process.cwd());
  assert.deepEqual(violations, []);
});

test('a deliberate anatomy-to-procedures fixture violation fails and passes after removal', async () => {
  const rootDir = await mkdtemp(
    path.join(os.tmpdir(), 'procedural-human-boundary-'),
  );
  const anatomySourceDir = path.join(rootDir, 'packages', 'anatomy', 'src');

  try {
    await mkdir(anatomySourceDir, { recursive: true });
    const violationPath = path.join(anatomySourceDir, 'violation.ts');
    await writeFile(
      violationPath,
      "import '@procedural-human/procedures';\n",
      'utf8',
    );

    const violations = await checkPackageBoundaries(rootDir);
    assert.equal(violations.length, 1);
    assert.match(
      violations[0] ?? '',
      /anatomy.*must not depend on.*procedures/,
    );

    await rm(violationPath);
    assert.deepEqual(await checkPackageBoundaries(rootDir), []);
  } finally {
    await rm(rootDir, { recursive: true, force: true });
  }
});
