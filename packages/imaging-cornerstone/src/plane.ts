import {
  IMAGE_BASIS_TOLERANCE,
  createPatientImagingPlane,
  type PatientImagingPlane,
} from '@procedural-human/imaging-core';
import {
  patientSpaceDirection,
  patientSpacePoint,
} from '@procedural-human/math';

export const MPR_DIRECTION_TOLERANCE = 1e-6;
export const MPR_POSITION_TOLERANCE_MM = 1e-4;

export interface CornerstoneCameraPlane {
  readonly viewPlaneNormal: [number, number, number];
  readonly viewUp: [number, number, number];
}

export interface CornerstoneCameraPose extends CornerstoneCameraPlane {
  readonly focalPoint: [number, number, number];
  readonly position: [number, number, number];
}

type Point3 = readonly [number, number, number];

function finitePoint3(value: Point3, name: string): void {
  if (!value || value.length !== 3 || !value.every(Number.isFinite)) {
    throw new TypeError(`${name} must contain three finite values.`);
  }
}

function checkedPatientPlane(plane: PatientImagingPlane): PatientImagingPlane {
  const checked = createPatientImagingPlane(plane);
  if (
    plane?.kind !== 'patient-imaging-plane' ||
    !plane.normal ||
    ['x', 'y', 'z'].some((axis) => {
      const key = axis as 'x' | 'y' | 'z';
      return (
        !Number.isFinite(plane.normal.value[key]) ||
        Math.abs(plane.normal.value[key] - checked.normal.value[key]) >
          IMAGE_BASIS_TOLERANCE
      );
    })
  ) {
    throw new TypeError('Patient imaging plane normal must match its basis.');
  }
  return checked;
}

function canonicalZero(value: number): number {
  return Object.is(value, -0) ? 0 : value;
}

