import assert from 'node:assert/strict';
import test from 'node:test';
import { patientSpacePoint } from '../packages/math/dist/index.js';
import {
  createInstrumentDefinition,
  createInstrumentInstance,
  createInstrumentPart,
  createInstrumentPose,
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
