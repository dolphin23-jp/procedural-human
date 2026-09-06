import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { entityId, structureId } from '../packages/core/dist/index.js';
import { patientSpacePoint as p } from '../packages/math/dist/index.js';
import {
  DistanceQuery,
  DistanceQueryFailure,
} from '../packages/spatial/dist/distance-query.js';
import {
  AxisAlignedBoxSpatialAdapter,
  XAxisCylinderSpatialAdapter,
} from '../packages/spatial/dist/index.js';
import { millimetres, toMillimetres } from '../packages/units/dist/index.js';

const fixture = JSON.parse(
  await readFile('fixtures/anatomy/synthetic-anatomy-v1.json', 'utf8'),
);

function adapterFor(entity) {
  const geometry = entity.geometry;
  const center = p(...geometry.centerMm);
  if (geometry.shape === 'slab') {
    return new AxisAlignedBoxSpatialAdapter({
      center,
      size: geometry.sizeMm.map(millimetres),
    });
  }
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
  membershipRoles: entity.type === 'fixture-tissue' ? ['tissue'] : ['lumen'],
  vascularLumenKind: entity.vascularLumenKind,
  representation: adapterFor(entity),
}));

const query = new DistanceQuery(entries);

test(
  'TASK-041 returns semantic identity and Length for an explicitly targeted representation',
  () => {
    const result = query.execute(
      p(0, -10, 20),
      structureId('structure.fixture.vein'),
    );
    assert.equal(result.structureId, 'structure.fixture.vein');
    assert.equal(result.canonicalEntityId, 'entity.fixture.vein');
    assert.equal(result.name, 'Fixture Vein');
    assert.equal(toMillimetres(result.distance), 7);
    assert.ok(Object.isFrozen(result));
  },
);

test(
  'TASK-041 distance is zero inside or on the represented solid region',
  () => {
    for (const point of [p(0, -10, 10), p(0, -13, 10)]) {
      assert.equal(
        toMillimetres(
          query.execute(point, structureId('structure.fixture.vein')).distance,
        ),
        0,
      );
    }
  },
);

test(
  'TASK-041 cylinder cap and box distances use the representation geometry',
  () => {
    assert.equal(
      toMillimetres(
        query.execute(p(40, -10, 10), structureId('structure.fixture.vein'))
          .distance,
      ),
      5,
    );
    assert.equal(
      toMillimetres(
        query.execute(
          p(0, 0, -6),
          structureId('structure.fixture.skin'),
        ).distance,
      ),
      5,
    );
  },
);

test(
  'TASK-041 semantic target is explicit rather than inferred from proximity or names',
  () => {
    const point = p(0, -10, 20);
    const vein = query.execute(point, structureId('structure.fixture.vein'));
    const artery = query.execute(point, structureId('structure.fixture.artery'));
    assert.notEqual(
      toMillimetres(vein.distance),
      toMillimetres(artery.distance),
    );

    const renamed = {
      ...entries.find((entry) => entry.structureId === 'structure.fixture.vein'),
      name: 'Opaque structure label',
    };
    const renamedQuery = new DistanceQuery([renamed]);
    const result = renamedQuery.execute(
      point,
      structureId('structure.fixture.vein'),
    );
    assert.equal(result.canonicalEntityId, 'entity.fixture.vein');
    assert.equal(toMillimetres(result.distance), 7);
  },
);

test(
  'TASK-041 rejects unknown targets, duplicate bindings, invalid points, and invalid adapter distances',
  () => {
    assert.throws(
      () => query.execute(p(0, 0, 0), structureId('structure.fixture.missing')),
      DistanceQueryFailure,
    );
    assert.throws(
      () => new DistanceQuery([entries[0], entries[0]]),
      /Duplicate/,
    );
    assert.throws(
      () => query.execute(p(NaN, 0, 0), structureId('structure.fixture.skin')),
      /finite patient-space/,
    );

    for (const bad of [NaN, -1, Infinity]) {
      const entry = {
        ...entries[0],
        representation: {
          ...entries[0].representation,
          distanceToPoint: () => millimetres(bad),
        },
      };
      assert.throws(
        () =>
          new DistanceQuery([entry]).execute(
            p(0, 0, 0),
            structureId('structure.fixture.skin'),
          ),
        /invalid distance/,
      );
    }
  },
);
