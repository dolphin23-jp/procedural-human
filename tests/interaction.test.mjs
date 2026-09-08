import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  assetId,
  contentHash,
  entityId,
  patientId,
  structureId,
  version,
} from '../packages/core/dist/index.js';
import { patientSpacePoint as p } from '../packages/math/dist/index.js';
import {
  createInstrumentPart,
  createInstrumentPose,
  createNeedleDefinition,
  createNeedleInstance,
  instrumentDefinitionId,
  instrumentInstanceId,
  instrumentPartId,
  NeedleMotionController,
  needleAdvanceIntent,
  needleRotationIntent,
  updateNeedlePose,
} from '../packages/instruments/dist/index.js';
import { InteractionEngine } from '../packages/interaction/dist/index.js';
import {
  PatientInstance,
  PatientStructureInstance,
} from '../packages/patient/dist/index.js';
import {
  AxisAlignedBoxSpatialAdapter as Box,
  SpatialQueryService,
  XAxisCylinderSpatialAdapter as Cylinder,
  patientSpaceSegment,
  spatialRegionId,
  PenetrationPathFailure,
} from '../packages/spatial/dist/index.js';
import {
  degrees,
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

const parts = Object.fromEntries(
  ['tip', 'bevel', 'shaft', 'lumen'].map((name) => [
    name,
    instrumentPartId(name),
  ]),
);
const definition = createNeedleDefinition({
  id: instrumentDefinitionId('task071.needle'),
  name: 'Software test needle',
  parts: Object.entries(parts).map(([name, id]) =>
    createInstrumentPart({ id, name }),
  ),
  functionalParts: parts,
  geometry: {
    shaftLength: mm(40),
    bevelLength: mm(3),
    outerDiameter: mm(1.2),
    lumenDiameter: mm(0.7),
  },
});
const pose = (position) =>
  createInstrumentPose({
    position,
    orientation: { x: 0, y: 0, z: 0, w: 1 },
  });
const needle = (position) =>
  createNeedleInstance({
    id: instrumentInstanceId('task071.instance'),
    definition,
    pose: pose(position),
  });
const engine = new InteractionEngine(service);
const previous = needle(p(0, -10, -5));
const current = updateNeedlePose(previous, pose(p(0, -10, 20)));
const request = { previous, current };

test('TASK-071 controller movement reaches the public query once in Patient Space', () => {
  const calls = [];
  let returned;
  const spatial = {
    querySegment(segment) {
      assert.equal(this, spatial);
      calls.push(segment);
      returned = service.querySegment(segment);
      return returned;
    },
    queryPoint() {
      assert.fail('Unexpected point query');
    },
    distanceTo() {
      assert.fail('Unexpected distance query');
    },
  };
  const controller = new NeedleMotionController({
    translationStep: mm(10),
    rotationStep: degrees(90),
    advanceStep: mm(25),
  });
  const moved = controller.apply(previous, needleAdvanceIntent(1));
  const result = new InteractionEngine(spatial).observeNeedleMovement({
    previous,
    current: moved,
  });
  assert.equal(result.kind, 'queried');
  assert.equal(result.instrumentId, previous.id);
  assert.equal(calls.length, 1);
  assert.equal(calls[0], result.segment);
  assert.deepEqual(result.segment, {
    start: p(0, -10, -5),
    end: p(0, -10, 20),
  });
  assert.equal(result.spatialResult, returned);
  assert.notEqual(result.segment.start, previous.tipPosition);
  assert.ok(Object.isFrozen(result.segment.start.value));
  assert.ok(Object.isFrozen(result.segment.end.value));
  assert.ok(Object.isFrozen(result.segment));
  assert.ok(Object.isFrozen(result));
});

test('TASK-071 preserves raw Spatial crossings without events or medical mutation', () => {
  const patient = new PatientInstance({
    id: patientId('patient.task071'),
    morphology: { mode: 'static' },
    anatomy: {
      canonicalAnatomy: {
        assetId: assetId('asset.fixture'),
        version: version('1'),
        contentHash: contentHash('fixture-test-reference'),
      },
      structures: regions.map(
        (region) =>
          new PatientStructureInstance({
            id: region.structureId,
            canonicalEntityId: region.canonicalEntityId,
            representationAssetIds: [],
          }),
      ),
    },
  });
  const snapshot = () =>
    regions.map((region) => patient.medicalStateFor(region.structureId));
  const before = snapshot();
  const instrumentBefore = JSON.stringify(request);
  for (const y of [-10, 10]) {
    const a = needle(p(0, y, -5));
    const b = updateNeedlePose(a, pose(p(0, y, 25)));
    engine.detectNeedleContacts({ previous: a, current: b });
    const result = engine.observeNeedleMovement({ previous: a, current: b });
    assert.deepEqual(Object.keys(result).sort(), [
      'instrumentId',
      'kind',
      'segment',
      'spatialResult',
    ]);
    assert.deepEqual(
      result.spatialResult,
      service.querySegment(patientSpaceSegment(a.tipPosition, b.tipPosition)),
    );
    assert.equal(
      result.spatialResult
        .filter((element) => element.kind === 'transition')
        .flatMap((element) => element.boundaryCrossings).length,
      2,
    );
    assert.doesNotMatch(
      JSON.stringify(result),
      /Contact|BoundaryCrossed|LumenEntered|LumenExited|SimulationEvent/,
    );
  }
  assert.deepEqual(snapshot(), before);
  assert.ok(before.every((state) => state.integrity === 'intact'));
  assert.equal(JSON.stringify(request), instrumentBefore);
});

test('TASK-071 oblique displacement preserves coordinates and physical distances', () => {
  const a = needle(p(100, 100, 100));
  const b = updateNeedlePose(a, pose(p(103, 104, 100)));
  const result = engine.observeNeedleMovement({ previous: a, current: b });
  assert.deepEqual(result.segment.start, p(100, 100, 100));
  assert.deepEqual(result.segment.end, p(103, 104, 100));
  assert.equal(result.spatialResult.length, 1);
  assert.equal(toMillimetres(result.spatialResult[0].end.distanceFromStart), 5);
});

test('TASK-071 unchanged tips including pure rotation never query or traverse', () => {
  const noQuery = new InteractionEngine({
    querySegment() {
      assert.fail('Stationary tip must not query');
    },
  });
  const controller = new NeedleMotionController({
    translationStep: mm(10),
    rotationStep: degrees(90),
    advanceStep: mm(25),
  });
  for (const z of [-5, -1, 0, 10]) {
    const a = needle(p(0, -10, z));
    for (const b of [
      a,
      updateNeedlePose(a, a.pose),
      controller.apply(a, needleRotationIntent(1, 0)),
    ]) {
      assert.deepEqual(
        noQuery.observeNeedleMovement({ previous: a, current: b }),
        {
          kind: 'stationary',
          instrumentId: a.id,
          position: a.tipPosition,
        },
      );
    }
  }
});

test('TASK-071 repeats, reversal and small displacement have no accumulated state', () => {
  const expected = engine.observeNeedleMovement(request);
  const reversed = engine.observeNeedleMovement({
    previous: current,
    current: previous,
  });
  assert.deepEqual(reversed.segment, {
    start: current.tipPosition,
    end: previous.tipPosition,
  });
  assert.deepEqual(
    reversed.spatialResult,
    service.querySegment(reversed.segment),
  );
  assert.deepEqual(engine.observeNeedleMovement(request), expected);
  assert.deepEqual(Object.keys(engine), []);
  const a = needle(p(0, 0, 0));
  const b = updateNeedlePose(a, pose(p(1e-12, 0, 0)));
  assert.equal(
    engine.observeNeedleMovement({ previous: a, current: b }).kind,
    'queried',
  );
});

test('TASK-071 malformed movements fail before any query, including stationary input', () => {
  let queryCalls = 0;
  const noQuery = new InteractionEngine({
    querySegment() {
      queryCalls += 1;
      assert.fail('Invalid movement must not query');
    },
  });
  for (const bad of [
    undefined,
    null,
    {},
    { ...previous, kind: 'other' },
    { ...previous, id: '' },
    { ...previous, id: instrumentInstanceId('different') },
    { ...previous, definitionId: instrumentDefinitionId('different') },
    { ...previous, tipPosition: undefined },
    { ...previous, tipPosition: { ...previous.tipPosition, space: 'render' } },
    { ...previous, tipPosition: { ...previous.tipPosition, kind: 'vector' } },
    { ...previous, tipPosition: p(NaN, 0, 0) },
    { ...previous, tipPosition: p(Infinity, 0, 0) },
    { ...previous, tipPosition: p(0, 0, 0) },
    { ...previous, pose: undefined },
  ]) {
    assert.throws(() =>
      noQuery.observeNeedleMovement({ previous, current: bad }),
    );
    assert.throws(() =>
      noQuery.observeNeedleMovement({ previous: bad, current: previous }),
    );
  }
  assert.throws(() => noQuery.observeNeedleMovement());
  const a = needle(p(-Number.MAX_VALUE, 0, 0));
  const b = updateNeedlePose(a, pose(p(Number.MAX_VALUE, 0, 0)));
  assert.throws(
    () => noQuery.observeNeedleMovement({ previous: a, current: b }),
    /overflow/,
  );
  assert.equal(queryCalls, 0);
  for (const dependency of [undefined, null, {}, { querySegment: 1 }]) {
    assert.throws(() => new InteractionEngine(dependency), /Spatial Query/);
  }
});

test('TASK-071 spatial errors propagate unchanged with no fallback', () => {
  const failure = new Error('Representation unavailable');
  const failing = new InteractionEngine({
    querySegment() {
      throw failure;
    },
  });
  assert.throws(
    () => failing.observeNeedleMovement(request),
    (error) => error === failure,
  );
  const a = needle(p(-60, 0, 1));
  const b = updateNeedlePose(a, pose(p(60, 0, 1)));
  assert.throws(
    () => engine.observeNeedleMovement({ previous: a, current: b }),
    PenetrationPathFailure,
  );
});

test('TASK-071 retains endpoint and tangent limitations without inventing contact', () => {
  for (const [start, end] of [
    [p(0, -10, 2), p(0, -10, 7)],
    [p(0, -10, 7), p(0, -10, 10)],
    [p(0, -13, 2), p(0, -13, 20)],
  ]) {
    const a = needle(start);
    const b = updateNeedlePose(a, pose(end));
    const result = engine.observeNeedleMovement({ previous: a, current: b });
    assert.equal(result.spatialResult.length, 1);
    assert.equal(result.spatialResult[0].kind, 'span');
  }
});

test('TASK-071 package declares only necessary dependencies and no DOM library', async () => {
  const pkg = JSON.parse(
    await readFile('packages/interaction/package.json', 'utf8'),
  );
  assert.deepEqual(Object.keys(pkg.dependencies).sort(), [
    '@procedural-human/instruments',
    '@procedural-human/math',
    '@procedural-human/spatial',
  ]);
  const config = JSON.parse(
    await readFile('packages/interaction/tsconfig.json', 'utf8'),
  );
  assert.deepEqual(config.compilerOptions.lib, ['ES2022']);
});

const contactsBetween = (start, end, api = engine) => {
  const a = needle(start);
  const b = updateNeedlePose(a, pose(end));
  return api.detectNeedleContacts({ previous: a, current: b });
};

test('TASK-072 emits first structure contact with Patient Space identity and distance', () => {
  const contacts = engine.detectNeedleContacts(request);
  assert.deepEqual(
    contacts.map((c) => [
      c.kind,
      c.instrumentId,
      c.structureId,
      c.at.position.value.z,
      toMillimetres(c.at.distanceFromStart),
    ]),
    [
      ['contact', previous.id, 'structure.skin', -1, 4],
      ['contact', previous.id, 'structure.soft', 1, 6],
      ['contact', previous.id, 'structure.vein', 7, 12],
    ],
  );
  assert.equal(contacts[2].canonicalEntityId, 'entity.fixture.vein');
  assert.ok(Object.isFrozen(contacts));
  assert.ok(contacts.every(Object.isFrozen));
  assert.ok(Object.isFrozen(contacts[2].at.position.value));
  assert.doesNotMatch(
    JSON.stringify(contacts),
    /BoundaryCrossed|LumenEntered|LumenExited|punctured|success|unsafe/,
  );
  const arterial = contactsBetween(p(0, 10, -5), p(0, 10, 25));
  assert.equal(arterial[2].structureId, 'structure.artery');
  assert.equal(arterial[2].kind, 'contact');
});

test('TASK-072 endpoint contact occurs once across consecutive movements', () => {
  const first = contactsBetween(p(0, -10, 2), p(0, -10, 7));
  assert.equal(first.length, 1);
  assert.equal(first[0].structureId, 'structure.vein');
  assert.equal(first[0].at.t, 1);
  assert.deepEqual(contactsBetween(p(0, -10, 7), p(0, -10, 10)), []);
  assert.deepEqual(contactsBetween(p(0, -10, 10), p(0, -10, 20)), []);
  const reentry = contactsBetween(p(0, -10, 20), p(0, -10, 10));
  assert.equal(reentry.length, 1);
  assert.deepEqual(reentry[0].at.position, p(0, -10, 13));
});

test('TASK-072 tangency and surface-following contacts need no fabricated crossing', () => {
  const tangent = contactsBetween(p(0, -13, 2), p(0, -13, 20));
  assert.equal(tangent.length, 1);
  assert.equal(tangent[0].structureId, 'structure.vein');
  assert.deepEqual(tangent[0].at.position, p(0, -13, 10));
  const overlap = contactsBetween(p(-60, 0, 1), p(60, 0, 1));
  assert.deepEqual(
    overlap.map((c) => [c.structureId, c.at.position.value.x]),
    [
      ['structure.skin', -50],
      ['structure.soft', -50],
    ],
  );
  assert.deepEqual(contactsBetween(p(0, 0, 1), p(10, 0, 1)), []);
});

test('TASK-072 initial occupancy, no movement and misses do not fabricate contact', () => {
  assert.deepEqual(contactsBetween(p(0, -10, 8), p(0, -10, 9)), []);
  assert.deepEqual(contactsBetween(p(100, 100, 0), p(100, 100, 20)), []);
  const api = new InteractionEngine({
    querySegment() {
      assert.fail('Contact must not call penetration query');
    },
    queryContacts() {
      assert.fail('Stationary tip must not query');
    },
  });
  assert.deepEqual(
    api.detectNeedleContacts({ previous, current: previous }),
    [],
  );
  const rotated = updateNeedlePose(
    previous,
    createInstrumentPose({
      position: previous.tipPosition,
      orientation: { x: 0, y: 1, z: 0, w: 0 },
    }),
  );
  assert.deepEqual(
    api.detectNeedleContacts({ previous, current: rotated }),
    [],
  );
});

test('TASK-072 uses the injected contact API and propagates errors without fallback', () => {
  let calls = 0;
  const api = new InteractionEngine({
    querySegment() {
      assert.fail('Contact must not call penetration query');
    },
    queryContacts(segment) {
      calls += 1;
      assert.deepEqual(segment, {
        start: previous.tipPosition,
        end: current.tipPosition,
      });
      return service.queryContacts(segment);
    },
  });
  assert.deepEqual(
    api.detectNeedleContacts(request),
    engine.detectNeedleContacts(request),
  );
  assert.equal(calls, 1);
  assert.throws(() => api.detectNeedleContacts({ previous }), /NeedleInstance/);
  assert.equal(calls, 1);
  const unavailable = new InteractionEngine({ querySegment: () => [] });
  assert.throws(() => unavailable.detectNeedleContacts(request), /unavailable/);
  const failure = new Error('Contact geometry unavailable');
  const broken = new InteractionEngine({
    querySegment: () => [],
    queryContacts() {
      throw failure;
    },
  });
  assert.throws(
    () => broken.detectNeedleContacts(request),
    (error) => error === failure,
  );
  assert.deepEqual(
    engine.detectNeedleContacts(request),
    engine.detectNeedleContacts(request),
  );
});
