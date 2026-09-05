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

test('anatomy rejects workspace dependencies above core, units, and math', async () => {
  const rootDir = await mkdtemp(
    path.join(os.tmpdir(), 'procedural-human-boundary-'),
  );
  const anatomySourceDir = path.join(rootDir, 'packages', 'anatomy', 'src');

  try {
    await mkdir(anatomySourceDir, { recursive: true });
    const violationPath = path.join(anatomySourceDir, 'violation.ts');
    await writeFile(
      violationPath,
      "import '@procedural-human/patient';\n",
      'utf8',
    );

    const violations = await checkPackageBoundaries(rootDir);
    assert.equal(violations.length, 1);
    assert.match(violations[0] ?? '', /anatomy may only depend/);

    await rm(violationPath);
    assert.deepEqual(await checkPackageBoundaries(rootDir), []);
  } finally {
    await rm(rootDir, { recursive: true, force: true });
  }
});

test('patient must not reverse-depend on spatial', async () => {
  const rootDir = await mkdtemp(
    path.join(os.tmpdir(), 'procedural-human-boundary-'),
  );
  const patientSourceDir = path.join(rootDir, 'packages', 'patient', 'src');

  try {
    await mkdir(patientSourceDir, { recursive: true });
    const violationPath = path.join(patientSourceDir, 'violation.ts');
    await writeFile(
      violationPath,
      "import '@procedural-human/spatial';\n",
      'utf8',
    );

    const violations = await checkPackageBoundaries(rootDir);
    assert.equal(violations.length, 1);
    assert.match(
      violations[0] ?? '',
      /patient.*must not depend on.*spatial/,
    );
  } finally {
    await rm(rootDir, { recursive: true, force: true });
  }
});
