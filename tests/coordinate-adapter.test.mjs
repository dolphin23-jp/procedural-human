import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  patientSpacePoint as p,
  patientSpaceVector as v,
  renderSpacePoint as r,
  renderSpaceVector as rv,
} from '../packages/math/dist/index.js';
import { millimetres } from '../packages/units/dist/index.js';
import { PatientRenderTransform } from '../packages/rendering-core/dist/index.js';
import {
  createFixtureCoordinateTransform,
  ThreeFixtureRenderer,
} from '../packages/rendering-three/dist/index.js';
import {
  patientToThreeMatrix,
  renderPointToThree,
  renderVectorToThree,
  threePointToRender,
  threeVectorToRender,
} from '../packages/rendering-three/dist/three-coordinates.js';
import { createFixtureGroup } from '../packages/rendering-three/dist/fixture-scene.js';
import { createFixtureCamera } from '../packages/rendering-three/dist/fixture-view.js';

const identity = { x: 0, y: 0, z: 0, w: 1 };
const quarterTurn = { x: 0, y: 0, z: Math.SQRT1_2, w: Math.SQRT1_2 };
const config = (origin = p(0, 0, 0), scale = 1, rotation = identity) => ({
  patientOrigin: origin,
  millimetresPerRenderUnit: millimetres(scale),
  patientToRenderRotation: rotation,
});

// Double-precision coordinate math tolerance in patient mm (not medical accuracy).
const EPSILON_MM = 1e-9;
function close(actual, expected, epsilon = EPSILON_MM) {
  for (const axis of ['x', 'y', 'z']) {
    assert.ok(
      Math.abs(actual[axis] - expected[axis]) <= epsilon,
      `${axis}: ${actual[axis]} != ${expected[axis]} (tolerance ${epsilon})`,
    );
  }
}

test('TASK-047 actual camera projection is invariant under render origin, rotation and scale', () => {
  const original = new PatientRenderTransform(config());
  const expectedCamera = createFixtureCamera(original);
  expectedCamera.updateMatrixWorld(true);
  const cases = [
    createFixtureCoordinateTransform(),
    new PatientRenderTransform(config(p(17, -23, 39), 10, quarterTurn)),
  ];
  for (const coordinates of cases) {
    const camera = createFixtureCamera(coordinates);
    camera.updateMatrixWorld(true);
    const scale = coordinates.config.millimetresPerRenderUnit;
    assert.ok(Math.abs(camera.near * scale - 0.1) < 1e-12);
    assert.ok(Math.abs(camera.far * scale - 500) < 1e-12);
    for (const point of [
      p(0, 0, 0),
      p(0, -10, 10),
      p(0, 10, 15),
      p(50, 40, 31),
    ]) {
      const before = renderPointToThree(
        original.patientPointToRender(point),
      ).project(expectedCamera);
      const after = renderPointToThree(
        coordinates.patientPointToRender(point),
      ).project(camera);
      close(after, before, 1e-12);
    }
  }
});

test('TASK-047 known coordinates independently establish origin, rotation, unit scale and handedness', () => {
  const explicitIdentity = new PatientRenderTransform(config());
  assert.deepEqual(
    explicitIdentity.patientPointToRender(p(2, -3, 4)),
    r(2, -3, 4),
  );
  const transform = new PatientRenderTransform(
    config(p(10, 20, 30), 10, quarterTurn),
  );
  close(transform.patientPointToRender(p(20, 40, 60)).value, {
    x: -2,
    y: 1,
    z: 3,
  });
  close(transform.renderPointToPatient(r(-2, 1, 3)).value, {
    x: 20,
    y: 40,
    z: 60,
  });
  close(transform.patientPointToRender(p(10, 20, 30)).value, {
    x: 0,
    y: 0,
    z: 0,
  });
  // Right-handed Z rotation sends +X to +Y, +Y to -X, and leaves +Z unchanged.
  close(transform.patientVectorToRender(v(10, 0, 0)).value, {
    x: 0,
    y: 1,
    z: 0,
  });
  close(transform.patientVectorToRender(v(0, 10, 0)).value, {
    x: -1,
    y: 0,
    z: 0,
  });
  close(transform.patientVectorToRender(v(0, 0, 10)).value, {
    x: 0,
    y: 0,
    z: 1,
  });
});

