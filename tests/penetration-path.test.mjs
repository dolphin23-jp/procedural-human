import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { entityId, structureId } from '../packages/core/dist/index.js';
import { patientSpacePoint as p } from '../packages/math/dist/index.js';
import {
  AxisAlignedBoxSpatialAdapter as Box,
  XAxisCylinderSpatialAdapter as Cylinder,
  BoundaryQuery,
  BoundaryQueryFailure,
  OrderedPenetrationPathQuery as Query,
  PenetrationPathFailure,
  spatialRegionId,
  patientSpaceSegment as segment,
} from '../packages/spatial/dist/index.js';
import {
  millimetres as mm,
  toMillimetres,
} from '../packages/units/dist/index.js';

const fixture = JSON.parse(
  await readFile('fixtures/anatomy/synthetic-anatomy-v1.json', 'utf8'),
);
// Explicit fixture authoring: IDs and roles never inferred by generic Spatial.
const identities = [
  ['region.skin', 'structure.skin', ['tissue']],
  ['region.soft', 'structure.soft', ['tissue']],
  ['region.vein', 'structure.vein', ['lumen']],
  ['region.artery', 'structure.artery', ['lumen']],
];
const regions = fixture.entities.map((entity, i) => {
  const g = entity.geometry;
  return {
    regionId: spatialRegionId(identities[i][0]),
    structureId: structureId(identities[i][1]),
    canonicalEntityId: entityId(entity.id),
    name: entity.name,
    membershipRoles: identities[i][2],
    vascularLumenKind: entity.vascularLumenKind,
    representation:
      g.shape === 'slab'
        ? new Box({ center: p(...g.centerMm), size: g.sizeMm.map(mm) })
        : new Cylinder({
            center: p(...g.centerMm),
            radius: mm(g.radiusMm),
            length: mm(g.lengthMm),
          }),
  };
});
const boundaryFor = (region, id = 'boundary.test') => ({
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
const boundaries = [
  boundaryFor(regions[2], 'boundary.vein-wall'),
  boundaryFor(regions[3], 'boundary.artery-wall'),
];
const query = new Query(regions, boundaries);
const veinSegment = segment(p(0, -10, -5), p(0, -10, 20));
const spans = (path) => path.filter((e) => e.kind === 'span');
const transitions = (path) => path.filter((e) => e.kind === 'transition');
const crossings = (path) =>
  transitions(path).flatMap((e) => e.boundaryCrossings);
const ids = (memberships) => memberships.map((m) => m.regionId);
const zSegment = (start, end) => segment(p(0, 0, start), p(0, 0, end));
const regionFor = (representation, id = 'region.test') => ({
  regionId: spatialRegionId(id),
  structureId: structureId('structure.opaque'),
  canonicalEntityId: entityId('entity.opaque'),
  name: 'Arbitrary label',
  membershipRoles: ['tissue'],
  representation,
});
const box = (center = 0, thickness = 2) =>
  new Box({ center: p(0, 0, center), size: [mm(2), mm(2), mm(thickness)] });
const wrap = (adapter, hits) => ({
  bounds: adapter.bounds,
  containsPoint: (point) => adapter.containsPoint(point),
  classifyPoint: (point) => adapter.classifyPoint(point),
  distanceToPoint: (point) => adapter.distanceToPoint(point),
  intersectSegment: hits,
});

function assertLocations(path, source) {
  const a = source.start.value;
  const b = source.end.value;
  const length = Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
  for (const element of path) {
    for (const location of element.kind === 'span'
      ? [element.start, element.end]
      : [element.at]) {
      assert.ok(location.t >= 0 && location.t <= 1);
      assert.deepEqual(
        location.position,
        p(
          a.x + location.t * (b.x - a.x),
          a.y + location.t * (b.y - a.y),
          a.z + location.t * (b.z - a.z),
        ),
      );
      assert.equal(
        toMillimetres(location.distanceFromStart),
        length * location.t,
      );
      assert.ok(Object.isFrozen(location.position.value));
    }
    if (element.kind === 'span') assert.ok(element.end.t > element.start.t);
  }
}

test('TASK-042 canonical fixture vein path preserves interval occupancy and wall point crossings', () => {
  const path = query.execute(veinSegment);
  assert.deepEqual(
    path.map((e) => e.kind),
    [
      'span',
      'transition',
      'span',
      'transition',
      'span',
      'transition',
      'span',
      'transition',
      'span',
    ],
  );
  assert.deepEqual(
    spans(path).map((e) => [
      e.start.position.value.z,
      e.end.position.value.z,
      ids(e.memberships),
    ]),
    [
      [-5, -1, []],
      [-1, 1, ['region.skin']],
      [1, 7, ['region.soft']],
      [7, 13, ['region.soft', 'region.vein']],
      [13, 20, ['region.soft']],
    ],
  );
  const wallHits = crossings(path);
  assert.deepEqual(
    wallHits.map((c) => [
      c.boundaryId,
      c.structureId,
      c.regionId,
      c.direction,
      c.position.value.z,
      toMillimetres(c.distanceFromStart),
    ]),
    [
      ['boundary.vein-wall', 'structure.vein', 'region.vein', 'entry', 7, 12],
      ['boundary.vein-wall', 'structure.vein', 'region.vein', 'exit', 13, 18],
    ],
  );
  const sourceBindings = boundaries.map((binding) => ({
    ...binding,
    ...{
      structureId: regions.find((r) => r.regionId === binding.regionId)
        .structureId,
      representation: regions.find((r) => r.regionId === binding.regionId)
        .representation,
    },
  }));
  assert.deepEqual(
    wallHits,
    new BoundaryQuery(sourceBindings).execute(veinSegment),
  );
  assertLocations(path, veinSegment);
  assert.ok(Object.isFrozen(path));
  assert.ok(path.every(Object.isFrozen));
});

test('TASK-042 overlapping tissue and lumen memberships retain separate semantic identities', () => {
  const middle = spans(query.execute(veinSegment))[3];
  assert.deepEqual(middle.memberships, [
    {
      regionId: 'region.soft',
      structureId: 'structure.soft',
      canonicalEntityId: 'entity.fixture.soft-tissue',
      tissue: true,
      lumen: null,
    },
    {
      regionId: 'region.vein',
      structureId: 'structure.vein',
      canonicalEntityId: 'entity.fixture.vein',
      tissue: false,
      lumen: { vascularLumenKind: 'venous' },
    },
  ]);
  assert.ok(Object.isFrozen(middle.memberships));
  assert.ok(Object.isFrozen(middle.memberships[1].lumen));
});

test('TASK-042 arterial lumen has normal spatial semantics and no clinical judgment', () => {
  const path = query.execute(segment(p(0, 10, -5), p(0, 10, 25)));
  const lumen = spans(path)
    .flatMap((e) => e.memberships)
    .find((m) => m.lumen);
  assert.deepEqual(lumen, {
    regionId: 'region.artery',
    structureId: 'structure.artery',
    canonicalEntityId: 'entity.fixture.artery',
    tissue: false,
    lumen: { vascularLumenKind: 'arterial' },
  });
  assert.deepEqual(
    crossings(path).map((c) => [c.boundaryId, c.direction]),
    [
      ['boundary.artery-wall', 'entry'],
      ['boundary.artery-wall', 'exit'],
    ],
  );
  assert.doesNotMatch(
    JSON.stringify(path),
    /success|failure|safe|unsafe|complication|violation/i,
  );
});

test('TASK-042 vessel miss produces only skin and soft tissue occupancy', () => {
  const path = query.execute(zSegment(-5, 20));
  assert.deepEqual(
    spans(path).map((e) => ids(e.memberships)),
    [[], ['region.skin'], ['region.soft']],
  );
  assert.deepEqual(crossings(path), []);
});

test('TASK-042 reverse traversal reverses spans, changes and crossing directions with new distances', () => {
  // Power-of-two total length permits exact reversal assertions.
  const source = segment(p(0, -10, -5), p(0, -10, 27));
  const reversed = segment(source.end, source.start);
  const forward = query.execute(source);
  const backward = query.execute(reversed);
  assert.equal(forward.length, backward.length);
  for (let i = 0; i < forward.length; i++) {
    const a = forward[i];
    const b = backward[backward.length - 1 - i];
    assert.equal(a.kind, b.kind);
    if (a.kind === 'span') {
      assert.deepEqual(a.memberships, b.memberships);
      assert.deepEqual(a.start.position, b.end.position);
      assert.deepEqual(a.end.position, b.start.position);
      assert.equal(b.start.t, 1 - a.end.t);
    } else {
      assert.deepEqual(a.entered, b.exited);
      assert.deepEqual(a.exited, b.entered);
      assert.equal(b.at.t, 1 - a.at.t);
      for (let j = 0; j < a.boundaryCrossings.length; j++) {
        const x = a.boundaryCrossings[j];
        const y = b.boundaryCrossings[j];
        assert.equal(x.boundaryId, y.boundaryId);
        assert.deepEqual(x.from, y.to);
        assert.deepEqual(x.to, y.from);
        assert.notEqual(x.direction, y.direction);
        assert.deepEqual(x.position, y.position);
        assert.equal(
          toMillimetres(y.distanceFromStart),
          32 - toMillimetres(x.distanceFromStart),
        );
      }
    }
  }
  assertLocations(backward, reversed);
});

test('TASK-042 tangent contact produces neither lumen span nor penetration knot', () => {
  const path = query.execute(segment(p(0, -13, 2), p(0, -13, 20)));
  assert.equal(path.length, 1);
  assert.deepEqual(ids(path[0].memberships), ['region.soft']);
  assert.deepEqual(crossings(path), []);
});

test('TASK-042 exact coincident transitions form one knot with sorted sets, no zero spans', () => {
  const a = regionFor(box(0), 'region.Z');
  const b = regionFor(box(2), 'region.a');
  const c = regionFor(box(2), 'region.B');
  const path = new Query(
    [b, a, c],
    [
      boundaryFor(c, 'boundary.z'),
      boundaryFor(a, 'boundary.A'),
      boundaryFor(b, 'boundary.a'),
    ],
  ).execute(zSegment(-2, 4));
  const knot = transitions(path).find((e) => e.at.position.value.z === 1);
  assert.deepEqual(ids(knot.entered), ['region.B', 'region.a']);
  assert.deepEqual(ids(knot.exited), ['region.Z']);
  assert.deepEqual(
    knot.boundaryCrossings.map((c) => c.boundaryId),
    ['boundary.A', 'boundary.a', 'boundary.z'],
  );
  assert.equal(
    transitions(path).filter((e) => e.at.position.value.z === 1).length,
    1,
  );
  assert.equal(spans(path).length, 4);
  assertLocations(path, zSegment(-2, 4));
});

test('TASK-042 real thin region and near transitions across different regions are not epsilon-merged', () => {
  // Binary-exact geometry permits strict position equality without a tolerance.
  const thickness = 2 ** -30;
  const thin = regionFor(box(0, thickness));
  const path = new Query([thin], [boundaryFor(thin)]).execute(
    zSegment(-thickness, thickness),
  );
  assert.deepEqual(
    spans(path).map((e) => ids(e.memberships)),
    [[], ['region.test'], []],
  );
  assert.equal(
    spans(path)[1].end.position.value.z - spans(path)[1].start.position.value.z,
    thickness,
  );
  assert.equal(crossings(path).length, 2);
  const decimalThin = regionFor(box(0, 1e-8));
  const decimalPath = new Query(
    [decimalThin],
    [boundaryFor(decimalThin)],
  ).execute(zSegment(-1e-8, 1e-8));
  assert.deepEqual(
    spans(decimalPath).map((e) => ids(e.memberships)),
    [[], [decimalThin.regionId], []],
  );
  assert.equal(crossings(decimalPath).length, 2);
  assert.ok(spans(decimalPath)[1].end.t > spans(decimalPath)[1].start.t);
  const a = regionFor(box(0), 'region.a');
  const b = regionFor(box(2 + 1e-8), 'region.b');
  const gapPath = new Query([a, b]).execute(zSegment(-2, 4));
  const gap = spans(gapPath)[2];
  assert.deepEqual(gap.memberships, []);
  assert.ok(gap.end.t > gap.start.t);
  assert.ok(
    toMillimetres(gap.end.distanceFromStart) -
      toMillimetres(gap.start.distanceFromStart) <
      1e-7,
  );
});

test('TASK-042 repeated runs and permutations of regions, boundary bindings and hit order serialize identically', () => {
  const expected = JSON.stringify(query.execute(veinSegment));
  for (let i = 0; i < regions.length; i++) {
    const ordered = [...regions.slice(i), ...regions.slice(0, i)]
      .reverse()
      .map((r) => ({
        ...r,
        representation: wrap(r.representation, (s) => {
          const hits = r.representation.intersectSegment(s);
          return [...hits, ...hits].reverse();
        }),
      }));
    const permuted = new Query(ordered, [...boundaries].reverse());
    for (let run = 0; run < 3; run++)
      assert.equal(JSON.stringify(permuted.execute(veinSegment)), expected);
  }
});

test('TASK-042 one disconnected region supports repeated entries and exits', () => {
  const boxes = [box(-3), box(3)];
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
    distanceToPoint: () => {
      throw new Error('Traversal must not use distance query');
    },
  };
  const region = regionFor(representation);
  const path = new Query([region], [boundaryFor(region)]).execute(
    zSegment(-5, 5),
  );
  assert.deepEqual(
    crossings(path).map((c) => [c.direction, c.position.value.z]),
    [
      ['entry', -4],
      ['exit', -2],
      ['entry', 2],
      ['exit', 4],
    ],
  );
  assert.deepEqual(
    spans(path).map((e) => ids(e.memberships)),
    [[], ['region.test'], [], ['region.test'], []],
  );
});

test('TASK-042 endpoint-only crossings are excluded while first and last open spans describe occupancy', () => {
  const region = regionFor(box());
  const q = new Query([region], [boundaryFor(region)]);
  for (const [a, b, inside] of [
    [-2, -1, false],
    [-1, 0, true],
    [0, 1, true],
    [1, 2, false],
    [-1, 1, true],
    [-1, -2, false],
    [0, 0.5, true],
  ]) {
    const path = q.execute(zSegment(a, b));
    assert.equal(path.length, 1);
    assert.deepEqual(ids(path[0].memberships), inside ? ['region.test'] : []);
  }
  assert.deepEqual(
    crossings(q.execute(zSegment(-1, 2))).map((c) => [
      c.direction,
      c.position.value.z,
    ]),
    [['exit', 1]],
  );
  assert.deepEqual(
    crossings(q.execute(zSegment(-2, 0))).map((c) => c.direction),
    ['entry'],
  );
});

test('TASK-042 zero length is deterministically empty without geometry calls or a point snapshot', () => {
  const region = regionFor({
    classifyPoint: () => {
      throw new Error('No geometry calls');
    },
    intersectSegment: () => {
      throw new Error('No geometry calls');
    },
  });
  const q = new Query([region], [boundaryFor(region)]);
  for (const z of [-5, -1, 0]) assert.deepEqual(q.execute(zSegment(z, z)), []);
});

test('TASK-042 finite boundary following fails explicitly even without semantic boundary binding', () => {
  for (const bindings of [[], [boundaryFor(regions[0])]]) {
    const q = new Query([regions[0]], bindings);
    assert.throws(
      () => q.execute(segment(p(-60, 0, 1), p(60, 0, 1))),
      /Boundary overlap/,
    );
  }
  assert.throws(
    () => query.execute(segment(p(-40, -13, 10), p(40, -13, 10))),
    PenetrationPathFailure,
  );
});

test('TASK-042 same structure supports multiple stable regions and geometry replacement without identity inference', () => {
  const a = regionFor(box(-3), 'region.a');
  const b = { ...regionFor(box(3), 'region.b'), membershipRoles: ['lumen'] };
  const path = new Query([a, b]).execute(zSegment(-5, 5));
  const active = spans(path).flatMap((e) => e.memberships);
  assert.deepEqual(
    active.map((m) => [m.regionId, m.structureId]),
    [
      ['region.a', 'structure.opaque'],
      ['region.b', 'structure.opaque'],
    ],
  );
  assert.deepEqual(active[1].lumen, { vascularLumenKind: null });
  const replacement = new Query([
    {
      ...a,
      name: 'arterial vein skin',
      representation: wrap(a.representation, (s) =>
        a.representation.intersectSegment(s),
      ),
    },
    b,
  ]);
  assert.deepEqual(replacement.execute(zSegment(-5, 5)), path);
});

test('TASK-042 nested and multi-role regions preserve every membership and sort roles independently', () => {
  const a = regionFor(box(0, 4), 'region.a');
  const b = {
    ...regionFor(box(), 'region.b'),
    membershipRoles: ['tissue', 'lumen'],
    vascularLumenKind: 'arterial',
  };
  const path = new Query([b, a]).execute(zSegment(-3, 3));
  assert.deepEqual(
    spans(path).map((e) => ids(e.memberships)),
    [[], ['region.a'], ['region.a', 'region.b'], ['region.a'], []],
  );
  assert.deepEqual(
    new Query([
      a,
      { ...b, membershipRoles: ['lumen', 'tissue', 'lumen'] },
    ]).execute(zSegment(-3, 3)),
    path,
  );
});

test('TASK-042 invalid bindings, points and unresolved geometry fail rather than guess', () => {
  const region = regionFor(box());
  assert.throws(() => new Query([region, region]), /Duplicate region/);
  assert.throws(
    () => new Query([], [boundaryFor(region)]),
    /Unknown boundary region/,
  );
  assert.throws(
    () => new Query([region], [boundaryFor(region), boundaryFor(region)]),
    /Duplicate region/,
  );
  assert.throws(
    () => new Query([{ ...region, representation: {} }]),
    /lacks region classification/,
  );
  assert.throws(
    () => new Query([{ ...region, vascularLumenKind: 'venous' }]),
    /requires lumen membership/,
  );
  assert.throws(
    () =>
      new Query([
        { ...region, membershipRoles: ['lumen'], vascularLumenKind: 'unknown' },
      ]),
    /Invalid vascular/,
  );
  assert.throws(() => query.execute(zSegment(NaN, 1)), BoundaryQueryFailure);
  assert.throws(
    () => query.execute(zSegment(-Number.MAX_VALUE, Number.MAX_VALUE)),
    /overflow/,
  );
  for (const hits of [
    [p(0, 0, 0.5), p(0, 0, 0.5 + Number.EPSILON / 2)],
    [p(1, 0, 0.5)],
    [p(0, 0, 2)],
  ]) {
    const broken = regionFor(wrap(box(), () => hits));
    assert.throws(
      () => new Query([broken]).execute(zSegment(0, 1)),
      BoundaryQueryFailure,
    );
  }
  const broken = regionFor({
    ...wrap(box(), () => []),
    classifyPoint: () => 'unknown',
  });
  assert.throws(
    () => new Query([broken]).execute(zSegment(0, 1)),
    /Invalid region classification/,
  );
});

test('TASK-042 empty region set is one outside span and oblique distances are physical Length', () => {
  const source = segment(p(0, 0, 0), p(3, 4, 0));
  const path = new Query([]).execute(source);
  assert.equal(path.length, 1);
  assert.deepEqual(path[0].memberships, []);
  assert.equal(toMillimetres(path[0].end.distanceFromStart), 5);
  assertLocations(path, source);
});
