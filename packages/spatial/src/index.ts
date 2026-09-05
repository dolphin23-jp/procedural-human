import type { PatientSpacePoint } from '@procedural-human/math';
import type { Length } from '@procedural-human/units';

export interface PatientSpaceSegment {
  readonly start: PatientSpacePoint;
  readonly end: PatientSpacePoint;
}

export const patientSpaceSegment = (
  start: PatientSpacePoint,
  end: PatientSpacePoint,
): PatientSpaceSegment => Object.freeze({ start, end });

/**
 * Geometry capability implemented by a patient-space representation adapter.
 *
 * This contract deliberately does not assign anatomical, lumen, boundary,
 * entry/exit, ordering, or procedure meaning to the returned geometry. Those
 * semantics belong to later Spatial Query tasks.
 */
export interface SpatialRepresentationAdapter {
  containsPoint(point: PatientSpacePoint): boolean;
  intersectSegment(segment: PatientSpaceSegment): readonly PatientSpacePoint[];
  distanceToPoint(point: PatientSpacePoint): Length;
}