function dot(a: Point3, b: Point3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function cross(a: Point3, b: Point3): [number, number, number] {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function normalize(value: Point3, name: string): [number, number, number] {
  finitePoint3(value, name);
  const magnitude = Math.hypot(value[0], value[1], value[2]);
  if (!Number.isFinite(magnitude) || magnitude <= Number.EPSILON) {
    throw new RangeError(`${name} must be non-zero.`);
  }
  return [value[0] / magnitude, value[1] / magnitude, value[2] / magnitude];
}

/**
 * PatientImagingPlane directionJ follows increasing image rows. Cornerstone's
 * viewUp points from screen bottom to top, so it is the negative row direction.
 * viewPlaneNormal is kept identical to the project's derived plane normal.
 */
export function patientPlaneToCornerstoneCamera(
  plane: PatientImagingPlane,
): CornerstoneCameraPlane {
  const checked = checkedPatientPlane(plane);
  const normal = checked.normal.value;
  const j = checked.directionJ.value;
  const viewPlaneNormal: [number, number, number] = [
    canonicalZero(normal.x),
    canonicalZero(normal.y),
    canonicalZero(normal.z),
  ];
  const viewUp: [number, number, number] = [
    canonicalZero(-j.x),
    canonicalZero(-j.y),
    canonicalZero(-j.z),
  ];
  return Object.freeze({ viewPlaneNormal, viewUp });
}

/**
 * Camera-only navigation helper for source-plane movement. The focal point is
 * translated only along the target plane normal, preserving its in-plane pan.
 * Camera distance is preserved while orientation is aligned to the target.
 */
export function cornerstoneCameraForParallelPatientPlane(
  focalPoint: Point3,
  position: Point3,
  plane: PatientImagingPlane,
): CornerstoneCameraPose {
  finitePoint3(focalPoint, 'Cornerstone focal point');
  finitePoint3(position, 'Cornerstone camera position');
  const target = patientPlaneToCornerstoneCamera(plane);
  const normal = target.viewPlaneNormal;
  const origin = checkedPatientPlane(plane).origin.value;
  const signedDistance =
    (origin.x - focalPoint[0]) * normal[0] +
    (origin.y - focalPoint[1]) * normal[1] +
    (origin.z - focalPoint[2]) * normal[2];
  const translatedFocalPoint: [number, number, number] = [
    canonicalZero(focalPoint[0] + normal[0] * signedDistance),
    canonicalZero(focalPoint[1] + normal[1] * signedDistance),
    canonicalZero(focalPoint[2] + normal[2] * signedDistance),
  ];
  const cameraDistance = Math.hypot(
    position[0] - focalPoint[0],
    position[1] - focalPoint[1],
    position[2] - focalPoint[2],
  );
  if (!Number.isFinite(cameraDistance) || cameraDistance <= Number.EPSILON) {
    throw new RangeError('Cornerstone viewport camera distance is invalid.');
  }
  const translatedPosition: [number, number, number] = [
    canonicalZero(translatedFocalPoint[0] + normal[0] * cameraDistance),
    canonicalZero(translatedFocalPoint[1] + normal[1] * cameraDistance),
    canonicalZero(translatedFocalPoint[2] + normal[2] * cameraDistance),
  ];
  return Object.freeze({
    ...target,
    focalPoint: translatedFocalPoint,
    position: translatedPosition,
  });
}

/**
 * Convert Cornerstone camera readback to the project-owned Patient Space plane.
 * Small camera basis residuals are orthogonalized before project validation.
 */
export function patientPlaneFromCornerstoneCamera(
  focalPoint: Point3,
  viewPlaneNormal: Point3,
  viewUp: Point3,
): PatientImagingPlane {
  finitePoint3(focalPoint, 'Cornerstone focal point');
  const normal = normalize(viewPlaneNormal, 'Cornerstone view-plane normal');
  const up = normalize(viewUp, 'Cornerstone view-up');
  const rowRaw: [number, number, number] = [-up[0], -up[1], -up[2]];
  const rowNormalComponent = dot(rowRaw, normal);
  const row = normalize(
    [
      rowRaw[0] - normal[0] * rowNormalComponent,
      rowRaw[1] - normal[1] * rowNormalComponent,
      rowRaw[2] - normal[2] * rowNormalComponent,
    ],
    'Cornerstone in-plane row direction',
  );
  const column = normalize(
    cross(row, normal),
    'Cornerstone in-plane column direction',
  );

  return createPatientImagingPlane({
    origin: patientSpacePoint(focalPoint[0], focalPoint[1], focalPoint[2]),
    directionI: patientSpaceDirection(column[0], column[1], column[2]),
    directionJ: patientSpaceDirection(row[0], row[1], row[2]),
  });
}

export function assertPatientPlaneOrientationEquivalent(
  expected: PatientImagingPlane,
  actual: PatientImagingPlane,
): void {
  const a = checkedPatientPlane(expected);
  const b = checkedPatientPlane(actual);
  for (const key of ['directionI', 'directionJ', 'normal'] as const) {
    for (const axis of ['x', 'y', 'z'] as const) {
      if (
        Math.abs(a[key].value[axis] - b[key].value[axis]) >
        MPR_DIRECTION_TOLERANCE
      ) {
        throw new Error(
          'Cornerstone camera orientation does not match the requested Patient Space plane.',
        );
      }
    }
  }
}

export function assertPatientPlanesEquivalent(
  expected: PatientImagingPlane,
  actual: PatientImagingPlane,
): void {
  const a = checkedPatientPlane(expected);
  const b = checkedPatientPlane(actual);
  assertPatientPlaneOrientationEquivalent(a, b);
  const distance = Math.hypot(
    a.origin.value.x - b.origin.value.x,
    a.origin.value.y - b.origin.value.y,
    a.origin.value.z - b.origin.value.z,
  );
  if (distance > MPR_POSITION_TOLERANCE_MM) {
    throw new Error(
      'Cornerstone camera position does not match the requested Patient Space plane.',
    );
  }
}
