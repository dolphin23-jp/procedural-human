/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local Three declarations */
/// <reference path="./three.d.ts" />
import { patientSpacePoint, patientSpaceVector } from '@procedural-human/math';
import type { PatientRenderTransform } from '@procedural-human/rendering-core';
import { toMillimetres } from '@procedural-human/units';
import { PerspectiveCamera } from 'three';
import {
  renderPointToThree,
  renderVectorToThree,
} from './three-coordinates.js';

/** Same physical viewpoint as TASK-046, expressed through the configured frame. */
export function createFixtureCamera(
  coordinates: PatientRenderTransform,
): PerspectiveCamera {
  const mmPerUnit = toMillimetres(coordinates.config.millimetresPerRenderUnit);
  const near = 0.1 / mmPerUnit;
  const far = 500 / mmPerUnit;
  if (!Number.isFinite(far) || near <= 0 || near >= far) {
    throw new RangeError(
      'Coordinate scale cannot represent the fixture camera clipping range.',
    );
  }
  const camera = new PerspectiveCamera(34, 1, near, far);
  camera.position.copy(
    renderPointToThree(
      coordinates.patientPointToRender(patientSpacePoint(105, -105, 85)),
    ),
  );
  camera.up.copy(
    renderVectorToThree(
      coordinates.patientVectorToRender(patientSpaceVector(0, 1, 0)),
    ).normalize(),
  );
  const target = coordinates.patientPointToRender(
    patientSpacePoint(0, 0, 12),
  ).value;
  camera.lookAt(target.x, target.y, target.z);
  return camera;
}
