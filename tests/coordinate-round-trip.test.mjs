import assert from 'node:assert/strict';
import test from 'node:test';
import {
  imageVoxelCoordinate as voxel,
  patientSpaceDirection as direction,
  patientSpacePoint as patient,
} from '../packages/math/dist/index.js';
import { millimetres } from '../packages/units/dist/index.js';
import {
  IMAGE_BASIS_TOLERANCE,
  ImagePatientTransform,
  createVolumeImagingFrame,
} from '../packages/imaging-core/dist/index.js';
import { PatientRenderTransform } from '../packages/rendering-core/dist/index.js';
import { ImageRenderCoordinateBridge } from '../packages/session/dist/index.js';
import { createSyntheticVolume } from '../fixtures/imaging/synthetic-volume-v1.mjs';

// TASK-062 numerical contract. These are floating-point arithmetic tolerances only;
// they are not anatomical accuracy or imaging-registration accuracy claims.
const PATIENT_MM_TOLERANCE = 1e-9;
const VOXEL_INDEX_TOLERANCE = 1e-9;
const RENDER_UNIT_TOLERANCE = 1e-10;

function closeVec3(actual, expected, tolerance, label) {
  for (const axis of ['x', 'y', 'z']) {
    assert.ok(
      Math.abs(actual[axis] - expected[axis]) <= tolerance,
      `${label} ${axis}: ${actual[axis]} != ${expected[axis]} (tolerance ${tolerance})`,
    );
  }
}

function closeVoxel(actual, expected, tolerance = VOXEL_INDEX_TOLERANCE) {
  assert.equal(actual.space, 'image-voxel');
  for (const axis of ['i', 'j', 'k']) {
    assert.ok(
      Math.abs(actual[axis] - expected[axis]) <= tolerance,
      `voxel ${axis}: ${actual[axis]} != ${expected[axis]} (tolerance ${tolerance})`,
    );
  }
}

const identity = Object.freeze({ x: 0, y: 0, z: 0, w: 1 });
const quarterTurnZ = Object.freeze({
  x: 0,
  y: 0,
  z: Math.SQRT1_2,
  w: Math.SQRT1_2,
});
const obliqueQuaternion = Object.freeze({
  x: 1 / Math.sqrt(30),
  y: 2 / Math.sqrt(30),
  z: 3 / Math.sqrt(30),
  w: 4 / Math.sqrt(30),
});

function imageFrames() {
  const source = createSyntheticVolume().frame;
  const descendingK = createVolumeImagingFrame({
    ...source,
    origin: patient(91.25, -47.5, 13.75),
    directionK: direction(-0.64, 0.48, -0.6),
    handedness: 'left',
    spacing: {
      i: millimetres(0.55),
      j: millimetres(1.75),
      k: millimetres(3.2),
    },
    dimensions: { i: 9, j: 7, k: 5 },
  });
  const acceptedResidual = createVolumeImagingFrame({
    ...source,
    origin: patient(-125.25, 400.5, -72.75),
    directionI: {
      ...source.directionI,
      value: {
        ...source.directionI.value,
        z: IMAGE_BASIS_TOLERANCE / 4,
      },
    },
    spacing: {
      i: millimetres(0.33),
      j: millimetres(2.2),
      k: millimetres(4.75),
    },
    dimensions: { i: 11, j: 6, k: 8 },
  });
  return [
    ['fixture-oblique-right-handed', source],
    ['descending-k-left-handed', descendingK],
    ['accepted-basis-rounding-residual', acceptedResidual],
  ];
}

function renderTransforms() {
  return [
    [
      'identity',
      new PatientRenderTransform({
        patientOrigin: patient(0, 0, 0),
        patientToRenderRotation: identity,
        millimetresPerRenderUnit: millimetres(1),
      }),
    ],
    [
      'translated-quarter-turn',
      new PatientRenderTransform({
        patientOrigin: patient(-7, 9, 11),
        patientToRenderRotation: quarterTurnZ,
        millimetresPerRenderUnit: millimetres(10),
      }),
    ],
    [
      'oblique-small-render-units',
      new PatientRenderTransform({
        patientOrigin: patient(275.5, -810.25, 33.125),
        patientToRenderRotation: obliqueQuaternion,
        millimetresPerRenderUnit: millimetres(0.125),
      }),
    ],
    [
      'oblique-large-render-units',
      new PatientRenderTransform({
        patientOrigin: patient(-1200, 640, 2050),
        patientToRenderRotation: obliqueQuaternion,
        millimetresPerRenderUnit: millimetres(250),
      }),
    ],
  ];
}

