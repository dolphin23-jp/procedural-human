/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local Three declarations */
/// <reference path="./three.d.ts" />
import type { PatientClippingPlane } from '@procedural-human/rendering-core';
import { PatientRenderTransform } from '@procedural-human/rendering-core';
import { Plane } from 'three';
import {
  renderDirectionToThree,
  renderPointToThree,
} from './three-coordinates.js';

/**
 * Convert the renderer-neutral Patient Space clipping contract to the
 * Three.js world-space plane used by WebGLRenderer.clippingPlanes.
 *
 * Three clips points with negative signed distance, matching the core contract
 * that keeps dot(normal, point - origin) >= 0.
 */
export function patientClippingPlaneToThree(
  plane: PatientClippingPlane,
  coordinates: PatientRenderTransform,
): Plane {
  if (!plane) throw new TypeError('Patient clipping plane is required.');
  if (!(coordinates instanceof PatientRenderTransform)) {
    throw new TypeError('Explicit PatientRenderTransform is required.');
  }

  const origin = renderPointToThree(
    coordinates.patientPointToRender(plane.origin),
  );
  const normal = renderDirectionToThree(
    coordinates.patientDirectionToRender(plane.normal),
  );

  return new Plane().setFromNormalAndCoplanarPoint(normal, origin);
}
