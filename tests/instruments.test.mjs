import assert from 'node:assert/strict';
import test from 'node:test';
import { patientSpacePoint } from '../packages/math/dist/index.js';
import { millimetres } from '../packages/units/dist/index.js';
import {
  createInstrumentDefinition,
  createInstrumentInstance,
  createInstrumentPart,
  createInstrumentPose,
  createNeedleDefinition,
  instrumentDefinitionId,
  instrumentInstanceId,
  instrumentPartId,
} from '../packages/instruments/dist/index.js';

test('TASK-065 builds a generic instrument definition from semantic parts', () => {
  const bodyId = instrumentPartId('part.body');
  const workingEndId = instrumentPartId('part.working-end');
  const inputParts = [
    createInstrumentPart({ id: bodyId, name: 'Body' }),
    createInstrumentPart({
      id: workingEndId,
      name: 'Working end',
      parentPartId: bodyId,
    }),
  ];
  const definition = createInstrumentDefinition({
    id: instrumentDefinitionId('instrument.generic'),
    name: 'Generic instrument',
    parts: inputParts,
  });

  assert.equal(definition.id, 'instrument.generic');
  assert.equal(definition.parts.length, 2);
  assert.equal(definition.parts[1].parentPartId, bodyId);
  assert.ok(Object.isFrozen(definition));
  assert.ok(Object.isFrozen(definition.parts));
  assert.ok(Object.isFrozen(definition.parts[0]));

  inputParts.pop();
  assert.equal(definition.parts.length, 2);
});

test('TASK-065 instrument pose is explicit Patient Space with a unit quaternion', () => {
  const position = patientSpacePoint(12.5, -4, 31.25);
  const pose = createInstrumentPose({
    position,
    orientation: { x: 0, y: Math.SQRT1_2, z: 0, w: Math.SQRT1_2 },
  });
  const instance = createInstrumentInstance({
    id: instrumentInstanceId('instrument-instance.1'),
    definitionId: instrumentDefinitionId('instrument.generic'),
    pose,
  });

  assert.deepEqual(instance.pose.position, position);
  assert.equal(instance.pose.position.space, 'patient');
  assert.equal(instance.pose.position.kind, 'point');
  assert.ok(
    Math.abs(Math.hypot(...Object.values(instance.pose.orientation)) - 1) <
      1e-12,
  );
  assert.ok(Object.isFrozen(instance));
  assert.ok(Object.isFrozen(instance.pose));
  assert.ok(Object.isFrozen(instance.pose.position.value));
});

test('TASK-065 rejects malformed identities, part graphs, coordinates, and rotations', () => {
  assert.throws(() => instrumentDefinitionId('   '), /non-empty/);
  const partId = instrumentPartId('part.same');
  assert.throws(
    () =>
      createInstrumentPart({ id: partId, name: 'Same', parentPartId: partId }),
    /own parent/,
  );
  assert.throws(
    () =>
      createInstrumentDefinition({
        id: instrumentDefinitionId('instrument.bad-duplicate'),
        name: 'Bad duplicate',
        parts: [
          createInstrumentPart({ id: partId, name: 'First' }),
          createInstrumentPart({ id: partId, name: 'Second' }),
        ],
      }),
    /Duplicate instrument part ID/,
  );
  assert.throws(
    () =>
      createInstrumentDefinition({
        id: instrumentDefinitionId('instrument.bad-parent'),
        name: 'Bad parent',
        parts: [
          createInstrumentPart({
            id: instrumentPartId('part.child'),
            name: 'Child',
            parentPartId: instrumentPartId('part.missing'),
          }),
        ],
      }),
    /unknown parent/,
  );
  const cycleA = instrumentPartId('part.cycle-a');
  const cycleB = instrumentPartId('part.cycle-b');
  assert.throws(
    () =>
      createInstrumentDefinition({
        id: instrumentDefinitionId('instrument.bad-cycle'),
        name: 'Bad cycle',
        parts: [
          createInstrumentPart({
            id: cycleA,
            name: 'Cycle A',
            parentPartId: cycleB,
          }),
          createInstrumentPart({
            id: cycleB,
            name: 'Cycle B',
            parentPartId: cycleA,
          }),
        ],
      }),
    /must not contain a cycle/,
  );
  assert.throws(
    () =>
      createInstrumentPose({
        position: {
          space: 'patient',
          kind: 'point',
          value: { x: Number.NaN, y: 0, z: 0 },
        },
        orientation: { x: 0, y: 0, z: 0, w: 1 },
      }),
    /finite Patient Space point/,
  );
  assert.throws(
    () =>
      createInstrumentPose({
        position: patientSpacePoint(0, 0, 0),
        orientation: { x: 0, y: 0, z: 0, w: 2 },
      }),
    /unit quaternion/,
  );
});


