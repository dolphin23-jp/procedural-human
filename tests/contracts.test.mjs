import assert from 'node:assert/strict';
import test from 'node:test';

import {
  assetId,
  caseId,
  contentHash,
  entityId,
  patientId,
  procedureId,
  schemaVersion,
  sessionId,
  structureId,
  version,
} from '../packages/core/dist/index.js';
import {
  centimetres,
  degrees,
  kilopascals,
  litres,
  litresPerMinute,
  metres,
  metresPerSecond,
  millimetresOfMercury,
  millinewtons,
  milliseconds,
  minutes,
  toCentimetres,
  toDegrees,
  toKilopascals,
  toLitres,
  toLitresPerMinute,
  toMetres,
  toMetresPerSecond,
  toMillimetresOfMercury,
  toMillinewtons,
  toMilliseconds,
  toMinutes,
} from '../packages/units/dist/index.js';
import {
  imageVoxelCoordinate,
  patientSpacePoint,
  patientSpaceVector,
  renderSpacePoint,
  vec3,
} from '../packages/math/dist/index.js';

test('core branded contract constructors preserve supplied values', () => {
  assert.equal(entityId('entity-1'), 'entity-1');
  assert.equal(structureId('structure-1'), 'structure-1');
  assert.equal(patientId('patient-1'), 'patient-1');
  assert.equal(assetId('asset-1'), 'asset-1');
  assert.equal(procedureId('procedure-1'), 'procedure-1');
  assert.equal(caseId('case-1'), 'case-1');
  assert.equal(sessionId('session-1'), 'session-1');
  assert.equal(version('1.2.3'), '1.2.3');
  assert.equal(schemaVersion('1'), '1');
  assert.equal(contentHash('sha256:abc'), 'sha256:abc');
});

test('unit conversions round-trip through canonical representations', () => {
  assert.equal(toCentimetres(centimetres(12.5)), 12.5);
  assert.equal(toMetres(metres(1.25)), 1.25);
  assert.equal(toMilliseconds(milliseconds(250)), 250);
  assert.equal(toMinutes(minutes(2.5)), 2.5);
  assert.ok(Math.abs(toDegrees(degrees(37)) - 37) < 1e-12);
  assert.equal(toKilopascals(kilopascals(12.3)), 12.3);
  assert.ok(
    Math.abs(toMillimetresOfMercury(millimetresOfMercury(120)) - 120) < 1e-12,
  );
  assert.equal(toMetresPerSecond(metresPerSecond(1.5)), 1.5);
  assert.ok(Math.abs(toLitresPerMinute(litresPerMinute(5.2)) - 5.2) < 1e-12);
  assert.equal(toLitres(litres(2)), 2);
  assert.equal(toMillinewtons(millinewtons(750)), 750);
});

test('coordinate-space constructors retain explicit coordinate semantics', () => {
  assert.deepEqual(patientSpacePoint(1, 2, 3), {
    space: 'patient',
    kind: 'point',
    value: vec3(1, 2, 3),
  });
  assert.equal(patientSpaceVector(1, 0, 0).kind, 'vector');
  assert.equal(renderSpacePoint(4, 5, 6).space, 'render');
  assert.deepEqual(imageVoxelCoordinate(7, 8, 9), {
    space: 'image-voxel',
    i: 7,
    j: 8,
    k: 9,
  });
});
