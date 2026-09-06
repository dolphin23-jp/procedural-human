import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { entityId, structureId } from '../packages/core/dist/index.js';
import { patientSpacePoint as p } from '../packages/math/dist/index.js';
import {
  AxisAlignedBoxSpatialAdapter as Box,
  SpatialQueryService,
  XAxisCylinderSpatialAdapter as Cylinder,
  patientSpaceSegment,
  spatialRegionId,
} from '../packages/spatial/dist/index.js';
import {
  millimetres as mm,
  toMillimetres,
} from '../packages/units/dist/index.js';

const fixture = JSON.parse(
  await readFile('fixtures/anatomy/synthetic-anatomy-v1.json', 'utf8'),
);
const identities = [
  ['region.skin', 'structure.skin', ['tissue']],
  ['region.soft', 'structure.soft', ['tissue']],
  ['region.vein', 'structure.vein', ['lumen']],
  ['region.artery', 'structure.artery', ['lumen']],
];

const regions = fixture.entities.map((entity, index) => {
  const geometry = entity.geometry;
  return {
    regionId: spatialRegionId(identities[index][0]),
    structureId: structureId(identities[index][1]),
    canonicalEntityId: entityId(entity.id),
    name: entity.name,
    membershipRoles: identities[index][2],
    vascularLumenKind: entity.vascularLumenKind,
    representation:
      geometry.shape === 'slab'
        ? new Box({
            center: p(...geometry.centerMm),
            size: geometry.sizeMm.map(mm),
          })
        : new Cylinder({
            center: p(...geometry.centerMm),
            radius: mm(geometry.radiusMm),
            length: mm(geometry.lengthMm),
          }),
  };
});

const boundaryFor = (region, id) => ({
  regionId: region.regionId,
  boundary: {
    id: entityId(id),
    name: 'Development fixture boundary',
    separates: ['provisional-a', 'provisional-b'],
    provenance: fixture.provenance,
    accuracy: {},
    validation: { level: 'V0', notes: 'Software testing only' },
  },
});

const service = new SpatialQueryService({
  regions,
  boundaries: [
    boundaryFor(regions[2], 'boundary.vein-wall'),
    boundaryFor(regions[3], 'boundary.artery-wall'),
  ],
});

test('TASK-043 public facade exposes only point, segment and distance query operations', () => {
  assert.deepEqual(Object.getOwnPropertyNames(Object.getPrototypeOf(service)), [
    'constructor',
    'queryPoint',
    'querySegment',
    'distanceTo',
  ]);
  assert.deepEqual(Object.keys(service), []);
});

test('TASK-043 queryPoint preserves tissue and venous lumen semantics', () => {
  const result = service.queryPoint(p(0, -10, 10));
  assert.deepEqual(
    result.tissues.map((match) => match.canonicalEntityId),
    ['entity.fixture.soft-tissue'],
  );
  assert.deepEqual(
    result.lumens.map((match) => [
      match.canonicalEntityId,
      match.vascularLumenKind,
    ]),
    [['entity.fixture.vein', 'venous']],
  );
  assert.ok(Object.isFrozen(result));
});

test('TASK-043 querySegment exposes the ordered semantic path instead of raw adapter internals', () => {
  const result = service.querySegment(
    patientSpaceSegment(p(0, -10, -5), p(0, -10, 20)),
  );
  const spans = result.filter((element) => element.kind === 'span');
  assert.deepEqual(
    spans.map((span) => span.memberships.map((member) => member.regionId)),
    [
      [],
      ['region.skin'],
      ['region.soft'],
      ['region.soft', 'region.vein'],
      ['region.soft'],
    ],
  );
  assert.deepEqual(
    result
      .filter((element) => element.kind === 'transition')
      .flatMap((element) => element.boundaryCrossings)
      .map((crossing) => [crossing.boundaryId, crossing.direction]),
    [
      ['boundary.vein-wall', 'entry'],
      ['boundary.vein-wall', 'exit'],
    ],
  );
  assert.ok(Object.isFrozen(result));
});

test('TASK-043 distanceTo keeps explicit StructureId targeting and physical Length', () => {
  const result = service.distanceTo(
    p(0, -10, 20),
    structureId('structure.vein'),
  );
  assert.equal(result.canonicalEntityId, 'entity.fixture.vein');
  assert.equal(toMillimetres(result.distance), 7);
});

test('TASK-043 ambiguous default distance bindings fail instead of selecting a region', () => {
  assert.throws(
    () =>
      new SpatialQueryService({
        regions: [
          regions[0],
          {
            ...regions[1],
            structureId: regions[0].structureId,
          },
        ],
      }),
    /Duplicate structure binding/,
  );

  assert.doesNotThrow(
    () =>
      new SpatialQueryService({
        regions: [
          regions[0],
          {
            ...regions[1],
            structureId: regions[0].structureId,
          },
        ],
        distanceEntries: [regions[0]],
      }),
  );
});
