import assert from 'node:assert/strict';
import test from 'node:test';
import {
  patientSpaceDirection,
  patientSpacePoint,
} from '../packages/math/dist/index.js';
import { opacity } from '../packages/rendering-core/dist/index.js';
import {
  FIXTURE_STRUCTURE_IDS,
  ThreeCameraRig,
  ThreeSemanticPicker,
  ThreeStructurePresentation,
  createFixtureCoordinateTransform,
  createFixtureSemanticContext,
  dollyIntentFromPixels,
  orbitIntentsFromScreenDrag,
  panIntentFromScreenDrag,
} from '../packages/rendering-three/dist/index.js';
import { patientClippingPlaneToThree } from '../packages/rendering-three/dist/clipping-plane.js';
import { createFixtureGroup } from '../packages/rendering-three/dist/fixture-scene.js';
import { createFixtureCamera } from '../packages/rendering-three/dist/fixture-view.js';
import { renderPointToThree } from '../packages/rendering-three/dist/three-coordinates.js';
import { bindSemanticObjects } from '../packages/rendering-three/dist/semantic-context.js';

function boundFixture() {
  const coordinates = createFixtureCoordinateTransform();
  const context = createFixtureSemanticContext();
  const group = createFixtureGroup(coordinates);
  for (const mesh of group.children) {
    bindSemanticObjects(context, mesh.userData.structureId, [mesh]);
  }
  return { coordinates, context, group };
}

test('TASK-050 opacity is semantic, validated and isolated from shared Three materials', () => {
  const { context, group } = boundFixture();
  const presentation = new ThreeStructurePresentation(context);
  const vein = group.children[2];
  const artery = group.children[3];
  artery.material.dispose();
  artery.material = vein.material;
  const shared = vein.material;

  presentation.setOpacity({
    structureId: FIXTURE_STRUCTURE_IDS.vein,
    opacity: opacity(0.25),
  });

  assert.notEqual(vein.material, shared);
  assert.equal(vein.material.opacity, 0.25);
  assert.equal(vein.material.transparent, true);
  assert.equal(vein.material.depthWrite, false);
  assert.equal(artery.material, shared);
  assert.equal(artery.material.opacity, 0.92);
  assert.throws(
    () =>
      presentation.setOpacity({
        structureId: FIXTURE_STRUCTURE_IDS.vein,
        opacity: 2,
      }),
    /between 0 and 1/,
  );
  presentation.dispose();
  assert.equal(vein.material, shared);
});

test('TASK-051 picking returns patient/canonical semantics rather than mesh names', () => {
  const { coordinates, context, group } = boundFixture();
  const presentation = new ThreeStructurePresentation(context);
  for (const structureId of [
    FIXTURE_STRUCTURE_IDS.skin,
    FIXTURE_STRUCTURE_IDS.softTissue,
    FIXTURE_STRUCTURE_IDS.artery,
  ]) {
    presentation.setVisibility({ structureId, visible: false });
  }
  const camera = createFixtureCamera(coordinates);
  camera.updateMatrixWorld(true);
  group.updateMatrixWorld(true);
  const projected = renderPointToThree(
    coordinates.patientPointToRender({
      space: 'patient',
      kind: 'point',
      value: { x: 0, y: -10, z: 10 },
    }),
  ).project(camera);
  const picker = new ThreeSemanticPicker(context, coordinates);
  const result = picker.pickNdc(projected.x, projected.y, camera);
  assert.equal(result?.patientStructure.id, FIXTURE_STRUCTURE_IDS.vein);
  assert.equal(result?.anatomicalEntity.name, 'Fixture Vein');
  assert.equal(group.children[2].name, 'Fixture Vein');
  group.children[2].name = 'definitely_not_a_vein';
  const renamed = picker.pickNdc(projected.x, projected.y, camera);
  assert.equal(renamed?.patientStructure.id, FIXTURE_STRUCTURE_IDS.vein);
});

