import assert from 'node:assert/strict';
import test from 'node:test';
import { ImagingPlaneSynchronizer } from '../packages/session/dist/index.js';
import {
  ImagePatientTransform,
  createPatientImagingPlane,
} from '../packages/imaging-core/dist/index.js';
import {
  patientSpacePoint,
  patientSpaceDirection,
} from '../packages/math/dist/index.js';
import { PatientRenderTransform } from '../packages/rendering-core/dist/index.js';
import { millimetres } from '../packages/units/dist/index.js';
import { patientClippingPlaneToThree } from '../packages/rendering-three/dist/clipping-plane.js';
import { renderPointToThree } from '../packages/rendering-three/dist/three-coordinates.js';
import { createSyntheticAxialVolumeFixture } from '../packages/imaging-cornerstone/dist/fixture.js';
import {
  axialVoxelKForPatientPlane,
  createAxialSliceStateAtVoxelK,
} from '../packages/imaging-cornerstone/dist/axial.js';

const frame = createSyntheticAxialVolumeFixture().frame;
const imageTransform = new ImagePatientTransform(frame);
function harness(before = async () => {}) {
  const calls = [],
    rendered = [],
    changes = [];
  const image = {
    currentSlice: createAxialSliceStateAtVoxelK(frame, 4, 4),
    currentPlane: createAxialSliceStateAtVoxelK(frame, 4, 4).plane,
    async setSlice(displayIndex) {
      calls.push(['image', displayIndex]);
      await before();
      this.currentSlice = createAxialSliceStateAtVoxelK(
        frame,
        displayIndex,
        8 - displayIndex,
      );
      this.currentPlane = this.currentSlice.plane;
      return this.currentSlice;
    },
    async setPatientPlane(plane) {
      const k = axialVoxelKForPatientPlane(frame, plane);
      calls.push(['plane', k]);
      await before();
      this.currentSlice = createAxialSliceStateAtVoxelK(frame, 8 - k, k);
      this.currentPlane = this.currentSlice.plane;
      return this.currentSlice;
    },
    async setImagingPlane(plane) {
      calls.push(['oblique', plane]);
      await before();
      this.currentPlane = createPatientImagingPlane(plane);
      return this.currentPlane;
    },
  };
  const sync = new ImagingPlaneSynchronizer({
    image,
    frame,
    render: { setClippingPlane: (plane) => rendered.push(plane) },
    onChange: (state) => changes.push(state),
  });
  return { sync, calls, rendered, changes, image };
}

test('TASK-060 image scroll commits readback plane through a rotated/scaled render frame', async () => {
  const { sync, calls, rendered } = harness();
  const coordinates = new PatientRenderTransform({
    patientOrigin: patientSpacePoint(17, -29, 31),
    patientToRenderRotation: { x: Math.SQRT1_2, y: 0, z: 0, w: Math.SQRT1_2 },
    millimetresPerRenderUnit: millimetres(10),
  });
  for (let displayIndex = 0; displayIndex < 9; displayIndex++) {
    await sync.setImageSlice(displayIndex);
    const plane = rendered.at(-1);
    assert.equal(sync.state.slice.voxelK, 8 - displayIndex);
    assert.equal(plane.origin.value.z, 8 - 2 * displayIndex);
    const three = patientClippingPlaneToThree(plane, coordinates);
    const point = renderPointToThree(
      coordinates.patientPointToRender(
        patientSpacePoint(11, 12, 8 - 2 * displayIndex),
      ),
    );
    assert.ok(Math.abs(three.distanceToPoint(point)) < 1e-10);
  }
  assert.equal(calls.length, 9); // no render → image feedback
});

test('TASK-061 moving the 3D plane resolves image position without assuming display index equals k', async () => {
  const { sync, calls, rendered } = harness();
  for (const k of [0, 8, 2, 6]) {
    await sync.setPlaneAtVoxelK(k);
    assert.equal(sync.state.slice.displayIndex, 8 - k);
    assert.equal(sync.state.slice.voxelK, k);
    assert.equal(rendered.at(-1).origin.value.z, -8 + k * 2);
  }
  assert.deepEqual(calls, [
    ['plane', 0],
    ['plane', 8],
    ['plane', 2],
    ['plane', 6],
  ]);
});

test('TASK-061 rejects oblique, rotated, reversed, off-sample and out-of-volume planes', () => {
  const at = (k) => imageTransform.planeAtK(k);
  for (const k of [-1, 9, 2.25])
    assert.throws(() => axialVoxelKForPatientPlane(frame, at(k)));
  const oblique = createPatientImagingPlane({
    origin: at(4).origin,
    directionI: patientSpaceDirection(Math.SQRT1_2, 0, Math.SQRT1_2),
    directionJ: patientSpaceDirection(0, 1, 0),
  });
  assert.throws(
    () => axialVoxelKForPatientPlane(frame, oblique),
    /orientation/,
  );
  const rotated = createPatientImagingPlane({
    origin: at(4).origin,
    directionI: patientSpaceDirection(0, 1, 0),
    directionJ: patientSpaceDirection(-1, 0, 0),
  });
  assert.throws(
    () => axialVoxelKForPatientPlane(frame, rotated),
    /orientation/,
  );
  assert.throws(() =>
    axialVoxelKForPatientPlane(frame, {
      ...at(4),
      normal: patientSpaceDirection(0, 0, -1),
    }),
  );
  assert.throws(() =>
    axialVoxelKForPatientPlane(frame, {
      ...at(4),
      origin: { space: 'render', kind: 'point', value: { x: 0, y: 0, z: 0 } },
    }),
  );
  const shiftedInPlane = { ...at(6), origin: patientSpacePoint(50, -70, 4) };
  assert.equal(axialVoxelKForPatientPlane(frame, shiftedInPlane), 6);
});

