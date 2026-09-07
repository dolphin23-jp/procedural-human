import assert from 'node:assert/strict';
import test from 'node:test';
import {
  imageVoxelCoordinate as voxel,
  patientSpacePoint as patient,
  patientSpaceDirection as direction,
  patientSpaceVector,
  renderSpacePoint as render,
} from '../packages/math/dist/index.js';
import { millimetres } from '../packages/units/dist/index.js';
import {
  ImagePatientTransform,
  ImagePlaneTransform,
  imagePixelCoordinate,
  createVolumeImagingFrame,
  createPlanarImagingFrame,
  createPatientImagingPlane,
  createImagingObservation,
  IMAGE_BASIS_TOLERANCE,
  IMAGE_PLANE_TOLERANCE_MM,
} from '../packages/imaging-core/dist/index.js';
import { PatientRenderTransform } from '../packages/rendering-core/dist/index.js';
import { ImageRenderCoordinateBridge } from '../packages/session/dist/index.js';
import { createSyntheticVolume } from '../fixtures/imaging/synthetic-volume-v1.mjs';

// Absolute double-precision arithmetic tolerances for this <=100 mm fixture.
// No anatomical/registration accuracy is claimed. Different output units are named.
const PATIENT_MM_TOLERANCE = 1e-10;
const VOXEL_TOLERANCE = 1e-10;
const RENDER_UNIT_TOLERANCE = 1e-11;
function close(actual, expected, tolerance) {
  for (const key of Object.keys(expected))
    assert.ok(
      Math.abs(actual[key] - expected[key]) <= tolerance,
      `${key}: ${actual[key]} != ${expected[key]} (tolerance ${tolerance})`,
    );
}
const frame = () => createSyntheticVolume().frame;
const renderTransform = () =>
  new PatientRenderTransform({
    patientOrigin: patient(-7, 9, 11),
    patientToRenderRotation: { x: 0, y: 0, z: Math.SQRT1_2, w: Math.SQRT1_2 },
    millimetresPerRenderUnit: millimetres(10),
  });
// Independently calculated: columns of the physical basis are
// (0.42,0.56,0), (-0.624,0.468,1.04), (1.6,-1.2,1.5) mm.
const landmarks = [
  [voxel(0, 0, 0), patient(13, -21, 34)],
  [voxel(1, 0, 0), patient(13.42, -20.44, 34)],
  [voxel(0, 1, 0), patient(12.376, -20.532, 35.04)],
  [voxel(0, 0, 1), patient(14.6, -22.2, 35.5)],
  [voxel(2, 1, 2), patient(16.416, -21.812, 38.04)],
  [voxel(-0.5, 1.25, 0.4), patient(12.65, -21.175, 35.9)],
];

test('TASK-057 known oblique anisotropic coordinates establish every axis, origin, center convention and inverse', () => {
  const transform = new ImagePatientTransform(frame());
  for (const [v, p] of landmarks) {
    close(transform.voxelToPatient(v).value, p.value, PATIENT_MM_TOLERANCE);
    const result = transform.patientToVoxel(p);
    assert.equal(result.space, 'image-voxel');
    close(result, { i: v.i, j: v.j, k: v.k }, VOXEL_TOLERANCE);
  }
});

test('TASK-057 synthetic volume samples and continuous coordinates round-trip without clamping', () => {
  const fixture = createSyntheticVolume();
  assert.equal(fixture.samples.length, 36);
  assert.equal(fixture.samples[2 + 4 * (1 + 3 * 2)], 212);
  assert.equal(fixture.observation.sourceType, 'synthetic');
  assert.equal(fixture.provenance.sourceClass, 'development-fixture');
  assert.equal(fixture.provenance.validation.level, 'V0');
  const transform = new ImagePatientTransform(fixture.frame);
  for (const v of [...landmarks.map(([v]) => v), voxel(30.75, -14.5, 4.2)]) {
    close(
      transform.patientToVoxel(transform.voxelToPatient(v)),
      { i: v.i, j: v.j, k: v.k },
      VOXEL_TOLERANCE,
    );
  }
});

test('TASK-057 composition reuses PatientRenderTransform with rotation, translation and physical scale', () => {
  const image = new ImagePatientTransform(frame());
  const bridge = new ImageRenderCoordinateBridge(image, renderTransform());
  const v = voxel(2, 1, 2);
  // r = (-(Py-9), Px+7, Pz-11)/10, independently evaluated.
  const expected = render(3.0812, 2.3416, 2.704);
  close(bridge.voxelToRender(v).value, expected.value, RENDER_UNIT_TOLERANCE);
  close(bridge.renderToVoxel(expected), { i: 2, j: 1, k: 2 }, VOXEL_TOLERANCE);
  for (const [v] of landmarks)
    close(
      bridge.renderToVoxel(bridge.voxelToRender(v)),
      { i: v.i, j: v.j, k: v.k },
      VOXEL_TOLERANCE,
    );
  assert.throws(() => new ImageRenderCoordinateBridge(image), /Explicit/);
  assert.throws(
    () => new ImageRenderCoordinateBridge(null, renderTransform()),
    /Explicit/,
  );
  assert.throws(
    () => bridge.renderToVoxel(patient(0, 0, 0)),
    /render-space point/,
  );
});

