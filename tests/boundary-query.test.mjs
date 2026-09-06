import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { entityId, structureId } from '../packages/core/dist/index.js';
import { patientSpacePoint as p } from '../packages/math/dist/index.js';
import {
  AxisAlignedBoxSpatialAdapter,
  XAxisCylinderSpatialAdapter,
  BoundaryQuery,
  BoundaryQueryFailure,
  boundaryIntersectionConsistencyTolerance,
  patientSpaceSegment as segment,
  spatialRegionId,
} from '../packages/spatial/dist/index.js';
import { millimetres, toMillimetres } from '../packages/units/dist/index.js';

const fixture = JSON.parse(
  await readFile('fixtures/anatomy/synthetic-anatomy-v1.json', 'utf8'),
);
const adapters = fixture.entities.map(({ geometry: g }) =>
  g.shape === 'slab'
    ? new AxisAlignedBoxSpatialAdapter({
        center: p(...g.centerMm),
        size: g.sizeMm.map(millimetres),
      })
    : new XAxisCylinderSpatialAdapter({
        center: p(...g.centerMm),
        radius: millimetres(g.radiusMm),
        length: millimetres(g.lengthMm),
      }),
);
const binding = (
  representation,
  id = 'boundary.fixture.test',
  region = 'region.fixture.test',
) => ({
  boundary: {
    id: entityId(id),
    name: 'Non-medical test boundary',
    separates: ['provisional-a', 'provisional-b'],
    provenance: fixture.provenance,
    accuracy: {},
    validation: { level: 'V0', notes: 'Software fixture only' },
  },
  regionId: spatialRegionId(region),
  structureId: structureId('structure.fixture.test'),
  representation,
});
const skin = new BoundaryQuery([binding(adapters[0])]);
const vein = new BoundaryQuery([binding(adapters[2])]);
const zSegment = (a, b) => segment(p(0, 0, a), p(0, 0, b));

test('TASK-039 simple entry preserves semantic identity, patient space and physical distance', () => {
  const [hit, ...rest] = skin.execute(zSegment(-5, 0));
  assert.deepEqual(rest, []);
  assert.equal(hit.boundaryId, 'boundary.fixture.test');
  assert.equal(hit.direction, 'entry');
  assert.deepEqual(hit.position, p(0, 0, -1));
  assert.equal(toMillimetres(hit.distanceFromStart), 4);
  assert.equal(hit.t, 0.8);
  assert.deepEqual(hit.from, {
    regionId: 'region.fixture.test',
    side: 'outside',
  });
  assert.deepEqual(hit.to, { regionId: 'region.fixture.test', side: 'inside' });
  assert.ok(Object.isFrozen(hit.position.value));
});

test('TASK-039 simple exit and reversed segment direction', () => {
  const hits = skin.execute(zSegment(0, -5));
  assert.equal(hits.length, 1);
  assert.equal(hits[0].direction, 'exit');
  assert.equal(toMillimetres(hits[0].distanceFromStart), 1);
});

test('TASK-039 through-crossing gives entry then exit', () => {
  assert.deepEqual(
    skin
      .execute(zSegment(-5, 5))
      .map((h) => [
        h.direction,
        h.position.value.z,
        toMillimetres(h.distanceFromStart),
      ]),
    [
      ['entry', -1, 4],
      ['exit', 1, 6],
    ],
  );
});

test('TASK-039 no crossing for entirely inside or outside', () => {
  assert.deepEqual(skin.execute(zSegment(-0.5, 0.5)), []);
  assert.deepEqual(skin.execute(zSegment(-5, -2)), []);
});

test('TASK-039 tangent and surface-following contacts are not crossings', () => {
  assert.deepEqual(vein.execute(segment(p(0, -13, 0), p(0, -13, 20))), []);
  assert.deepEqual(skin.execute(segment(p(-60, 0, 1), p(60, 0, 1))), []);
  assert.deepEqual(vein.execute(segment(p(-40, -13, 10), p(40, -13, 10))), []);
  // Box corner touch, outside on both sides.
  assert.deepEqual(skin.execute(segment(p(40, 0, 2), p(60, 0, 0))), []);
});

