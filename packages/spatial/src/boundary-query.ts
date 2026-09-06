import type { BoundaryEntity } from '@procedural-human/anatomy';
import type { EntityId, StructureId } from '@procedural-human/core';
import {
  patientSpacePoint,
  type PatientSpacePoint,
} from '@procedural-human/math';
import {
  millimetres,
  toMillimetres,
  type Length,
} from '@procedural-human/units';
import type {
  BoundedSpatialRepresentationAdapter,
  PatientSpaceSegment,
} from './index.js';

export type SpatialPointLocation = 'outside' | 'boundary' | 'inside';

/**
 * Opt-in region capability; containsPoint alone cannot distinguish a surface.
 * intersectSegment must enumerate every isolated contact and both ends of every
 * boundary-overlap interval in (0,1). Endpoint contacts may be omitted.
 * Between consecutive contacts, classifyPoint must be constant. Duplicate hits
 * are permitted. Adapters must fail explicitly if they cannot satisfy this
 * finite partition contract (e.g. unresolved/open collision surfaces).
 * This describes geometry only, including for volume/SDF implementations.
 */
export interface RegionSpatialRepresentationAdapter
  extends BoundedSpatialRepresentationAdapter {
  classifyPoint(point: PatientSpacePoint): SpatialPointLocation;
}

declare const spatialRegionIdBrand: unique symbol;
export type SpatialRegionId = string & {
  readonly [spatialRegionIdBrand]: 'SpatialRegionId';
};
export const spatialRegionId = (value: string): SpatialRegionId =>
  value as SpatialRegionId;

/** A patient-scoped region; its identity is independent of replaceable geometry. */
export interface BoundaryRegionBinding {
  readonly boundary: BoundaryEntity;
  readonly regionId: SpatialRegionId;
  readonly structureId: StructureId;
  /** The complete surface of this region is associated with this boundary. */
  readonly representation: RegionSpatialRepresentationAdapter;
}

export interface BoundaryRegionSide {
  readonly regionId: SpatialRegionId;
  /** Outside means the complement of this region, not a named adjacent tissue. */
  readonly side: 'outside' | 'inside';
}

export interface BoundaryCrossing {
  readonly boundaryId: EntityId;
  readonly structureId: StructureId;
  readonly regionId: SpatialRegionId;
  readonly direction: 'entry' | 'exit';
  readonly from: BoundaryRegionSide;
  readonly to: BoundaryRegionSide;
  readonly position: PatientSpacePoint;
  readonly distanceFromStart: Length;
  /** p(t) = start + t * (end - start), dimensionless; strictly 0 < t < 1. */
  readonly t: number;
}

/** Numerical consistency check only, not clustering or anatomical accuracy. */
export const boundaryIntersectionConsistencyTolerance: Length =
  millimetres(1e-7);

export class BoundaryQueryFailure extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'BoundaryQueryFailure';
  }
}

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
const compareId = (a: string, b: string): number =>
  a < b ? -1 : a > b ? 1 : 0;

/** Stateless, patient-scoped query. No Interaction events or medical state writes. */
export class BoundaryQuery {
  readonly #bindings: readonly BoundaryRegionBinding[];

  constructor(bindings: readonly BoundaryRegionBinding[]) {
    const seen = new Set<string>();
    this.#bindings = Object.freeze(
      bindings.map((binding) => {
        // One semantic binding per region prevents duplicate/contradictory surfaces.
        if (seen.has(binding.regionId)) {
          throw new BoundaryQueryFailure(
            `Duplicate region binding: ${binding.regionId}`,
          );
        }
        seen.add(binding.regionId);
        if (typeof binding.representation.classifyPoint !== 'function') {
          throw new BoundaryQueryFailure(
            'Representation lacks region classification',
          );
        }
        return Object.freeze({
          ...binding,
          boundary: Object.freeze({ ...binding.boundary }),
        });
      }),
    );
  }

  execute(segment: PatientSpaceSegment): readonly BoundaryCrossing[] {
    checkPoint(segment.start);
    checkPoint(segment.end);
    const delta = axes.map(
      (axis) => segment.end.value[axis] - segment.start.value[axis],
    );
    const lengthMm = Math.hypot(...delta);
    if (!Number.isFinite(lengthMm))
      throw new BoundaryQueryFailure('Segment length overflow');
    if (lengthMm === 0) return Object.freeze([]);
    // Dominant-axis parameter avoids squaring large/small physical coordinates.
    const axis = axes.reduce((best, next) =>
      Math.abs(segment.end.value[next] - segment.start.value[next]) >
      Math.abs(segment.end.value[best] - segment.start.value[best])
        ? next
        : best,
    );
    const at = (t: number): PatientSpacePoint =>
      patientSpacePoint(
        segment.start.value.x +
          (segment.end.value.x - segment.start.value.x) * t,
        segment.start.value.y +
          (segment.end.value.y - segment.start.value.y) * t,
        segment.start.value.z +
          (segment.end.value.z - segment.start.value.z) * t,
      );
    const crossings: BoundaryCrossing[] = [];
    for (const binding of this.#bindings) {
      const representation = binding.representation;
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
      for (let i = 1; i < knots.length - 1; i += 1) {
        const before = states[i - 1]!;
        const after = states[i]!;
        if (before === after || before === 'boundary' || after === 'boundary')
          continue;
        const t = knots[i]!;
        const point = at(t);
        const position = Object.freeze({
          ...point,
          value: Object.freeze({ ...point.value }),
        });
        crossings.push(
          Object.freeze({
            boundaryId: binding.boundary.id,
            structureId: binding.structureId,
            regionId: binding.regionId,
            direction: before === 'outside' ? 'entry' : 'exit',
            from: Object.freeze({ regionId: binding.regionId, side: before }),
            to: Object.freeze({ regionId: binding.regionId, side: after }),
            position,
            distanceFromStart: millimetres(lengthMm * t),
            t,
          }),
        );
      }
    }
    crossings.sort(
      (a, b) =>
        a.t - b.t ||
        compareId(a.boundaryId, b.boundaryId) ||
        compareId(a.regionId, b.regionId) ||
        compareId(a.structureId, b.structureId) ||
        compareId(a.direction, b.direction),
    );
    return Object.freeze(crossings);
  }
}
