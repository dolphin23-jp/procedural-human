import type { EntityId, StructureId } from '../../packages/core/src/index';
import {
  patientSpacePoint,
  renderSpacePoint,
  vec3,
  type PatientSpacePoint,
} from '../../packages/math/src/index';
import type { Length } from '../../packages/units/src/index';
import type {
  OrderedPenetrationPathQuery,
  PenetrationLocation,
  PenetrationMembership,
  PenetrationTransition,
  SpatialRegionBinding,
  SpatialRegionId,
} from '../../packages/spatial/src/index';

declare const query: OrderedPenetrationPathQuery;
declare const location: PenetrationLocation;
declare const member: PenetrationMembership;
declare const transition: PenetrationTransition;
declare const binding: SpatialRegionBinding;
const length: Length = location.distanceFromStart;
const position: PatientSpacePoint = location.position;
const structure: StructureId = member.structureId;
const entity: EntityId = member.canonicalEntityId;
const region: SpatialRegionId = member.regionId;
const boundary: EntityId = transition.boundaryCrossings[0]!.boundaryId;
void [length, position, structure, entity, region, boundary];
// @ts-expect-error Physical distances cannot be raw numbers.
const rawLength: PenetrationLocation = { ...location, distanceFromStart: 1 };
// @ts-expect-error Vec3 lacks patient-space identity.
const rawPoint: PenetrationLocation = { ...location, position: vec3(0, 0, 0) };
const renderPoint: PenetrationLocation = {
  ...location,
  // @ts-expect-error Render-space points cannot replace patient-space positions.
  position: renderSpacePoint(0, 0, 0),
};
const rawStructure: PenetrationMembership = {
  ...member,
  // @ts-expect-error Structure ID must preserve its brand.
  structureId: 'structure',
};
const wrongEntity: PenetrationMembership = {
  ...member,
  // @ts-expect-error Canonical entity and patient structure identity are distinct.
  canonicalEntityId: member.structureId,
};
// @ts-expect-error Stable region IDs are required independently of StructureId.
const rawRegion: SpatialRegionBinding = { ...binding, regionId: 'region' };
query.execute({
  // @ts-expect-error Query only accepts patient-space coordinates.
  start: renderSpacePoint(0, 0, 0),
  end: patientSpacePoint(0, 0, 1),
});
// @ts-expect-error Coincident crossings still preserve typed boundary IDs.
const rawBoundary: typeof boundary = 'boundary';
void [
  rawLength,
  rawPoint,
  renderPoint,
  rawStructure,
  wrongEntity,
  rawRegion,
  rawBoundary,
];