test('TASK-039 endpoint contacts are excluded; later interior crossings remain', () => {
  for (const [a, b] of [
    [-5, -1],
    [-1, 0],
    [0, 1],
    [1, 5],
    [-1, 1],
    [-1, -5],
  ]) {
    assert.deepEqual(skin.execute(zSegment(a, b)), []);
  }
  const hits = skin.execute(zSegment(-1, 5));
  assert.deepEqual(
    hits.map((h) => [h.direction, h.position.value.z]),
    [['exit', 1]],
  );
  const cylinderHits = vein.execute(segment(p(0, -10, 7), p(0, -10, 20)));
  assert.deepEqual(
    cylinderHits.map((h) => [h.direction, h.position.value.z]),
    [['exit', 13]],
  );
});

test('TASK-039 zero length is empty inside, outside, and on boundary', () => {
  for (const z of [-5, -1, 0])
    assert.deepEqual(skin.execute(zSegment(z, z)), []);
});

const wrap = (adapter, intersections) => ({
  bounds: adapter.bounds,
  containsPoint: (p) => adapter.containsPoint(p),
  classifyPoint: (p) => adapter.classifyPoint(p),
  distanceToPoint: (p) => adapter.distanceToPoint(p),
  intersectSegment: intersections,
});

test('TASK-039 duplicate hits and triangle-order permutations yield one crossing per transition', () => {
  const source = adapters[0];
  const representation = wrap(source, (s) => {
    const hits = source.intersectSegment(s);
    return [...hits, ...hits, ...hits].reverse();
  });
  const query = new BoundaryQuery([binding(representation)]);
  assert.deepEqual(
    query.execute(zSegment(-5, 5)),
    skin.execute(zSegment(-5, 5)),
  );
});

test('TASK-039 deterministic progression and coincident semantic ID tie order', () => {
  const bindings = [
    binding(adapters[0], 'boundary.z', 'region.z'),
    binding(adapters[0], 'boundary.a', 'region.a'),
    binding(adapters[1], 'boundary.b', 'region.b'),
  ];
  const expected = new BoundaryQuery(bindings).execute(zSegment(-5, 40));
  assert.deepEqual(
    expected.map((h) => [h.position.value.z, h.boundaryId, h.direction]),
    [
      [-1, 'boundary.a', 'entry'],
      [-1, 'boundary.z', 'entry'],
      [1, 'boundary.a', 'exit'],
      [1, 'boundary.b', 'entry'],
      [1, 'boundary.z', 'exit'],
      [31, 'boundary.b', 'exit'],
    ],
  );
  for (let i = 0; i < 20; i++) {
    assert.deepEqual(
      new BoundaryQuery(i % 2 ? bindings : [...bindings].reverse()).execute(
        zSegment(-5, 40),
      ),
      expected,
    );
  }
});

test('TASK-039 same semantic boundary may have multiple explicitly identified regions', () => {
  const a = binding(adapters[0], 'boundary.same', 'region.a');
  const b = binding(adapters[0], 'boundary.same', 'region.b');
  assert.deepEqual(
    new BoundaryQuery([b, a]).execute(zSegment(-5, 0)).map((h) => h.regionId),
    ['region.a', 'region.b'],
  );
  assert.throws(() => new BoundaryQuery([a, a]), /Duplicate region binding/);
});

test('TASK-039 representation replacement preserves semantic identity without inspecting names', () => {
  const cylinder = binding(adapters[2]);
  cylinder.boundary.name = 'Renamed independently';
  cylinder.boundary.separates.reverse();
  const hits = new BoundaryQuery([cylinder]).execute(
    segment(p(0, -10, 0), p(0, -10, 20)),
  );
  assert.deepEqual(
    hits.map((h) => [h.boundaryId, h.direction]),
    [
      ['boundary.fixture.test', 'entry'],
      ['boundary.fixture.test', 'exit'],
    ],
  );
});

test('TASK-039 cylinder caps and oblique physical distance', () => {
  assert.deepEqual(
    vein
      .execute(segment(p(-40, -10, 10), p(40, -10, 10)))
      .map((h) => [h.direction, h.position.value.x]),
    [
      ['entry', -35],
      ['exit', 35],
    ],
  );
  const hits = skin.execute(segment(p(0, 0, -5), p(3, 0, -1)));
  assert.deepEqual(hits, []);
  const [hit] = skin.execute(segment(p(0, 0, -5), p(6, 0, 3)));
  assert.deepEqual(hit.position, p(3, 0, -1));
  assert.equal(toMillimetres(hit.distanceFromStart), 5);
});

