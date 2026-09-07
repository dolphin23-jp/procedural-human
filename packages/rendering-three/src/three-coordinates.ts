/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local Three declarations */
/// <reference path="./three.d.ts" />

import { Matrix4, Vector3 } from 'three';
import {
  patientSpacePoint,
  patientSpaceVector,
  renderSpacePoint,
  renderSpaceVector,
  type RenderSpacePoint,
  type RenderSpaceVector,
} from '@procedural-human/math';
import type { PatientRenderTransform } from '@procedural-human/rendering-core';

function finite(x: number, y: number, z: number): void {
  if (![x, y, z].every(Number.isFinite))
    throw new RangeError('Three coordinates must be finite.');
}

// Three values here are world coordinates, never mesh-local coordinates.
export function renderPointToThree(point: RenderSpacePoint): Vector3 {
  if (!point || point.space !== 'render' || point.kind !== 'point')
    throw new TypeError('Expected render-space point.');
  finite(point.value.x, point.value.y, point.value.z);
  return new Vector3(point.value.x, point.value.y, point.value.z);
}

export function threePointToRender(point: Vector3): RenderSpacePoint {
  finite(point.x, point.y, point.z);
  return renderSpacePoint(point.x, point.y, point.z);
}

export function renderVectorToThree(vector: RenderSpaceVector): Vector3 {
  if (!vector || vector.space !== 'render' || vector.kind !== 'vector')
    throw new TypeError('Expected render-space vector.');
  finite(vector.value.x, vector.value.y, vector.value.z);
  return new Vector3(vector.value.x, vector.value.y, vector.value.z);
}

export function threeVectorToRender(vector: Vector3): RenderSpaceVector {
  finite(vector.x, vector.y, vector.z);
  return renderSpaceVector(vector.x, vector.y, vector.z);
}

/** Column basis built from the same neutral transform used by point queries. */
export function patientToThreeMatrix(
  coordinates: PatientRenderTransform,
): Matrix4 {
  const x = coordinates.patientVectorToRender(
    patientSpaceVector(1, 0, 0),
  ).value;
  const y = coordinates.patientVectorToRender(
    patientSpaceVector(0, 1, 0),
  ).value;
  const z = coordinates.patientVectorToRender(
    patientSpaceVector(0, 0, 1),
  ).value;
  const t = coordinates.patientPointToRender(patientSpacePoint(0, 0, 0)).value;
  // Matrix4.set takes row-major arguments; its internal elements are column-major.
  return new Matrix4().set(
    x.x,
    y.x,
    z.x,
    t.x,
    x.y,
    y.y,
    z.y,
    t.y,
    x.z,
    y.z,
    z.z,
    t.z,
    0,
    0,
    0,
    1,
  );
}
