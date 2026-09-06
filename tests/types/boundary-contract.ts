import type {
  BoundaryCrossing,
  BoundaryRegionBinding,
  BoundaryQuery,
  SpatialRegionId,
} from '../../packages/spatial/src/index';
import type { PatientSpacePoint } from '../../packages/math/src/index';
import {
  patientSpacePoint,
  renderSpacePoint,
  vec3,
} from '../../packages/math/src/index';
import type { Length } from '../../packages/units/src/index';

declare const crossing: BoundaryCrossing;
declare const query: BoundaryQuery;
declare const binding: BoundaryRegionBinding;
const length: Length = crossing.distanceFromStart;
const point: PatientSpacePoint = crossing.position;
const region: SpatialRegionId = binding.regionId;
void [length, point, region];
// @ts-expect-error Physical distances require Length.
const rawLength: BoundaryCrossing = { ...crossing, distanceFromStart: 4 };
// @ts-expect-error A Vec3 is not a patient-space point.
const rawPoint: BoundaryCrossing = { ...crossing, position: vec3(0, 0, 0) };
query.execute({
  // @ts-expect-error Render coordinates are not patient coordinates.
  start: renderSpacePoint(0, 0, 0),
  end: patientSpacePoint(0, 0, 1),
});
// @ts-expect-error Spatial region references must be explicitly typed.
const rawRegion: BoundaryRegionBinding = { ...binding, regionId: 'vein' };
void [rawLength, rawPoint, rawRegion];
