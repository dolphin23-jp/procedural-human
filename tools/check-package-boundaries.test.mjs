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
    assert.match(violations[0] ?? '', /patient.*must not depend on.*spatial/);
  } finally {
    await rm(rootDir, { recursive: true, force: true });
  }
});

test('spatial rejects renderer and higher-level workspace dependencies', async () => {
  const rootDir = await mkdtemp(
    path.join(os.tmpdir(), 'procedural-human-boundary-'),
  );
  const spatialSourceDir = path.join(rootDir, 'packages', 'spatial', 'src');

  try {
    await mkdir(spatialSourceDir, { recursive: true });
    const violationPath = path.join(spatialSourceDir, 'violation.ts');
    await writeFile(
      violationPath,
      "import '@procedural-human/rendering-three';\n",
      'utf8',
    );

    const violations = await checkPackageBoundaries(rootDir);
    assert.equal(violations.length, 1);
    assert.match(violations[0] ?? '', /spatial may only depend/);
  } finally {
    await rm(rootDir, { recursive: true, force: true });
  }
});

test('TASK-056 imaging core cannot depend on rendering/session or leak Three/Cornerstone/React', async () => {
  const rootDir = await mkdtemp(
    path.join(os.tmpdir(), 'procedural-human-imaging-boundary-'),
  );
  try {
    for (const [owner, target] of [
      ['imaging-core', '@procedural-human/rendering-core'],
      ['imaging-core', '@procedural-human/session'],
      ['imaging-core', 'three'],
      ['imaging-core', '@cornerstonejs/core'],
      ['imaging-core', 'react'],
      ['rendering-core', '@procedural-human/imaging-core'],
      ['rendering-core', '@procedural-human/session'],
    ]) {
      const dir = path.join(rootDir, 'packages', owner, 'src');
      await mkdir(dir, { recursive: true });
      const file = path.join(dir, 'violation.ts');
      await writeFile(file, `export * from '${target}';\n`);
      assert.equal(
        (await checkPackageBoundaries(rootDir)).length,
        1,
        `${owner} -> ${target}`,
      );
      await rm(file);
    }
  } finally {
    await rm(rootDir, { recursive: true, force: true });
  }
});

test('TASK-071 enforces Interaction direction and public domain imports', async () => {
  const rootDir = await mkdtemp(
    path.join(os.tmpdir(), 'procedural-human-interaction-boundary-'),
  );
  try {
    for (const [owner, target] of [
      ['interaction', '@procedural-human/procedures'],
      ['interaction', '@procedural-human/rendering-core'],
      ['interaction', '@procedural-human/rendering-three'],
      ['interaction', '@procedural-human/session'],
      ['interaction', '@procedural-human/event-log'],
      ['interaction', 'react'],
      ['interaction', 'three'],
      ['interaction', '@cornerstonejs/core'],
      ['interaction', '@procedural-human/spatial/src/index'],
      ['interaction', '../../spatial/src/index.js'],
      ['interaction', '../../../apps/web/src/needle-touch-pencil-input.js'],
      ['spatial', '@procedural-human/interaction'],
      ['instruments', '@procedural-human/interaction'],
      ['patient', '@procedural-human/interaction'],
      ['patient', '../../interaction/src/index.js'],
    ]) {
      const dir = path.join(rootDir, 'packages', owner, 'src');
      await mkdir(dir, { recursive: true });
      const file = path.join(dir, 'violation.ts');
      await writeFile(file, `export * from '${target}';\n`);
      assert.ok(
        (await checkPackageBoundaries(rootDir)).length > 0,
        `${owner} -> ${target}`,
      );
      await rm(file);
    }
    const dir = path.join(rootDir, 'packages', 'interaction', 'src');
    await writeFile(
      path.join(dir, 'allowed.ts'),
      [
        "import '@procedural-human/instruments';",
        "import type { PatientSpacePoint } from '@procedural-human/math';",
        "import '@procedural-human/spatial';",
        "export * from './local.js';",
      ].join('\n'),
    );
    assert.deepEqual(await checkPackageBoundaries(rootDir), []);
  } finally {
    await rm(rootDir, { recursive: true, force: true });
  }
});
