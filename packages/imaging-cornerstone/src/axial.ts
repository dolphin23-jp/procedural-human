import {
  ImagePatientTransform,
  createPatientImagingPlane,
  type AxialSliceState,
  createVolumeImagingFrame,
  type PatientImagingPlane,
  type VolumeImagingFrame,
} from '@procedural-human/imaging-core';
import type { PatientSpacePoint } from '@procedural-human/math';

export const PATIENT_AXIAL_TOLERANCE = 1e-9;
export const AXIAL_SAMPLE_PLANE_TOLERANCE = 1e-4;

export type { AxialSliceState } from '@procedural-human/imaging-core';

function displayIndex(value: number, count: number): number {
  if (!Number.isSafeInteger(value) || value < 0 || value >= count) {
    throw new RangeError('Axial display index is outside the volume.');
  }
  return value;
}

/**
 * TASK-059 is deliberately limited to patient-axial source planes.
 * Oblique MPR belongs to TASK-063 and must not be silently approximated here.
 */
export function assertPatientAxialFrame(
  frame: VolumeImagingFrame,
): VolumeImagingFrame {
  const checked = createVolumeImagingFrame(frame);
  const i = checked.directionI.value;
  const j = checked.directionJ.value;
  const k = checked.directionK.value;
  if (
    Math.abs(i.z) > PATIENT_AXIAL_TOLERANCE ||
    Math.abs(j.z) > PATIENT_AXIAL_TOLERANCE ||
    Math.abs(Math.abs(k.z) - 1) > PATIENT_AXIAL_TOLERANCE
  ) {
    throw new RangeError(
      'TASK-059 axial viewer requires source planes parallel to patient axial planes.',
    );
  }
  return checked;
}

/**
 * Converts the actual displayed Cornerstone focal plane back through the
 * ImagePatientTransform. No assumption is made that Cornerstone display order
 * equals source k order.
 */
export function createAxialSliceStateFromPatientPoint(
  frame: VolumeImagingFrame,
  currentDisplayIndex: number,
  pointOnDisplayedPlane: PatientSpacePoint,
): AxialSliceState {
  const axialFrame = assertPatientAxialFrame(frame);
  const index = displayIndex(currentDisplayIndex, axialFrame.dimensions.k);
  const transform = new ImagePatientTransform(axialFrame);
  const voxel = transform.patientToVoxel(pointOnDisplayedPlane);
  // Descending source axes can produce -0; indices have a canonical zero.
  const nearestK = Math.round(voxel.k) || 0;

  if (
    Math.abs(voxel.k - nearestK) > AXIAL_SAMPLE_PLANE_TOLERANCE ||
    nearestK < 0 ||
    nearestK >= axialFrame.dimensions.k
  ) {
    throw new RangeError(
      'Displayed plane does not coincide with a declared axial source sample plane.',
    );
  }

  return Object.freeze({
    displayIndex: index,
    voxelK: nearestK,
    plane: transform.planeAtK(nearestK),
  });
}

/** Pure helper for tests and callers that already know a source voxel-k plane. */
export function createAxialSliceStateAtVoxelK(
  frame: VolumeImagingFrame,
  currentDisplayIndex: number,
  voxelK: number,
): AxialSliceState {
  const axialFrame = assertPatientAxialFrame(frame);
  const index = displayIndex(currentDisplayIndex, axialFrame.dimensions.k);
  if (
    !Number.isSafeInteger(voxelK) ||
    voxelK < 0 ||
    voxelK >= axialFrame.dimensions.k
  ) {
    throw new RangeError('Voxel k is outside the axial source volume.');
  }
  const transform = new ImagePatientTransform(axialFrame);
  return Object.freeze({
    displayIndex: index,
    voxelK,
    plane: transform.planeAtK(voxelK),
  });
}

/** Reject unsupported orientation and off-lattice positions before moving a camera. */
export function axialVoxelKForPatientPlane(
  frame: VolumeImagingFrame,
  plane: PatientImagingPlane,
): number {
  if (!plane || plane.kind !== 'patient-imaging-plane') {
    throw new TypeError('Expected patient imaging plane.');
  }
  const checked = createPatientImagingPlane(plane);
  const axialFrame = assertPatientAxialFrame(frame);
  const expected = new ImagePatientTransform(axialFrame).planeAtK(0);
  for (const key of ['directionI', 'directionJ', 'normal'] as const) {
    for (const axis of ['x', 'y', 'z'] as const) {
      const value = plane[key]?.value?.[axis];
      if (
        !Number.isFinite(value) ||
        Math.abs(value - expected[key].value[axis]) > PATIENT_AXIAL_TOLERANCE
      ) {
        throw new RangeError(
          'Axial synchronization cannot change plane orientation; oblique MPR belongs to TASK-063.',
        );
      }
    }
  }
  return createAxialSliceStateFromPatientPoint(axialFrame, 0, checked.origin)
    .voxelK;
}
