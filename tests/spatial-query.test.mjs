import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  entityId,
  structureId,
} from '../packages/core/dist/index.js';
import { patientSpacePoint } from '../packages/math/dist/index.js';
import {
  AxisAlignedBoxSpatialAdapter,
  BasicSpatialIndex,
  PointQuery,
  SegmentQuery,
  XAxisCylinderSpatialAdapter,
  patientSpaceSegment,
} from '../packages/spatial/dist/index.js';
import { millimetres } from '../packages/units/dist/index.js';

const fixture = JSON.parse(
  await readFile('fixtures/anatomy/synthetic-anatomy-v1.json', 'utf8'),
);

function adapterFor(entity) {
  const geometry = entity.geometry;
  const center = patientSpacePoint(...geometry.centerMm);

  if (geometry.shape === 'slab') {
    return new AxisAlignedBoxSpatialAdapter({
      center,
      size: geometry.sizeMm.map(millimetres),
    });
  }

  assert.equal(geometry.shape, 'cylinder');
  assert.equal(geometry.axis, 'x');
  return new XAxisCylinderSpatialAdapter({
    center,
    radius: millimetres(geometry.radiusMm),
    length: millimetres(geometry.lengthMm),
  });
}

const entries = fixture.entities.map((entity) => ({
  structureId: structureId(entity.id.replace('entity.', 'structure.')),
  canonicalEntityId: entityId(entity.id),
  name: entity.name,
  membershipRoles:
    entity.type === 'fixture-tissue' ? ['tissue'] : ['lumen'],
  representation: adapterFor(entity),
}));

const index = new BasicSpatialIndex(entries);

test('TASK-036 basic spatial index narrows point and segment candidates by bounds', () => {
  const skinPoint = patientSpacePoint(0, 0, 0);
  assert.deepEqual(
    index.candidatesForPoint(skinPoint).map((entry) => entry.canonicalEntityId),
    ['entity.fixture.skin'],
  );

  const farPoint = patientSpacePoint(200, 200, 200);
  assert.deepEqual(index.candidatesForPoint(farPoint), []);

  const farSegment = patientSpaceSegment(
    patientSpacePoint(100, 100, -10),
    patientSpacePoint(100, 100, 40),
  );
  assert.deepEqual(index.candidatesForSegment(farSegment), []);
});

test('TASK-037 point query returns named structures, tissue, and fixture lumen membership', () => {
  const query = new PointQuery(index);

  const skin = query.execute(patientSpacePoint(0, 0, 0));
  assert.deepEqual(
    skin.structures.map((match) => match.canonicalEntityId),
    ['entity.fixture.skin'],
  );
  assert.deepEqual(
    skin.tissues.map((match) => match.canonicalEntityId),
    ['entity.fixture.skin'],
  );
  assert.deepEqual(skin.lumens, []);

  const veinCenter = query.execute(patientSpacePoint(0, -10, 10));
  assert.deepEqual(
    veinCenter.structures.map((match) => match.canonicalEntityId),
    ['entity.fixture.soft-tissue', 'entity.fixture.vein'],
  );
  assert.deepEqual(
    veinCenter.tissues.map((match) => match.canonicalEntityId),
    ['entity.fixture.soft-tissue'],
  );
  assert.deepEqual(
    veinCenter.lumens.map((match) => match.canonicalEntityId),
    ['entity.fixture.vein'],
  );
});

test('TASK-038 segment query returns actual fixture intersections without boundary semantics', () => {
  const query = new SegmentQuery(index);
  const segment = patientSpaceSegment(
    patientSpacePoint(0, -10, -5),
    patientSpacePoint(0, -10, 20),
  );

  const hits = query.execute(segment);
  assert.deepEqual(
    hits.map((hit) => hit.canonicalEntityId),
    [
      'entity.fixture.skin',
      'entity.fixture.soft-tissue',
      'entity.fixture.vein',
    ],
  );

  assert.deepEqual(
    hits.map((hit) => hit.intersections.map((point) => point.value.z)),
    [
      [-1, 1],
      [1],
      [7, 13],
    ],
  );
  assert.equal('entry' in hits[0], false);
  assert.equal('exit' in hits[0], false);
  assert.equal('boundaryId' in hits[0], false);
});

test('primitive spatial adapters provide deterministic containment and intersection behavior', () => {
  const vein = entries.find(
    (entry) => entry.canonicalEntityId === 'entity.fixture.vein',
  );
  assert.ok(vein);
  assert.equal(vein.representation.containsPoint(patientSpacePoint(0, -10, 10)), true);
  assert.equal(vein.representation.containsPoint(patientSpacePoint(0, -10, 14)), false);

  const tangent = patientSpaceSegment(
    patientSpacePoint(0, -13, 0),
    patientSpacePoint(0, -13, 20),
  );
  assert.deepEqual(
    vein.representation
      .intersectSegment(tangent)
      .map((point) => [point.value.x, point.value.y, point.value.z]),
    [[0, -13, 10]],
  );
});
