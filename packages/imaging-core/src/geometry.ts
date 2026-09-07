import type {
  PatientSpaceDirection,
  PatientSpacePoint,
  Vec3,
} from '@procedural-human/math';
import { toMillimetres, type Length } from '@procedural-human/units';
import type {
  ImagingFrame,
  ImagingObservation,
  PatientImagingPlane,
  PlanarImagingFrame,
  VolumeImagingFrame,
} from './contracts.js';

/** Dimensionless metadata tolerance, not a medical registration accuracy. */
export const IMAGE_BASIS_TOLERANCE = 1e-9;
/** Absolute patient-mm residual accepted by the inverse of a 2D plane. */
export const IMAGE_PLANE_TOLERANCE_MM = 1e-9;

export function finite(values: readonly number[]): void {
  if (!values.every(Number.isFinite))
    throw new RangeError('Imaging coordinates must be finite.');
}
export const dot = (a: Vec3, b: Vec3): number =>
  a.x * b.x + a.y * b.y + a.z * b.z;
export const cross = (a: Vec3, b: Vec3): Vec3 => ({
  x: a.y * b.z - a.z * b.y,
  y: a.z * b.x - a.x * b.z,
  z: a.x * b.y - a.y * b.x,
});

export function checkedPoint(point: PatientSpacePoint): PatientSpacePoint {
  if (
    !point ||
    point.space !== 'patient' ||
    point.kind !== 'point' ||
    !point.value
  )
    throw new TypeError('Expected patient-space point.');
  finite([point.value.x, point.value.y, point.value.z]);
  return Object.freeze({
    space: 'patient',
    kind: 'point',
    value: Object.freeze({ ...point.value }),
  });
}
function checkedDirection(
  direction: PatientSpaceDirection,
): PatientSpaceDirection {
  if (
    !direction ||
    direction.space !== 'patient' ||
    direction.kind !== 'direction' ||
    !direction.value
  )
    throw new TypeError('Expected patient-space direction.');
  const { x, y, z } = direction.value;
  finite([x, y, z]);
  if (Math.abs(Math.hypot(x, y, z) - 1) > IMAGE_BASIS_TOLERANCE)
    throw new RangeError('Imaging basis must contain unit directions.');
  // Preserve accepted metadata exactly: no silent normalization/orthogonalization.
  return Object.freeze({
    space: 'patient',
    kind: 'direction',
    value: Object.freeze({ x, y, z }),
  });
}
function orthogonal(a: PatientSpaceDirection, b: PatientSpaceDirection): void {
  if (Math.abs(dot(a.value, b.value)) > IMAGE_BASIS_TOLERANCE)
    throw new RangeError('Imaging basis must be orthogonal and nonsingular.');
}
function spacing(value: Length): Length {
  const mm = toMillimetres(value);
  if (!Number.isFinite(mm) || mm <= 0 || !Number.isFinite(1 / mm))
    throw new RangeError(
      'Imaging spacing must be positive, finite and invertible.',
    );
  return value;
}
function dimension(value: number): number {
  if (!Number.isSafeInteger(value) || value <= 0)
    throw new RangeError('Imaging dimensions must be positive safe integers.');
  return value;
}
function base(frame: ImagingFrame) {
  if (!frame || frame.indexConvention !== 'zero-based-sample-centers')
    throw new TypeError(
      'Explicit zero-based-sample-centers convention is required.',
    );
  const origin = checkedPoint(frame.origin);
  const directionI = checkedDirection(frame.directionI);
  const directionJ = checkedDirection(frame.directionJ);
  orthogonal(directionI, directionJ);
  if (!frame.spacing || !frame.dimensions)
    throw new TypeError(
      'Explicit imaging spacing and dimensions are required.',
    );
  return {
    indexConvention: frame.indexConvention,
    origin,
    directionI,
    directionJ,
  };
}
export function createPlanarImagingFrame(
  frame: PlanarImagingFrame,
): PlanarImagingFrame {
  if (!frame || frame.kind !== 'plane-2d')
    throw new TypeError('Expected plane-2d imaging frame.');
  return Object.freeze({
    ...base(frame),
    kind: 'plane-2d',
    spacing: Object.freeze({
      i: spacing(frame.spacing.i),
      j: spacing(frame.spacing.j),
    }),
    dimensions: Object.freeze({
      i: dimension(frame.dimensions.i),
      j: dimension(frame.dimensions.j),
    }),
  });
}
export function createVolumeImagingFrame(
  frame: VolumeImagingFrame,
): VolumeImagingFrame {
  if (!frame || frame.kind !== 'volume-3d')
    throw new TypeError('Expected volume-3d imaging frame.');
  const common = base(frame);
  const directionK = checkedDirection(frame.directionK);
  orthogonal(common.directionI, directionK);
  orthogonal(common.directionJ, directionK);
  const determinant = dot(
    common.directionI.value,
    cross(common.directionJ.value, directionK.value),
  );
  if (Math.abs(determinant) < 1 - 4 * IMAGE_BASIS_TOLERANCE)
    throw new RangeError('Imaging basis is singular or invalid.');
  if (frame.handedness !== (determinant > 0 ? 'right' : 'left'))
    throw new RangeError('Imaging handedness does not match the basis.');
  return Object.freeze({
    ...common,
    kind: 'volume-3d',
    directionK,
    handedness: frame.handedness,
    spacing: Object.freeze({
      i: spacing(frame.spacing.i),
      j: spacing(frame.spacing.j),
      k: spacing(frame.spacing.k),
    }),
    dimensions: Object.freeze({
      i: dimension(frame.dimensions.i),
      j: dimension(frame.dimensions.j),
      k: dimension(frame.dimensions.k),
    }),
  });
}
export function createPatientImagingPlane(
  geometry: Pick<PatientImagingPlane, 'origin' | 'directionI' | 'directionJ'>,
): PatientImagingPlane {
  if (!geometry)
    throw new TypeError('Explicit imaging plane geometry is required.');
  const origin = checkedPoint(geometry.origin);
  const directionI = checkedDirection(geometry.directionI);
  const directionJ = checkedDirection(geometry.directionJ);
  orthogonal(directionI, directionJ);
  const n = cross(directionI.value, directionJ.value);
  const norm = Math.hypot(n.x, n.y, n.z);
  const normal: PatientSpaceDirection = Object.freeze({
    space: 'patient',
    kind: 'direction',
    value: Object.freeze({ x: n.x / norm, y: n.y / norm, z: n.z / norm }),
  });
  return Object.freeze({
    kind: 'patient-imaging-plane',
    origin,
    directionI,
    directionJ,
    normal,
  });
}
function nonempty(value: string): void {
  if (typeof value !== 'string' || !value.trim())
    throw new TypeError(
      'Imaging reference identifiers must be nonempty strings.',
    );
}
export function createImagingObservation(
  observation: ImagingObservation,
): ImagingObservation {
  if (!observation) throw new TypeError('Imaging observation is required.');
  nonempty(observation.id);
  nonempty(observation.patientId);
  nonempty(observation.assetId);
  if (!['acquired', 'synthetic', 'hybrid'].includes(observation.sourceType))
    throw new TypeError('Invalid imaging source type.');
  if (observation.registrationId !== null) nonempty(observation.registrationId);
  if (observation.registrationStatus === 'registered') {
    if (!Array.isArray(observation.frames) || observation.frames.length === 0)
      throw new TypeError('Registered observation requires explicit frames.');
    const frames = Array.from(observation.frames, (frame: ImagingFrame) => {
      if (frame?.kind === 'plane-2d') return createPlanarImagingFrame(frame);
      return createVolumeImagingFrame(frame);
    });
    return Object.freeze({ ...observation, frames: Object.freeze(frames) });
  }
  if (
    !['unknown', 'unregistered'].includes(observation.registrationStatus) ||
    observation.frames !== null
  )
    throw new TypeError('Unavailable registration requires null frames.');
  return Object.freeze({ ...observation });
}
