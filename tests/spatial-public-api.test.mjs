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

test('TASK-043 facade retains its operations with TASK-072 contact capability', () => {
  assert.deepEqual(Object.getOwnPropertyNames(Object.getPrototypeOf(service)), [
    'constructor',
    'queryPoint',
    'querySegment',
    'distanceTo',
    'queryContacts',
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

test('TASK-072 Spatial contact intervals include closed endpoints and tangency', () => {
  const contacts = service.queryContacts(
    patientSpaceSegment(p(0, -10, -5), p(0, -10, 20)),
  );
  assert.deepEqual(
    contacts.map((c) => [
      c.structureId,
      c.start.position.value.z,
      c.end.position.value.z,
    ]),
    [
      ['structure.skin', -1, 1],
      ['structure.soft', 1, 20],
      ['structure.vein', 7, 13],
    ],
  );
  assert.equal(toMillimetres(contacts[2].start.distanceFromStart), 12);
  assert.ok(Object.isFrozen(contacts));
  assert.ok(Object.isFrozen(contacts[0].start.position.value));
  const tangent = service.queryContacts(
    patientSpaceSegment(p(0, -13, 2), p(0, -13, 20)),
  );
  const touch = tangent.find((c) => c.structureId === 'structure.vein');
  assert.deepEqual(touch.start, touch.end);
  assert.deepEqual(touch.start.position, p(0, -13, 10));
  const endpoint = service.queryContacts(
    patientSpaceSegment(p(0, -10, 2), p(0, -10, 7)),
  );
  assert.equal(endpoint[1].start.t, 1);
  assert.equal(endpoint[1].end.t, 1);
});

test('TASK-072 surface overlap is contact while penetration semantics stay unchanged', () => {
  const segment = patientSpaceSegment(p(-60, 0, 1), p(60, 0, 1));
  const contacts = service.queryContacts(segment);
  assert.deepEqual(
    contacts.map((c) => [
      c.structureId,
      c.start.position.value.x,
      c.end.position.value.x,
    ]),
    [
      ['structure.skin', -50, 50],
      ['structure.soft', -50, 50],
    ],
  );
  assert.throws(() => service.querySegment(segment), /Boundary overlap/);
});

const contactRegion = (id, center, thickness = 2) => ({
  regionId: spatialRegionId(id),
  structureId: structureId('structure.union'),
  canonicalEntityId: entityId('entity.union'),
  name: 'Non-medical union test',
  membershipRoles: ['tissue'],
  representation: new Box({
    center: p(0, 0, center),
    size: [mm(2), mm(2), mm(thickness)],
  }),
});
const contactService = (bindings) =>
  new SpatialQueryService({
    regions: bindings,
    distanceEntries: [bindings[0]],
  });

test('TASK-072 merges same-structure overlap and exact adjacency, not separate contacts', () => {
  const bindings = [
    contactRegion('r.a', 0),
    contactRegion('r.b', 1),
    contactRegion('r.c', 3),
    contactRegion('r.d', 7),
  ];
  const segment = patientSpaceSegment(p(0, 0, -2), p(0, 0, 10));
  const expected = contactService(bindings).queryContacts(segment);
  assert.deepEqual(
    expected.map((c) => [c.start.position.value.z, c.end.position.value.z]),
    [
      [-1, 4],
      [6, 8],
    ],
  );
  assert.deepEqual(
    contactService([...bindings].reverse()).queryContacts(segment),
    expected,
  );
  const gap = 2 ** -30;
  const separated = contactService([
    contactRegion('r.a', 0),
    contactRegion('r.b', 2 + gap),
  ]).queryContacts(patientSpaceSegment(p(0, 0, -2), p(0, 0, 6)));
  assert.equal(separated.length, 2);
  assert.equal(
    separated[1].start.position.value.z - separated[0].end.position.value.z,
    gap,
  );
});

test('TASK-072 duplicate/permuted contacts and reversed movement are deterministic', () => {
  const region = contactRegion('r.a', 0);
  const adapter = region.representation;
  const replaced = {
    ...region,
    representation: {
      bounds: adapter.bounds,
      containsPoint: (point) => adapter.containsPoint(point),
      classifyPoint: (point) => adapter.classifyPoint(point),
      distanceToPoint: (point) => adapter.distanceToPoint(point),
      intersectSegment: (segment) => {
        const hits = adapter.intersectSegment(segment);
        return [...hits, ...hits].reverse();
      },
    },
  };
  const segment = patientSpaceSegment(p(0, 0, -2), p(0, 0, 2));
  const expected = contactService([region]).queryContacts(segment);
  assert.deepEqual(contactService([replaced]).queryContacts(segment), expected);
  const reverse = contactService([region]).queryContacts(
    patientSpaceSegment(segment.end, segment.start),
  );
  assert.deepEqual(reverse[0].start.position, expected[0].end.position);
  assert.deepEqual(reverse[0].end.position, expected[0].start.position);
  assert.equal(toMillimetres(reverse[0].start.distanceFromStart), 1);
});

test('TASK-072 zero-length queries never call geometry and invalid geometry fails', () => {
  const region = contactRegion('r.a', 0);
  const broken = {
    ...region,
    representation: {
      ...region.representation,
      classifyPoint() {
        throw new Error('Geometry unavailable');
      },
      intersectSegment() {
        throw new Error('Geometry unavailable');
      },
    },
  };
  const api = contactService([broken]);
  const point = p(0, 0, 0);
  assert.deepEqual(api.queryContacts(patientSpaceSegment(point, point)), []);
  assert.throws(
    () => api.queryContacts(patientSpaceSegment(point, p(0, 0, 1))),
    /Geometry unavailable/,
  );
  for (const bad of [
    p(NaN, 0, 0),
    { ...point, space: 'render' },
    { ...point, kind: 'vector' },
  ]) {
    assert.throws(() =>
      api.queryContacts(patientSpaceSegment(bad, p(0, 0, 1))),
    );
  }
  const inconsistent = contactService([
    region,
    {
      ...contactRegion('r.b', 3),
      canonicalEntityId: entityId('entity.other'),
    },
  ]);
  assert.throws(
    () => inconsistent.queryContacts(patientSpaceSegment(point, p(0, 0, 5))),
    /disagree on canonical/,
  );
});

test('TASK-072 off-segment hits and unknown classifications fail closed', () => {
  const region = contactRegion('r.a', 0);
  const adapter = region.representation;
  for (const [hits, classify] of [
    [[p(10, 0, 0)], (point) => adapter.classifyPoint(point)],
    [[], () => 'unknown'],
  ]) {
    const api = contactService([
      {
        ...region,
        representation: {
          bounds: adapter.bounds,
          intersectSegment: () => hits,
          classifyPoint: classify,
          containsPoint: (point) => adapter.containsPoint(point),
          distanceToPoint: (point) => adapter.distanceToPoint(point),
        },
      },
    ]);
    assert.throws(() =>
      api.queryContacts(patientSpaceSegment(p(0, 0, -2), p(0, 0, 2))),
    );
  }
});
