import { patientSpacePoint } from '@procedural-human/math';
import { PatientRenderTransform } from '@procedural-human/rendering-core';
import { millimetres } from '@procedural-human/units';

/** Explicit non-medical fixture configuration; never a registration fallback. */
export function createFixtureCoordinateTransform(): PatientRenderTransform {
  return new PatientRenderTransform({
    patientOrigin: patientSpacePoint(0, 0, 12),
    patientToRenderRotation: { x: 0, y: 0, z: 0, w: 1 },
    millimetresPerRenderUnit: millimetres(100),
  });
}
