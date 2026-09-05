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

export interface PatientSpaceVector {
  readonly space: 'patient';
  readonly kind: 'vector';
  readonly value: Vec3;
}

export interface RenderSpacePoint {
  readonly space: 'render';
  readonly kind: 'point';
  readonly value: Vec3;
}

export interface ImageVoxelCoordinate {
  readonly space: 'image-voxel';
  readonly i: number;
  readonly j: number;
  readonly k: number;
}

export const vec3 = (x: number, y: number, z: number): Vec3 => ({ x, y, z });

export const patientSpacePoint = (x: number, y: number, z: number): PatientSpacePoint => ({
  space: 'patient',
  kind: 'point',
  value: vec3(x, y, z),
});

export const patientSpaceVector = (x: number, y: number, z: number): PatientSpaceVector => ({
  space: 'patient',
  kind: 'vector',
  value: vec3(x, y, z),
});

export const renderSpacePoint = (x: number, y: number, z: number): RenderSpacePoint => ({
  space: 'render',
  kind: 'point',
  value: vec3(x, y, z),
});

export const imageVoxelCoordinate = (i: number, j: number, k: number): ImageVoxelCoordinate => ({
  space: 'image-voxel',
  i,
  j,
  k,
});
