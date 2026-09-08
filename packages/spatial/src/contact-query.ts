import type { EntityId, StructureId } from '@procedural-human/core';
import type { PatientSpacePoint } from '@procedural-human/math';
import { millimetres, type Length } from '@procedural-human/units';
import { BoundaryQueryFailure } from './boundary-query.js';
import type { PatientSpaceSegment } from './index.js';
import type { SpatialRegionBinding } from './penetration-path.js';
import { partitionRegion, segmentTraversal } from './region-partition.js';

export interface SpatialContactLocation {
  /** Dimensionless segment parameter, including endpoints. */
  readonly t: number;
  readonly position: PatientSpacePoint;
  readonly distanceFromStart: Length;
}

/** Maximal closed intersection of a segment with one structure's region union. */
export interface SpatialContactInterval {
  readonly structureId: StructureId;
  readonly canonicalEntityId: EntityId;
  readonly start: SpatialContactLocation;
  readonly end: SpatialContactLocation;
}

/** Optional public capability; independent of ordered penetration semantics. */
export interface SpatialContactQueryApi {
  queryContacts(
    segment: PatientSpaceSegment,
  ): readonly SpatialContactInterval[];
}

const compareId = (a: string, b: string): number =>
  a < b ? -1 : a > b ? 1 : 0;

/** Internal implementation. Consumers use SpatialContactQueryApi. */
export class ContactQuery {
  readonly #regions: readonly SpatialRegionBinding[];

  constructor(regions: readonly SpatialRegionBinding[]) {
    this.#regions = regions;
  }

  execute(segment: PatientSpaceSegment): readonly SpatialContactInterval[] {
    const traversal = segmentTraversal(segment);
    if (traversal.lengthMm === 0) return Object.freeze([]);
    const byStructure = new Map<
      StructureId,
      { entity: EntityId; intervals: [number, number][] }
    >();
    for (const region of this.#regions) {
      let group = byStructure.get(region.structureId);
      if (group && group.entity !== region.canonicalEntityId) {
        throw new BoundaryQueryFailure(
          'Contact regions disagree on canonical structure identity',
        );
      }
      if (!group) {
        group = { entity: region.canonicalEntityId, intervals: [] };
        byStructure.set(region.structureId, group);
      }
      const { knots, states } = partitionRegion(
        traversal,
        region.representation,
      );
      for (let i = 0; i < states.length; i += 1) {
        if (states[i] !== 'outside') {
          group.intervals.push([knots[i]!, knots[i + 1]!]);
        }
      }
      // Every interior knot is a validated geometric contact from the adapter.
      // Keep isolated tangencies even when adjacent open intervals are outside.
      for (const t of knots) {
        if (t > 0 && t < 1) {
          group.intervals.push([t, t]);
        } else {
          // The region contract permits omission of endpoint intersections.
          const state = region.representation.classifyPoint(traversal.at(t));
          if (!['inside', 'outside', 'boundary'].includes(state)) {
            throw new BoundaryQueryFailure('Invalid region classification');
          }
          if (state !== 'outside') group.intervals.push([t, t]);
        }
      }
    }
    const location = (t: number): SpatialContactLocation => {
      const point = traversal.at(t);
      return Object.freeze({
        t,
        position: Object.freeze({
          ...point,
          value: Object.freeze({ ...point.value }),
        }),
        distanceFromStart: millimetres(traversal.lengthMm * t),
      });
    };
    const result: SpatialContactInterval[] = [];
    for (const [structureId, group] of byStructure) {
      group.intervals.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
      const merged: [number, number][] = [];
      for (const interval of group.intervals) {
        const last = merged[merged.length - 1];
        if (last && interval[0] <= last[1]) {
          last[1] = Math.max(last[1], interval[1]);
        } else {
          merged.push([...interval]);
        }
      }
      for (const [start, end] of merged) {
        result.push(
          Object.freeze({
            structureId,
            canonicalEntityId: group.entity,
            start: location(start),
            end: location(end),
          }),
        );
      }
    }
    result.sort(
      (a, b) =>
        a.start.t - b.start.t ||
        compareId(a.structureId, b.structureId) ||
        a.end.t - b.end.t,
    );
    return Object.freeze(result);
  }
}
