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
  createNeedleInstance,
  needleAdvanceIntent,
  needleRetractIntent,
  needleRotationIntent,
  needleTranslationIntent,
  normalizedControlAxis,
  normalizedControlMagnitude,
  instrumentDefinitionId,
  instrumentInstanceId,
  instrumentPartId,
  updateNeedlePose,
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
        functionalParts: {
          tip,
          bevel,
          shaft,
          lumen: instrumentPartId('missing'),
        },
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

function task067NeedleDefinition() {
  const shaft = instrumentPartId('task067.shaft');
  const bevel = instrumentPartId('task067.bevel');
  const tip = instrumentPartId('task067.tip');
  const lumen = instrumentPartId('task067.lumen');
  return createNeedleDefinition({
    id: instrumentDefinitionId('task067.needle'),
    name: 'TASK-067 needle',
    parts: [
      createInstrumentPart({ id: shaft, name: 'Shaft' }),
      createInstrumentPart({ id: bevel, name: 'Bevel' }),
      createInstrumentPart({ id: tip, name: 'Tip' }),
      createInstrumentPart({ id: lumen, name: 'Lumen' }),
    ],
    functionalParts: { tip, bevel, shaft, lumen },
    geometry: {
      shaftLength: millimetres(40),
      bevelLength: millimetres(3),
      outerDiameter: millimetres(1.2),
      lumenDiameter: millimetres(0.7),
    },
  });
}

test('TASK-067 needle instance derives tip position, direction, and trajectory from pose', () => {
  const definition = task067NeedleDefinition();
  const instance = createNeedleInstance({
    id: instrumentInstanceId('task067.instance'),
    definition,
    pose: createInstrumentPose({
      position: patientSpacePoint(1, 2, 3),
      orientation: { x: 0, y: 0, z: 0, w: 1 },
    }),
  });

  assert.deepEqual(instance.tipPosition.value, { x: 1, y: 2, z: 3 });
  assert.deepEqual(instance.tipDirection.value, { x: 0, y: 0, z: 1 });
  assert.equal(instance.trajectory.length, 1);
  assert.ok(Object.isFrozen(instance.trajectory));
  assert.ok(Object.isFrozen(instance.trajectory[0]));
});

test('TASK-067 pose updates rotate +Z tip direction and append only changed samples', () => {
  const definition = task067NeedleDefinition();
  const initial = createNeedleInstance({
    id: instrumentInstanceId('task067.rotated'),
    definition,
    pose: createInstrumentPose({
      position: patientSpacePoint(0, 0, 0),
      orientation: { x: 0, y: 0, z: 0, w: 1 },
    }),
  });
  const quarterTurnY = {
    x: 0,
    y: Math.SQRT1_2,
    z: 0,
    w: Math.SQRT1_2,
  };
  const moved = updateNeedlePose(
    initial,
    createInstrumentPose({
      position: patientSpacePoint(4, -2, 8),
      orientation: quarterTurnY,
    }),
  );

  assert.ok(Math.abs(moved.tipDirection.value.x - 1) < 1e-12);
  assert.ok(Math.abs(moved.tipDirection.value.y) < 1e-12);
  assert.ok(Math.abs(moved.tipDirection.value.z) < 1e-12);
  assert.equal(moved.trajectory.length, 2);

  const repeated = updateNeedlePose(moved, moved.pose);
  assert.equal(repeated.trajectory.length, 2);
});

test('TASK-068 normalizes device-independent needle control intents', () => {
  assert.deepEqual(needleTranslationIntent(-1, 0.5), {
    type: 'translate',
    lateral: -1,
    vertical: 0.5,
  });
  assert.deepEqual(needleRotationIntent(0.25, -0.75), {
    type: 'rotate',
    yaw: 0.25,
    pitch: -0.75,
  });
  assert.deepEqual(needleAdvanceIntent(1), { type: 'advance', amount: 1 });
  assert.deepEqual(needleRetractIntent(0), { type: 'retract', amount: 0 });
});

test('TASK-068 rejects out-of-range and non-finite normalized input', () => {
  assert.throws(() => normalizedControlAxis(1.01), /within \[-1, 1\]/);
  assert.throws(() => normalizedControlAxis(Number.NaN), /finite/);
  assert.throws(() => normalizedControlMagnitude(-0.01), /within \[0, 1\]/);
  assert.throws(() => normalizedControlMagnitude(Infinity), /finite/);
});