test('TASK-047 deterministic points and vectors round-trip through real Three Vector3 objects', () => {
  const oblique = {
    x: 1 / Math.sqrt(30),
    y: 2 / Math.sqrt(30),
    z: 3 / Math.sqrt(30),
    w: 4 / Math.sqrt(30),
  };
  for (const rotation of [identity, quarterTurn, oblique]) {
    for (const scale of [0.1, 1, 100, 1000]) {
      const transform = new PatientRenderTransform(
        config(p(104.25, -250.5, 900.125), scale, rotation),
      );
      for (let i = 0; i < 40; i++) {
        const point = p(i * 10.25 - 180, (i * i) / 7, 40 - i / 3);
        const render = transform.patientPointToRender(point);
        const three = renderPointToThree(render);
        assert.equal(three.isVector3, true);
        close(
          transform.renderPointToPatient(threePointToRender(three)).value,
          point.value,
        );
        close(
          transform.patientPointToRender(transform.renderPointToPatient(render))
            .value,
          render.value,
        );
        const vector = v(point.value.x, point.value.y, point.value.z);
        const threeVector = renderVectorToThree(
          transform.patientVectorToRender(vector),
        );
        close(
          transform.renderVectorToPatient(threeVectorToRender(threeVector))
            .value,
          vector.value,
        );
      }
    }
  }
});

test('TASK-047 displacement excludes origin and preserves physical distance', () => {
  const a = new PatientRenderTransform(config(p(0, 0, 0), 100, quarterTurn));
  const b = new PatientRenderTransform(
    config(p(900, -600, 400), 100, quarterTurn),
  );
  assert.deepEqual(
    a.patientVectorToRender(v(3, 4, 12)),
    b.patientVectorToRender(v(3, 4, 12)),
  );
  const delta = b.patientVectorToRender(v(3, 4, 12)).value;
  assert.ok(
    Math.abs(Math.hypot(delta.x, delta.y, delta.z) * 100 - 13) < EPSILON_MM,
  );
  const start = b.patientPointToRender(p(10, 20, 30)).value;
  const end = b.patientPointToRender(p(13, 24, 42)).value;
  close({ x: end.x - start.x, y: end.y - start.y, z: end.z - start.z }, delta);
});

test('TASK-047 configuration snapshots and conversions do not alias caller-owned data', () => {
  const source = config(p(10, 20, 30));
  source.patientToRenderRotation = { ...identity };
  const transform = new PatientRenderTransform(source);
  source.patientOrigin.value.x = 999;
  source.patientToRenderRotation.w = 0;
  assert.deepEqual(transform.patientPointToRender(p(10, 20, 30)), r(0, 0, 0));
  assert.throws(() => {
    transform.config.patientOrigin.value.x = 0;
  }, TypeError);
  const render = r(1, 2, 3);
  const three = renderPointToThree(render);
  three.x = 100;
  assert.equal(render.value.x, 1);
  const copy = threePointToRender(three);
  three.x = 200;
  assert.equal(copy.value.x, 100);
});