test('TASK-052 camera input emits physical intents and uses dimensionless directions', () => {
  const coordinates = createFixtureCoordinateTransform();
  const camera = createFixtureCamera(coordinates);
  const rig = new ThreeCameraRig(camera, coordinates, {
    space: 'patient',
    kind: 'point',
    value: { x: 0, y: 0, z: 12 },
  });
  const frame = rig.inputFrame(800);
  assert.equal(frame.screenRight.kind, 'direction');
  assert.equal(frame.screenUp.kind, 'direction');
  assert.ok(frame.millimetresPerPixel > 0);
  assert.ok(
    Math.abs(Math.hypot(...Object.values(frame.screenRight.value)) - 1) < 1e-9,
  );

  const orbit = orbitIntentsFromScreenDrag(frame, 20, -10);
  assert.equal(orbit.length, 2);
  assert.equal(orbit[0].axis.kind, 'direction');
  assert.equal(panIntentFromScreenDrag(frame, 12, 8).offset.kind, 'vector');
  assert.equal(dollyIntentFromPixels(frame, 10).type, 'dolly');
  for (const intent of orbit) rig.apply(intent);
  rig.apply(panIntentFromScreenDrag(rig.inputFrame(800), 4, -3));
  rig.apply(dollyIntentFromPixels(rig.inputFrame(800), 5));

  assert.throws(() => patientSpaceDirection(2, 0, 0), /unit direction/);
});

test(
  'TASK-054 structure metadata comes from canonical semantics and preserves unavailable accuracy',
  () => {
    const { context, group } = boundFixture();
    const identity = context.identityFor(FIXTURE_STRUCTURE_IDS.vein);

    assert.equal(identity.anatomicalEntity.name, 'Fixture Vein');
    assert.equal(
      identity.anatomicalEntity.provenance.sourceClass,
      'development-fixture',
    );
    assert.equal(identity.anatomicalEntity.validation.level, 'V0');
    assert.equal(identity.anatomicalEntity.accuracy.geometryAccuracy, null);

    group.children[2].name = 'high-confidence-real-vein';
    const sameIdentity = context.identityFor(FIXTURE_STRUCTURE_IDS.vein);
    assert.equal(sameIdentity.anatomicalEntity.validation.level, 'V0');
    assert.equal(sameIdentity.anatomicalEntity.accuracy.geometryAccuracy, null);
  },
);

test(
  'TASK-055 clipping plane preserves Patient Space keep-positive semantics after render conversion',
  () => {
    const coordinates = createFixtureCoordinateTransform();
    const origin = patientSpacePoint(8, -4, 18);
    const normal = patientSpaceDirection(Math.SQRT1_2, 0, Math.SQRT1_2);
    const plane = patientClippingPlaneToThree({ origin, normal }, coordinates);

    const onPlane = renderPointToThree(
      coordinates.patientPointToRender(origin),
    );
    const keptPoint = renderPointToThree(
      coordinates.patientPointToRender(
        patientSpacePoint(
          origin.value.x + normal.value.x * 10,
          origin.value.y + normal.value.y * 10,
          origin.value.z + normal.value.z * 10,
        ),
      ),
    );
    const clippedPoint = renderPointToThree(
      coordinates.patientPointToRender(
        patientSpacePoint(
          origin.value.x - normal.value.x * 10,
          origin.value.y - normal.value.y * 10,
          origin.value.z - normal.value.z * 10,
        ),
      ),
    );

    assert.ok(Math.abs(plane.distanceToPoint(onPlane)) < 1e-12);
    assert.ok(plane.distanceToPoint(keptPoint) > 0);
    assert.ok(plane.distanceToPoint(clippedPoint) < 0);
    assert.throws(
      () =>
        patientClippingPlaneToThree(
          {
            origin,
            normal: {
              space: 'patient',
              kind: 'direction',
              value: { x: 2, y: 0, z: 0 },
            },
          },
          coordinates,
        ),
      /unit direction/,
    );
  },
);