function samplesFor(frame) {
  const { i, j, k } = frame.dimensions;
  return [
    voxel(0, 0, 0),
    voxel(i - 1, j - 1, k - 1),
    voxel((i - 1) / 2, (j - 1) / 3, (k - 1) * 0.75),
    voxel(-0.25, j + 0.5, -1.125),
    voxel(i + 13.375, -7.75, k + 4.625),
  ];
}

test('TASK-062 known waypoint prevents a self-consistent but wrong coordinate convention', () => {
  const image = new ImagePatientTransform(createSyntheticVolume().frame);
  const render = new PatientRenderTransform({
    patientOrigin: patient(-7, 9, 11),
    patientToRenderRotation: quarterTurnZ,
    millimetresPerRenderUnit: millimetres(10),
  });
  const bridge = new ImageRenderCoordinateBridge(image, render);
  const source = voxel(2, 1, 2);

  const patientPoint = image.voxelToPatient(source);
  closeVec3(
    patientPoint.value,
    { x: 16.416, y: -21.812, z: 38.04 },
    PATIENT_MM_TOLERANCE,
    'patient waypoint',
  );
  closeVec3(
    bridge.voxelToRender(source).value,
    { x: 3.0812, y: 2.3416, z: 2.704 },
    RENDER_UNIT_TOLERANCE,
    'render waypoint',
  );
});

test('TASK-062 voxel -> patient -> render -> patient -> voxel stays within explicit numerical tolerance', () => {
  for (const [frameName, frame] of imageFrames()) {
    const image = new ImagePatientTransform(frame);
    for (const [renderName, render] of renderTransforms()) {
      const bridge = new ImageRenderCoordinateBridge(image, render);
      for (const sourceVoxel of samplesFor(frame)) {
        const patientBefore = image.voxelToPatient(sourceVoxel);
        const renderPoint = render.patientPointToRender(patientBefore);
        const patientAfter = render.renderPointToPatient(renderPoint);
        const recoveredVoxel = image.patientToVoxel(patientAfter);

        assert.equal(patientBefore.space, 'patient');
        assert.equal(renderPoint.space, 'render');
        assert.equal(patientAfter.space, 'patient');
        closeVec3(
          patientAfter.value,
          patientBefore.value,
          PATIENT_MM_TOLERANCE,
          `${frameName}/${renderName} patient round-trip`,
        );
        closeVoxel(recoveredVoxel, sourceVoxel);

        const bridgedRender = bridge.voxelToRender(sourceVoxel);
        closeVec3(
          bridgedRender.value,
          renderPoint.value,
          RENDER_UNIT_TOLERANCE,
          `${frameName}/${renderName} composed render`,
        );
        closeVoxel(bridge.renderToVoxel(bridgedRender), sourceVoxel);
      }
    }
  }
});

test('TASK-062 continuous voxel geometry remains unclamped through the full round trip', () => {
  const frame = createSyntheticVolume().frame;
  const image = new ImagePatientTransform(frame);
  const render = new PatientRenderTransform({
    patientOrigin: patient(31.5, -18.25, 74.75),
    patientToRenderRotation: obliqueQuaternion,
    millimetresPerRenderUnit: millimetres(7.5),
  });
  const bridge = new ImageRenderCoordinateBridge(image, render);
  const outside = voxel(30.75, -14.5, 9.2);

  const patientPoint = image.voxelToPatient(outside);
  const renderPoint = render.patientPointToRender(patientPoint);
  const patientAgain = render.renderPointToPatient(renderPoint);
  closeVec3(
    patientAgain.value,
    patientPoint.value,
    PATIENT_MM_TOLERANCE,
    'continuous outside-volume patient round-trip',
  );
  closeVoxel(image.patientToVoxel(patientAgain), outside);
  closeVoxel(bridge.renderToVoxel(bridge.voxelToRender(outside)), outside);
});