test('TASK-047 missing transforms, wrong spaces, nonfinite values and invalid scales/rotations fail explicitly', () => {
  assert.throws(
    () => new PatientRenderTransform(),
    /configuration is required/,
  );
  assert.throws(
    () => new ThreeFixtureRenderer(null),
    /Explicit PatientRenderTransform/,
  );
  assert.throws(() => createFixtureGroup(), /Explicit PatientRenderTransform/);
  for (const scale of [0, -1, NaN, Infinity, Number.MIN_VALUE]) {
    assert.throws(
      () => new PatientRenderTransform(config(p(0, 0, 0), scale)),
      /invertible/,
    );
  }
  for (const rotation of [
    null,
    { x: 0, y: 0, z: 0, w: 0 },
    { ...identity, w: 2 },
    { ...identity, x: NaN },
    { ...identity, z: Infinity },
  ]) {
    assert.throws(
      () => new PatientRenderTransform(config(p(0, 0, 0), 1, rotation)),
      /quaternion/,
    );
  }
  assert.throws(
    () => new PatientRenderTransform(config(r(0, 0, 0))),
    /patient-space point/,
  );
  const transform = new PatientRenderTransform(config());
  for (const bad of [NaN, Infinity, -Infinity]) {
    assert.throws(
      () => new PatientRenderTransform(config(p(bad, 0, 0))),
      /finite/,
    );
    assert.throws(() => transform.patientPointToRender(p(bad, 0, 0)), /finite/);
    assert.throws(() => transform.renderPointToPatient(r(0, bad, 0)), /finite/);
    assert.throws(
      () => transform.patientVectorToRender(v(0, 0, bad)),
      /finite/,
    );
    assert.throws(
      () => transform.renderVectorToPatient(rv(0, bad, 0)),
      /finite/,
    );
    assert.throws(() => threePointToRender({ x: bad, y: 0, z: 0 }), /finite/);
  }
  assert.throws(
    () => transform.patientPointToRender(r(0, 0, 0)),
    /patient-space point/,
  );
  assert.throws(
    () => transform.renderPointToPatient(p(0, 0, 0)),
    /render-space point/,
  );
  assert.throws(
    () => transform.patientVectorToRender(p(0, 0, 0)),
    /patient-space vector/,
  );
  assert.throws(
    () => transform.renderVectorToPatient(r(0, 0, 0)),
    /render-space vector/,
  );
  assert.throws(() => renderPointToThree(p(0, 0, 0)), /render-space point/);
  assert.throws(() => renderVectorToThree(r(0, 0, 0)), /render-space vector/);
  const largeOrigin = new PatientRenderTransform(
    config(p(Number.MAX_VALUE, 0, 0)),
  );
  assert.throws(
    () => largeOrigin.patientPointToRender(p(-Number.MAX_VALUE, 0, 0)),
    /finite/,
  );
  const largeScale = new PatientRenderTransform(
    config(p(0, 0, 0), Number.MAX_VALUE),
  );
  assert.throws(() => largeScale.renderPointToPatient(r(2, 0, 0)), /finite/);
});

test('TASK-047 Three matrix agrees with independently known coordinates and inverse conversion', () => {
  const transform = new PatientRenderTransform(
    config(p(10, 20, 30), 10, quarterTurn),
  );
  const matrix = patientToThreeMatrix(transform);
  const point = renderPointToThree(r(20, 40, 60)); // raw patient numbers solely for testing the patient->world matrix
  point.applyMatrix4(matrix);
  close(point, { x: -2, y: 1, z: 3 });
  point.applyMatrix4(matrix.clone().invert());
  close(point, { x: 20, y: 40, z: 60 });
});

test('TASK-047 real fixture meshes apply a single transform to positions, orientation and dimensions', async () => {
  const source = JSON.parse(
    await readFile('fixtures/anatomy/synthetic-anatomy-v1.json', 'utf8'),
  );
  for (const transform of [
    createFixtureCoordinateTransform(),
    new PatientRenderTransform(config(p(17, -23, 39), 10, quarterTurn)),
  ]) {
    const group = createFixtureGroup(transform);
    group.updateMatrixWorld(true);
    assert.equal(group.matrixAutoUpdate, false);
    for (let i = 0; i < source.entities.length; i++) {
      const entity = source.entities[i];
      const mesh = group.children[i];
      const center = p(...entity.geometry.centerMm);
      const worldCenter = mesh.getWorldPosition(renderPointToThree(r(0, 0, 0)));
      close(worldCenter, transform.patientPointToRender(center).value);
      close(
        transform.renderPointToPatient(threePointToRender(worldCenter)).value,
        center.value,
      );
      const parameters = mesh.geometry.parameters;
      if (entity.geometry.shape === 'slab') {
        assert.deepEqual(
          [parameters.width, parameters.height, parameters.depth],
          entity.geometry.sizeMm,
        );
      } else {
        assert.equal(parameters.radiusTop, entity.geometry.radiusMm);
        assert.equal(parameters.height, entity.geometry.lengthMm);
        // CylinderGeometry is Y-aligned locally; its existing Z rotation makes it X-aligned in patient space.
        const cap = renderPointToThree(
          r(0, entity.geometry.lengthMm / 2, 0),
        ).applyMatrix4(mesh.matrixWorld);
        const recovered = transform.renderPointToPatient(
          threePointToRender(cap),
        );
        close(recovered.value, {
          x: center.value.x - entity.geometry.lengthMm / 2,
          y: center.value.y,
          z: center.value.z,
        });
      }
      assert.equal(
        mesh.userData.structureId,
        entity.id.replace('entity.', 'structure.'),
      );
      mesh.geometry.dispose();
      mesh.material.dispose();
    }
  }
});
