import {
  patientSpacePoint,
  patientSpaceVector,
  renderSpacePoint,
  renderSpaceVector,
} from '../../packages/math/src/index';
import { millimetres } from '../../packages/units/src/index';
import { PatientRenderTransform } from '../../packages/rendering-core/src/index';
import { ThreeFixtureRenderer } from '../../packages/rendering-three/src/index';

const settings = {
  patientOrigin: patientSpacePoint(0, 0, 0),
  patientToRenderRotation: { x: 0, y: 0, z: 0, w: 1 },
  millimetresPerRenderUnit: millimetres(100),
};
const transform = new PatientRenderTransform(settings);
transform.patientPointToRender(patientSpacePoint(10, 20, 30));
transform.renderPointToPatient(renderSpacePoint(1, 2, 3));
transform.patientVectorToRender(patientSpaceVector(1, 2, 3));
transform.renderVectorToPatient(renderSpaceVector(1, 2, 3));
// @ts-expect-error Registration cannot be omitted.
new PatientRenderTransform();
// @ts-expect-error Physical scale requires Length.
new PatientRenderTransform({ ...settings, millimetresPerRenderUnit: 100 });
new PatientRenderTransform({
  ...settings,
  // @ts-expect-error A render point cannot be a patient origin.
  patientOrigin: renderSpacePoint(0, 0, 0),
});
// @ts-expect-error Points retain their coordinate space.
transform.patientPointToRender(renderSpacePoint(0, 0, 0));
// @ts-expect-error Vectors cannot substitute for points.
transform.patientPointToRender(patientSpaceVector(0, 0, 0));
// @ts-expect-error Render vectors cannot substitute for patient displacements.
transform.patientVectorToRender(renderSpaceVector(0, 0, 0));
// @ts-expect-error Points cannot substitute for vectors.
transform.renderVectorToPatient(renderSpacePoint(0, 0, 0));
// @ts-expect-error Raw vectors are not tagged coordinates.
transform.renderPointToPatient({ x: 1, y: 2, z: 3 });
declare const canvas: HTMLCanvasElement;
new ThreeFixtureRenderer(canvas, { coordinates: transform });
// @ts-expect-error Runtime renderer requires explicit coordinates.
new ThreeFixtureRenderer(canvas, {});
