import assert from 'node:assert/strict';
import test from 'node:test';
import { ImagePatientTransform } from '../packages/imaging-core/dist/index.js';
import { imageVoxelCoordinate } from '../packages/math/dist/index.js';
import {
  assertPatientAxialFrame,
  createAxialSliceStateAtVoxelK,
  createAxialSliceStateFromPatientPoint,
} from '../packages/imaging-cornerstone/dist/axial.js';
import { createSyntheticAxialVolumeFixture } from '../packages/imaging-cornerstone/dist/fixture.js';

test('TASK-058 fixture is deterministic, bounded, and explicitly non-medical', () => {
  const first = createSyntheticAxialVolumeFixture();
  const second = createSyntheticAxialVolumeFixture();

  assert.equal(first.provenance.sourceClass, 'development-fixture');
  assert.equal(first.provenance.validationLevel, 'V0');
  assert.equal(first.frame.dimensions.i, 48);
  assert.equal(first.frame.dimensions.j, 48);
  assert.equal(first.frame.dimensions.k, 9);
  assert.equal(first.scalarData.length, 48 * 48 * 9);
  assert.deepEqual(first.scalarData, second.scalarData);
  assert.doesNotThrow(() => assertPatientAxialFrame(first.frame));
});

test('TASK-059 voxel-k slice has an explicit Patient Space plane', () => {
  const source = createSyntheticAxialVolumeFixture();
  const state = createAxialSliceStateAtVoxelK(source.frame, 4, 4);

  assert.equal(state.displayIndex, 4);
  assert.equal(state.voxelK, 4);
  assert.equal(state.plane.kind, 'patient-imaging-plane');
  assert.equal(state.plane.origin.space, 'patient');
  assert.equal(state.plane.origin.value.x, -18.8);
  assert.equal(state.plane.origin.value.y, -18.8);
  assert.equal(state.plane.origin.value.z, 0);
  assert.deepEqual(state.plane.normal.value, { x: 0, y: 0, z: 1 });
});

test('TASK-059 derives source k through Patient Space instead of equating display index with k', () => {
  const source = createSyntheticAxialVolumeFixture();
  const transform = new ImagePatientTransform(source.frame);
  const point = transform.voxelToPatient(imageVoxelCoordinate(17.25, 8.5, 7));

  const state = createAxialSliceStateFromPatientPoint(source.frame, 1, point);

  assert.equal(state.displayIndex, 1);
  assert.equal(state.voxelK, 7);
  assert.equal(state.plane.origin.value.z, 6);

  const betweenSlices = transform.voxelToPatient(
    imageVoxelCoordinate(17.25, 8.5, 7.25),
  );
  assert.throws(
    () => createAxialSliceStateFromPatientPoint(source.frame, 1, betweenSlices),
    /does not coincide/,
  );
});
