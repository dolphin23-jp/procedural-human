import type { StructureId } from '../../packages/core/src/index';
import {
  patientSpacePoint,
  renderSpacePoint,
} from '../../packages/math/src/index';
import type {
  PenetrationPathElement,
  PointQueryResult,
  SpatialQueryApi,
} from '../../packages/spatial/src/index';
import type { DistanceQueryResult } from '../../packages/spatial/src/distance-query';

declare const api: SpatialQueryApi;
declare const structure: StructureId;

const pointResult: PointQueryResult = api.queryPoint(
  patientSpacePoint(0, 0, 0),
);
const segmentResult: readonly PenetrationPathElement[] = api.querySegment({
  start: patientSpacePoint(0, 0, 0),
  end: patientSpacePoint(0, 0, 1),
});
const distanceResult: DistanceQueryResult = api.distanceTo(
  patientSpacePoint(0, 0, 0),
  structure,
);
void [pointResult, segmentResult, distanceResult];

// @ts-expect-error Public point queries require Patient Space.
api.queryPoint(renderSpacePoint(0, 0, 0));
api.querySegment({
  // @ts-expect-error Segment start cannot be Render Space.
  start: renderSpacePoint(0, 0, 0),
  end: patientSpacePoint(0, 0, 1),
});
// @ts-expect-error StructureId remains branded at the public boundary.
api.distanceTo(patientSpacePoint(0, 0, 0), 'structure');