test('TASK-057 valid but incorrect axis permutations/signs fail the analytic landmark oracle', () => {
  const original = frame();
  const swapped = {
    ...original,
    directionI: original.directionJ,
    directionJ: original.directionI,
    handedness: 'left',
  };
  const reversed = {
    ...original,
    directionK: direction(-0.64, 0.48, -0.6),
    handedness: 'left',
  };
  for (const wrong of [swapped, reversed]) {
    const actual = new ImagePatientTransform(wrong).voxelToPatient(
      voxel(2, 1, 2),
    );
    assert.throws(
      () => close(actual.value, landmarks[4][1].value, PATIENT_MM_TOLERANCE),
      assert.AssertionError,
    );
  }
  const left = new ImagePatientTransform(reversed);
  close(
    left.voxelToPatient(voxel(0, 0, 1)).value,
    { x: 11.4, y: -19.8, z: 32.5 },
    PATIENT_MM_TOLERANCE,
  );
  close(
    left.patientToVoxel(patient(11.4, -19.8, 32.5)),
    { i: 0, j: 0, k: 1 },
    VOXEL_TOLERANCE,
  );
  // Oriented image-plane normal retains row/column orientation, independent of slice order.
  close(
    left.planeAtK(1).normal.value,
    original.directionK.value,
    IMAGE_BASIS_TOLERANCE,
  );
});

test('TASK-056/057 malformed geometry fails explicitly, including tags and arithmetic overflow', () => {
  const f = frame();
  for (const axis of ['i', 'j', 'k'])
    for (const value of [0, -1, NaN, Infinity, -Infinity, Number.MIN_VALUE]) {
      assert.throws(
        () =>
          new ImagePatientTransform({
            ...f,
            spacing: { ...f.spacing, [axis]: millimetres(value) },
          }),
        /spacing/,
      );
    }
  for (const value of [NaN, Infinity, -Infinity]) {
    assert.throws(
      () => new ImagePatientTransform({ ...f, origin: patient(value, 0, 0) }),
      /finite/,
    );
    assert.throws(
      () =>
        new ImagePatientTransform({
          ...f,
          directionI: {
            space: 'patient',
            kind: 'direction',
            value: { x: value, y: 0, z: 0 },
          },
        }),
      /finite/,
    );
  }
  for (const directionI of [
    direction(1, 0, 0),
    f.directionJ,
    { space: 'patient', kind: 'direction', value: { x: 2, y: 0, z: 0 } },
    { space: 'patient', kind: 'direction', value: { x: 0, y: 0, z: 0 } },
  ]) {
    assert.throws(
      () => new ImagePatientTransform({ ...f, directionI }),
      /orthogonal|unit/,
    );
  }
  assert.throws(
    () => new ImagePatientTransform({ ...f, handedness: 'left' }),
    /handedness/,
  );
  assert.throws(
    () => new ImagePatientTransform({ ...f, handedness: undefined }),
    /handedness/,
  );
  assert.throws(
    () =>
      new ImagePatientTransform({
        ...f,
        directionI: patientSpaceVector(0.6, 0.8, 0),
      }),
    /direction/,
  );
  assert.throws(
    () => new ImagePatientTransform({ ...f, origin: render(0, 0, 0) }),
    /patient-space point/,
  );
  assert.throws(
    () => new ImagePatientTransform({ ...f, indexConvention: 'corners' }),
    /convention/,
  );
  assert.throws(() => new ImagePatientTransform(), /volume-3d/);
  for (const i of [0, -1, 0.5, Infinity, Number.MAX_SAFE_INTEGER + 1])
    assert.throws(
      () =>
        createVolumeImagingFrame({ ...f, dimensions: { ...f.dimensions, i } }),
      /dimensions/,
    );
  const transform = new ImagePatientTransform(f);
  for (const bad of [NaN, Infinity, -Infinity]) {
    assert.throws(() => transform.voxelToPatient(voxel(bad, 0, 0)), /finite/);
    assert.throws(() => transform.patientToVoxel(patient(bad, 0, 0)), /finite/);
  }
  assert.throws(
    () => transform.voxelToPatient(patient(0, 0, 0)),
    /image-voxel/,
  );
  assert.throws(() => transform.voxelToPatient([0, 0, 0]), /image-voxel/);
  assert.throws(
    () => transform.patientToVoxel(render(0, 0, 0)),
    /patient-space/,
  );
  assert.throws(
    () => transform.voxelToPatient(voxel(0, 0, Number.MAX_VALUE)),
    /finite/,
  );
  const tiny = new ImagePatientTransform({
    ...f,
    spacing: { ...f.spacing, i: millimetres(1e-300) },
  });
  assert.throws(() => tiny.patientToVoxel(patient(1e100, 0, 0)), /finite/);
});

