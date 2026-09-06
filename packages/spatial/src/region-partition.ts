// Internal shared numerical partition for TASK-039 and TASK-042.
import {
  patientSpacePoint,
  type PatientSpacePoint,
} from '@procedural-human/math';
import { toMillimetres } from '@procedural-human/units';
import {
  BoundaryQueryFailure,
  boundaryIntersectionConsistencyTolerance,
  type RegionSpatialRepresentationAdapter,
  type SpatialPointLocation,
} from './boundary-query.js';
import type { PatientSpaceSegment } from './index.js';

const axes = ['x', 'y', 'z'] as const;
const checkPoint = (point: PatientSpacePoint): void => {
  if (
    point.space !== 'patient' ||
    point.kind !== 'point' ||
    !axes.every((axis) => Number.isFinite(point.value[axis]))
  ) {
    throw new BoundaryQueryFailure(
      'Expected finite patient-space coordinates in millimetres',
    );
  }
};

export const segmentTraversal = (segment: PatientSpaceSegment) => {
  checkPoint(segment.start);
  checkPoint(segment.end);
  const delta = axes.map(
    (axis) => segment.end.value[axis] - segment.start.value[axis],
  );
  const lengthMm = Math.hypot(...delta);
  if (!Number.isFinite(lengthMm))
    throw new BoundaryQueryFailure('Segment length overflow');
  // Dominant-axis parameter avoids squaring large/small physical coordinates.
  const axis = axes.reduce((best, next) =>
    Math.abs(segment.end.value[next] - segment.start.value[next]) >
    Math.abs(segment.end.value[best] - segment.start.value[best])
      ? next
      : best,
  );
  const at = (t: number): PatientSpacePoint =>
    patientSpacePoint(
      segment.start.value.x + (segment.end.value.x - segment.start.value.x) * t,
      segment.start.value.y + (segment.end.value.y - segment.start.value.y) * t,
      segment.start.value.z + (segment.end.value.z - segment.start.value.z) * t,
    );
  return { segment, lengthMm, axis, at };
};

export const partitionRegion = (
  traversal: ReturnType<typeof segmentTraversal>,
  representation: RegionSpatialRepresentationAdapter,
): { knots: number[]; states: SpatialPointLocation[] } => {
  const { segment, axis, at } = traversal;
  const parameters = [0, 1];
  for (const point of representation.intersectSegment(segment)) {
    checkPoint(point);
    const t =
      (point.value[axis] - segment.start.value[axis]) /
      (segment.end.value[axis] - segment.start.value[axis]);
    const projected = at(t);
    const errorMm = Math.hypot(
      ...axes.map((a) => point.value[a] - projected.value[a]),
    );
    if (
      !Number.isFinite(t) ||
      t < 0 ||
      t > 1 ||
      !Number.isFinite(errorMm) ||
      errorMm > toMillimetres(boundaryIntersectionConsistencyTolerance)
    ) {
      throw new BoundaryQueryFailure(
        'Adapter returned an intersection off the segment',
      );
    }
    parameters.push(t);
  }
  // Exact equality only: no epsilon may merge away a thin spatial region.
  const knots = [...new Set(parameters)].sort((a, b) => a - b);
  const states: SpatialPointLocation[] = [];
  for (let i = 1; i < knots.length; i += 1) {
    const left = knots[i - 1]!;
    const right = knots[i]!;
    const middle = left + (right - left) / 2;
    const point = at(middle);
    if (
      !(middle > left && middle < right) ||
      [at(left), at(right)].some((end) =>
        axes.every((a) => end.value[a] === point.value[a]),
      )
    ) {
      throw new BoundaryQueryFailure(
        'Contact interval cannot be resolved at numeric precision',
      );
    }
    const state = representation.classifyPoint(point);
    if (!['inside', 'outside', 'boundary'].includes(state)) {
      throw new BoundaryQueryFailure('Invalid region classification');
    }
    states.push(state);
  }
  return { knots, states };
};