test('TASK-061 descending k and anisotropic spacing retain source geometry', () => {
  const descending = {
    ...frame,
    origin: patientSpacePoint(12, -21, 100),
    directionK: patientSpaceDirection(0, 0, -1),
    handedness: 'left',
    spacing: { i: millimetres(0.6), j: millimetres(1.3), k: millimetres(2.5) },
  };
  const transform = new ImagePatientTransform(descending);
  for (let k = 0; k < 9; k++) {
    const plane = transform.planeAtK(k);
    assert.equal(plane.origin.value.z, 100 - k * 2.5);
    assert.equal(plane.normal.value.z, 1);
    assert.equal(axialVoxelKForPatientPlane(descending, plane), k);
  }
});

test('TASK-063 arbitrary oblique plane becomes the shared Patient Space plane without fabricating source-k state', async () => {
  const { sync, calls, rendered } = harness();
  const oblique = createPatientImagingPlane({
    origin: patientSpacePoint(0.5, -1.25, 2.75),
    directionI: patientSpaceDirection(Math.SQRT1_2, 0, Math.SQRT1_2),
    directionJ: patientSpaceDirection(0, 1, 0),
  });

  await sync.setPatientPlane(oblique);

  assert.equal(sync.state.slice, null);
  assert.deepEqual(sync.state.plane, oblique);
  assert.deepEqual(rendered.at(-1), oblique);
  assert.equal(calls.at(-1)[0], 'oblique');

  await assert.rejects(sync.scrollImage(1), /oblique/);
  assert.deepEqual(sync.state.plane, oblique);
  assert.deepEqual(rendered.at(-1), oblique);

  await sync.setPlaneAtVoxelK(4);
  assert.equal(sync.state.slice.voxelK, 4);
  assert.deepEqual(sync.state.plane, sync.state.slice.plane);
});

test('mixed rapid commands execute in input order with at most one camera mutation in flight', async () => {
  let release;
  let active = 0;
  const { sync, calls } = harness(async () => {
    assert.equal(++active, 1);
    await new Promise((resolve) => {
      release = resolve;
    });
    active--;
  });
  const first = sync.setImageSlice(1);
  const second = sync.setPlaneAtVoxelK(2);
  const third = sync.scrollImage(1);
  await Promise.resolve();
  assert.deepEqual(calls, [['image', 1]]);
  release();
  await first;
  await Promise.resolve();
  assert.deepEqual(calls, [
    ['image', 1],
    ['plane', 2],
  ]);
  release();
  await second;
  await Promise.resolve();
  assert.deepEqual(calls.at(-1), ['image', 7]);
  release();
  await third;
  assert.equal(sync.state.slice.voxelK, 1);
});

test('failed readback clears stale clipping, reports error and permits recovery', async () => {
  let fail = true;
  const { sync, rendered } = harness(async () => {
    if (fail) throw new Error('readback failed');
  });
  await assert.rejects(sync.setImageSlice(1), /readback failed/);
  assert.equal(sync.state.slice, null);
  assert.equal(sync.state.error, 'readback failed');
  assert.equal(rendered.at(-1), null);
  fail = false;
  await sync.setPlaneAtVoxelK(8);
  assert.equal(sync.state.slice.voxelK, 8);
  assert.equal(sync.state.error, null);
});

test('clipping toggle preserves shared plane and scroll boundaries never wrap', async () => {
  const { sync, rendered } = harness();
  sync.setClippingEnabled(false);
  await sync.setImageSlice(8);
  await sync.scrollImage(1);
  assert.equal(rendered.at(-1), null);
  assert.equal(sync.state.slice.displayIndex, 8);
  sync.setClippingEnabled(true);
  assert.equal(rendered.at(-1).origin.value.z, -8);
  await sync.setImageSlice(0);
  await sync.scrollImage(-1);
  assert.equal(sync.state.slice.displayIndex, 0);
});

test('dispose invalidates in-flight completion and queued commands without touching a disposed renderer', async () => {
  let release;
  const { sync, calls, rendered, changes } = harness(
    () =>
      new Promise((resolve) => {
        release = resolve;
      }),
  );
  const first = sync.setImageSlice(1);
  const second = sync.setPlaneAtVoxelK(7);
  const rejected = [
    assert.rejects(first, /disposed/),
    assert.rejects(second, /disposed/),
  ];
  await Promise.resolve();
  sync.dispose();
  sync.dispose();
  const count = rendered.length;
  release();
  await Promise.all(rejected);
  assert.equal(rendered.length, count);
  assert.equal(rendered.at(-1), null);
  assert.equal(changes.length, 1);
  assert.deepEqual(calls, [['image', 1]]);
});