test('TASK-066 defines a generic needle by semantic tip, bevel, shaft, and lumen parts', () => {
  const shaft = instrumentPartId('needle.part.shaft');
  const bevel = instrumentPartId('needle.part.bevel');
  const tip = instrumentPartId('needle.part.tip');
  const lumen = instrumentPartId('needle.part.lumen');
  const definition = createNeedleDefinition({
    id: instrumentDefinitionId('instrument.needle.generic'),
    name: 'Generic needle',
    parts: [
      createInstrumentPart({ id: shaft, name: 'Shaft' }),
      createInstrumentPart({ id: bevel, name: 'Bevel', parentPartId: shaft }),
      createInstrumentPart({ id: tip, name: 'Tip', parentPartId: bevel }),
      createInstrumentPart({ id: lumen, name: 'Lumen', parentPartId: shaft }),
    ],
    functionalParts: { tip, bevel, shaft, lumen },
    geometry: {
      shaftLength: millimetres(40),
      bevelLength: millimetres(3),
      outerDiameter: millimetres(1.2),
      lumenDiameter: millimetres(0.7),
    },
  });

  assert.equal(definition.kind, 'needle');
  assert.equal(definition.functionalParts.tip, tip);
  assert.equal(definition.geometry.shaftLength, 40);
  assert.ok(Object.isFrozen(definition));
  assert.ok(Object.isFrozen(definition.functionalParts));
  assert.ok(Object.isFrozen(definition.geometry));
});

test('TASK-066 needle definition fails closed on invalid functional mapping and geometry', () => {
  const shaft = instrumentPartId('needle.bad.shaft');
  const bevel = instrumentPartId('needle.bad.bevel');
  const tip = instrumentPartId('needle.bad.tip');
  const lumen = instrumentPartId('needle.bad.lumen');
  const parts = [
    createInstrumentPart({ id: shaft, name: 'Shaft' }),
    createInstrumentPart({ id: bevel, name: 'Bevel' }),
    createInstrumentPart({ id: tip, name: 'Tip' }),
    createInstrumentPart({ id: lumen, name: 'Lumen' }),
  ];
  const base = {
    id: instrumentDefinitionId('instrument.needle.bad'),
    name: 'Bad needle',
    parts,
    functionalParts: { tip, bevel, shaft, lumen },
  };

  assert.throws(
    () =>
      createNeedleDefinition({
        ...base,
        functionalParts: { tip, bevel, shaft, lumen: instrumentPartId('missing') },
        geometry: {
          shaftLength: millimetres(40),
          bevelLength: millimetres(3),
          outerDiameter: millimetres(1.2),
          lumenDiameter: millimetres(0.7),
        },
      }),
    /not in the instrument definition/,
  );
  assert.throws(
    () =>
      createNeedleDefinition({
        ...base,
        geometry: {
          shaftLength: millimetres(40),
          bevelLength: millimetres(41),
          outerDiameter: millimetres(1.2),
          lumenDiameter: millimetres(0.7),
        },
      }),
    /bevel length must not exceed shaft length/,
  );
  assert.throws(
    () =>
      createNeedleDefinition({
        ...base,
        geometry: {
          shaftLength: millimetres(40),
          bevelLength: millimetres(3),
          outerDiameter: millimetres(1),
          lumenDiameter: millimetres(1),
        },
      }),
    /lumen diameter must be smaller/,
  );
});
