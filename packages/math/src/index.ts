export interface Vec3 {
  readonly x: number;
  readonly y: number;
  readonly z: number;
}

export interface Quaternion {
  readonly x: number;
  readonly y: number;
  readonly z: number;
  readonly w: number;
}

export type Mat4 = readonly [
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
];

export interface Transform {
  readonly translation: Vec3;
  readonly rotation: Quaternion;
  readonly scale: Vec3;
}

export interface Plane {
  readonly normal: Vec3;
  readonly constant: number;
}

export interface Ray {
  readonly origin: Vec3;
  readonly direction: Vec3;
}

export interface Segment {
  readonly start: Vec3;
  readonly end: Vec3;
}

export interface BoundingBox {
  readonly min: Vec3;
  readonly max: Vec3;
}

export interface PatientSpacePoint {
  readonly space: 'patient';
  readonly kind: 'point';
  readonly value: Vec3;
}

/** Physical displacement in Patient Space millimetres. */
export interface PatientSpaceVector {
  readonly space: 'patient';
  readonly kind: 'vector';
  readonly value: Vec3;
}

/** Dimensionless finite unit direction in Patient Space. */
export interface PatientSpaceDirection {
  readonly space: 'patient';
  readonly kind: 'direction';
  readonly value: Vec3;
}

export interface RenderSpacePoint {
  readonly space: 'render';
  readonly kind: 'point';
  readonly value: Vec3;
}

/** Displacement in the explicitly configured render units, not a direction. */
export interface RenderSpaceVector {
  readonly space: 'render';
  readonly kind: 'vector';
  readonly value: Vec3;
}

/** Dimensionless finite unit direction in Render Space. */
export interface RenderSpaceDirection {
  readonly space: 'render';
  readonly kind: 'direction';
  readonly value: Vec3;
}

export interface ImageVoxelCoordinate {
  readonly space: 'image-voxel';
  readonly i: number;
  readonly j: number;
  readonly k: number;
}

export const vec3 = (x: number, y: number, z: number): Vec3 => ({ x, y, z });

function unitDirection(
  x: number,
  y: number,
  z: number,
  label: string,
): Vec3 {
  if (![x, y, z].every(Number.isFinite)) {
    throw new RangeError(`${label} components must be finite.`);
  }
  const norm = Math.hypot(x, y, z);
  if (!Number.isFinite(norm) || Math.abs(norm - 1) > 1e-9) {
    throw new RangeError(`${label} must be a unit direction.`);
  }
  return vec3(x / norm, y / norm, z / norm);
}

export const patientSpacePoint = (
  x: number,
  y: number,
  z: number,
): PatientSpacePoint => ({
  space: 'patient',
  kind: 'point',
  value: vec3(x, y, z),
});

export const patientSpaceVector = (
  x: number,
  y: number,
  z: number,
): PatientSpaceVector => ({
  space: 'patient',
  kind: 'vector',
  value: vec3(x, y, z),
});

export const patientSpaceDirection = (
  x: number,
  y: number,
  z: number,
): PatientSpaceDirection => ({
  space: 'patient',
  kind: 'direction',
  value: unitDirection(x, y, z, 'Patient-space direction'),
});

export const renderSpacePoint = (
  x: number,
  y: number,
  z: number,
): RenderSpacePoint => ({
  space: 'render',
  kind: 'point',
  value: vec3(x, y, z),
});

export const renderSpaceVector = (
  x: number,
  y: number,
  z: number,
): RenderSpaceVector => ({
  space: 'render',
  kind: 'vector',
  value: vec3(x, y, z),
});

export const renderSpaceDirection = (
  x: number,
  y: number,
  z: number,
): RenderSpaceDirection => ({
  space: 'render',
  kind: 'direction',
  value: unitDirection(x, y, z, 'Render-space direction'),
});

export const imageVoxelCoordinate = (
  i: number,
  j: number,
  k: number,
): ImageVoxelCoordinate => ({
  space: 'image-voxel',
  i,
  j,
  k,
});