test('TASK-057 accepted rounding residuals are preserved and inverted, not silently normalized', () => {
  const f = frame();
  const perturbed = {
    ...f,
    directionI: {
      ...f.directionI,
      value: { ...f.directionI.value, z: IMAGE_BASIS_TOLERANCE / 4 },
    },
  };
  const transform = new ImagePatientTransform(perturbed);
  assert.equal(transform.frame.directionI.value.z, IMAGE_BASIS_TOLERANCE / 4);
  const v = voxel(200, -300, 400);
  close(
    transform.patientToVoxel(transform.voxelToPatient(v)),
    { i: v.i, j: v.j, k: v.k },
    VOXEL_TOLERANCE,
  );
});

const planar = (origin = frame().origin) => {
  const f = frame();
  return {
    kind: 'plane-2d',
    indexConvention: f.indexConvention,
    origin,
    directionI: f.directionI,
    directionJ: f.directionJ,
    spacing: { i: f.spacing.i, j: f.spacing.j },
    dimensions: { i: 4, j: 3 },
  };
};

test('TASK-056/057 2D frames retain in-plane orientation and reject off-plane inverse and implied volumes', () => {
  const transform = new ImagePlaneTransform(planar());
  const expected = patient(13.216, -19.412, 35.04);
  close(
    transform.pixelToPatient(imagePixelCoordinate(2, 1)).value,
    expected.value,
    PATIENT_MM_TOLERANCE,
  );
  close(transform.patientToPixel(expected), { i: 2, j: 1 }, VOXEL_TOLERANCE);
  assert.equal(transform.plane.kind, 'patient-imaging-plane');
  close(
    transform.plane.normal.value,
    frame().directionK.value,
    IMAGE_BASIS_TOLERANCE,
  );
  const n = transform.plane.normal.value;
  assert.throws(
    () =>
      transform.patientToPixel(
        patient(
          expected.value.x + n.x * 0.1,
          expected.value.y + n.y * 0.1,
          expected.value.z + n.z * 0.1,
        ),
      ),
    /outside/,
  );
  assert.throws(() => new ImagePatientTransform(planar()), /volume-3d/);
  assert.throws(() => transform.pixelToPatient(voxel(2, 1, 0)), /image-pixel/);
  assert.throws(
    () =>
      createPatientImagingPlane({
        ...planar(),
        directionJ: frame().directionI,
      }),
    /orthogonal/,
  );
  assert.throws(
    () => createPlanarImagingFrame({ ...planar(), spacing: { i: 0, j: 1 } }),
    /spacing/,
  );
  assert.throws(() => imagePixelCoordinate(NaN, 0), /finite/);
  assert.equal(IMAGE_PLANE_TOLERANCE_MM, 1e-9);
  const plane = new ImagePatientTransform(frame()).planeAtK(0.4);
  close(
    plane.origin.value,
    { x: 13.64, y: -21.48, z: 34.6 },
    PATIENT_MM_TOLERANCE,
  );
});

test('TASK-056 immutable observations distinguish source classes and unavailable registration; independent frames preserve irregular spacing', () => {
  const fixture = createSyntheticVolume();
  assert.throws(
    () =>
      createImagingObservation({ ...fixture.observation, frames: Array(1) }),
    /volume-3d/,
  );
  for (const sourceType of ['acquired', 'synthetic', 'hybrid']) {
    const observation = createImagingObservation({
      ...fixture.observation,
      sourceType,
    });
    assert.equal(observation.sourceType, sourceType);
    assert.equal(observation.patientId, fixture.observation.patientId);
  }
  for (const registrationStatus of ['unknown', 'unregistered']) {
    const unknown = createImagingObservation({
      ...fixture.observation,
      registrationStatus,
      registrationId: null,
      frames: null,
    });
    assert.equal(unknown.frames, null);
    assert.throws(
      () => createImagingObservation({ ...unknown, frames: [frame()] }),
      /null frames/,
    );
  }
  assert.throws(
    () => createImagingObservation({ ...fixture.observation, frames: [] }),
    /explicit frames/,
  );
  assert.throws(
    () =>
      createImagingObservation({
        ...fixture.observation,
        sourceType: 'development-fixture',
      }),
    /source type/,
  );
  assert.throws(
    () => createImagingObservation({ ...fixture.observation, patientId: '' }),
    /identifiers/,
  );
  const volume = new ImagePatientTransform(frame());
  const frames = [0, 0.8, 2.1].map((k) =>
    structuredClone(planar(volume.planeAtK(k).origin)),
  );
  const observation = createImagingObservation({
    ...fixture.observation,
    frames,
  });
  assert.deepEqual(
    observation.frames.map((f) => f.origin),
    frames.map((f) => f.origin),
  );
  frames[0].origin.value.x = 999;
  assert.equal(observation.frames[0].origin.value.x, 13);
  assert.throws(() => {
    observation.frames[0].spacing.i = 100;
  }, TypeError);
  const raw = structuredClone(frame());
  const transform = new ImagePatientTransform(raw);
  raw.origin.value.x = 999;
  raw.directionI.value.x = 0;
  raw.spacing.i = 999;
  close(
    transform.voxelToPatient(voxel(1, 0, 0)).value,
    landmarks[1][1].value,
    PATIENT_MM_TOLERANCE,
  );
});
