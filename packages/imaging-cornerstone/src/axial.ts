import {
  ImagePatientTransform,
  createVolumeImagingFrame,
  type PatientImagingPlane,
  type VolumeImagingFrame,
} from '@procedural-human/imaging-core';
import type { PatientSpacePoint } from '@procedural-human/math';

export const PATIENT_AXIAL_TOLERANCE = 1e-9;
export const AXIAL_SAMPLE_PLANE_TOLERANCE = 1e-4;

export interface AxialSliceState {
  /** Cornerstone viewport ordering; this is not assumed to equal voxel k. */
  readonly displayIndex: number;
  /** Source-volume sample plane recovered through Patient Space. */
  readonly voxelK: number;
  readonly plane: PatientImagingPlane;
}

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
  const nearestK = Math.round(voxel.k);

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
