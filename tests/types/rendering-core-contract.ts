import {
  entityId,
  patientId,
  structureId,
} from '../../packages/core/src/index';
import {
  patientSpacePoint,
  patientSpaceVector,
  renderSpacePoint,
} from '../../packages/math/src/index';
import { degrees, millimetres } from '../../packages/units/src/index';
import { opacity } from '../../packages/rendering-core/src/index';
import type {
  CameraIntent,
  RenderingPresentationApi,
} from '../../packages/rendering-core/src/index';

declare const api: RenderingPresentationApi;
const id = structureId('structure.fixture.vein');
const origin = patientSpacePoint(0, 0, 0);
const normal = patientSpaceVector(0, 0, 1);
api.setVisibility({ structureId: id, visible: false });
api.setOpacity({ structureId: id, opacity: opacity(0.3) });
api.setSelection(id);
api.setSelection(null);
api.setClippingPlane({ origin, normal });
api.setClippingPlane(null);
api.applyCameraIntent({
  type: 'orbit',
  pivot: origin,
  axis: normal,
  angle: degrees(30),
});
api.applyCameraIntent({ type: 'pan', offset: patientSpaceVector(10, 0, 0) });
api.applyCameraIntent({ type: 'dolly', distance: millimetres(-5) });
api.applyCameraIntent({ type: 'focus', target: origin });

// @ts-expect-error Patient binding is readonly.
api.patientId = patientId('another');
// @ts-expect-error Mesh names are not semantic IDs.
api.setSelection('mesh.vein');
// @ts-expect-error Canonical identity cannot substitute for patient structure identity.
api.setSelection(entityId('vein'));
// @ts-expect-error Opacity must go through the validated constructor.
api.setOpacity({ structureId: id, opacity: 0.3 });
// @ts-expect-error Render Space is not Patient Space.
api.setClippingPlane({ origin: renderSpacePoint(0, 0, 0), normal });
// @ts-expect-error A point cannot substitute for a plane normal.
api.setClippingPlane({ origin, normal: origin });
api.applyCameraIntent({
  type: 'orbit',
  pivot: origin,
  axis: normal,
  // @ts-expect-error Angles are not unitless numbers.
  angle: 30,
});
// @ts-expect-error Displacement requires a vector, not a point.
api.applyCameraIntent({ type: 'pan', offset: origin });
// @ts-expect-error Dolly distance retains Length units.
api.applyCameraIntent({ type: 'dolly', distance: 5 });
// @ts-expect-error Focus cannot silently accept render coordinates.
api.applyCameraIntent({ type: 'focus', target: renderSpacePoint(0, 0, 0) });
// @ts-expect-error Clearing clipping must be explicit.
api.setClippingPlane();
// @ts-expect-error Visibility uses semantic IDs too.
api.setVisibility({ structureId: 'mesh', visible: true });

// All variants must remain discriminated and exhaustively handleable.
function intentKind(intent: CameraIntent): string {
  switch (intent.type) {
    case 'orbit':
      return String(intent.angle);
    case 'pan':
      return String(intent.offset.value.x);
    case 'dolly':
      return String(intent.distance);
    case 'focus':
      return String(intent.target.value.x);
    default: {
      const unreachable: never = intent;
      return unreachable;
    }
  }
}
void intentKind;