test('TASK-039 close distinct surfaces are not epsilon-merged', () => {
  const thin = new AxisAlignedBoxSpatialAdapter({
    center: p(0, 0, 0),
    size: [millimetres(2), millimetres(2), millimetres(1e-8)],
  });
  const hits = new BoundaryQuery([binding(thin)]).execute(
    zSegment(-1e-8, 1e-8),
  );
  assert.deepEqual(
    hits.map((h) => h.direction),
    ['entry', 'exit'],
  );
});

test('TASK-039 numerical consistency tolerance only checks distance off the segment', () => {
  const toleranceMm = toMillimetres(boundaryIntersectionConsistencyTolerance);
  const query = (offset) =>
    new BoundaryQuery([binding(wrap(adapters[0], () => [p(offset, 0, -1)]))]);
  assert.equal(query(toleranceMm / 2).execute(zSegment(-5, 0)).length, 1);
  assert.throws(
    () => query(toleranceMm * 2).execute(zSegment(-5, 0)),
    /off the segment/,
  );
});

test('TASK-039 invalid coordinates, missing capability and invalid hits fail explicitly', () => {
  assert.throws(() => skin.execute(zSegment(NaN, 0)), BoundaryQueryFailure);
  assert.throws(
    () => skin.execute(zSegment(-Number.MAX_VALUE, Number.MAX_VALUE)),
    /overflow/,
  );
  assert.throws(
    () => new BoundaryQuery([binding({})]),
    /lacks region classification/,
  );
  for (const point of [p(0, 0, -6), p(0, 0, NaN)]) {
    const query = new BoundaryQuery([
      binding(wrap(adapters[0], () => [point])),
    ]);
    assert.throws(() => query.execute(zSegment(-5, 0)), BoundaryQueryFailure);
  }
});

test('TASK-039 nonconvex region supports more than two contacts without convexity assumptions', () => {
  const boxes = [-3, 3].map(
    (z) =>
      new AxisAlignedBoxSpatialAdapter({
        center: p(0, 0, z),
        size: [millimetres(2), millimetres(2), millimetres(2)],
      }),
  );
  const representation = {
    bounds: { min: p(-1, -1, -4), max: p(1, 1, 4) },
    containsPoint: (point) => boxes.some((b) => b.containsPoint(point)),
    classifyPoint: (point) => {
      const states = boxes.map((b) => b.classifyPoint(point));
      return states.includes('inside')
        ? 'inside'
        : states.includes('boundary')
          ? 'boundary'
          : 'outside';
    },
    intersectSegment: (s) =>
      boxes.flatMap((b) => b.intersectSegment(s)).reverse(),
    distanceToPoint: (point) =>
      millimetres(
        Math.min(...boxes.map((b) => toMillimetres(b.distanceToPoint(point)))),
      ),
  };
  assert.deepEqual(
    new BoundaryQuery([binding(representation)])
      .execute(zSegment(-5, 5))
      .map((h) => [h.direction, h.position.value.z]),
    [
      ['entry', -4],
      ['exit', -2],
      ['entry', 2],
      ['exit', 4],
    ],
  );
});

test('TASK-039 unresolved adjacent floating-point hits fail instead of fabricating a transition', () => {
  const representation = wrap(adapters[0], () => [
    p(0, 0, 0.5),
    p(0, 0, 0.5 + Number.EPSILON / 2),
  ]);
  assert.throws(
    () => new BoundaryQuery([binding(representation)]).execute(zSegment(0, 1)),
    /cannot be resolved/,
  );
});

test('TASK-039 region primitives reject degenerate dimensions', () => {
  for (const n of [0, -1, NaN, Infinity]) {
    assert.throws(
      () =>
        new AxisAlignedBoxSpatialAdapter({
          center: p(0, 0, 0),
          size: [millimetres(n), millimetres(1), millimetres(1)],
        }),
      /finite positive/,
    );
    assert.throws(
      () =>
        new XAxisCylinderSpatialAdapter({
          center: p(0, 0, 0),
          radius: millimetres(n),
          length: millimetres(1),
        }),
      /finite positive/,
    );
  }
});
