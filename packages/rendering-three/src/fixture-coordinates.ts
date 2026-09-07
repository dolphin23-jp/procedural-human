import {
  patientSpaceDirection,
  patientSpacePoint,
} from '@procedural-human/math';
import {
  PatientRenderTransform,
  type PatientClippingPlane,
} from '@procedural-human/rendering-core';
import { millimetres } from '@procedural-human/units';

/** Explicit non-medical fixture configuration; never a registration fallback. */
export function createFixtureCoordinateTransform(): PatientRenderTransform {
  return new PatientRenderTransform({
    patientOrigin: patientSpacePoint(0, 0, 12),
    patientToRenderRotation: { x: 0, y: 0, z: 0, w: 1 },
    millimetresPerRenderUnit: millimetres(100),
  });
}

/** Oblique non-medical plane used only to exercise TASK-055 in the fixture UI. */
export function createFixtureDemoClippingPlane(): PatientClippingPlane {
  return Object.freeze({
    origin: patientSpacePoint(0, 0, 12),
    normal: patientSpaceDirection(Math.SQRT1_2, 0, Math.SQRT1_2),
  });
}
