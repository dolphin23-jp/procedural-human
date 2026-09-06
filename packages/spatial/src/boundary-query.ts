import { partitionRegion, segmentTraversal } from './region-partition.js';
import type { BoundaryEntity } from '@procedural-human/anatomy';
import type { EntityId, StructureId } from '@procedural-human/core';
import type { PatientSpacePoint } from '@procedural-human/math';
import { millimetres, type Length } from '@procedural-human/units';
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
    const traversal = segmentTraversal(segment);
    const { lengthMm, at } = traversal;
    if (lengthMm === 0) return Object.freeze([]);
    const crossings: BoundaryCrossing[] = [];
    for (const binding of this.#bindings) {
      const { knots, states } = partitionRegion(
        traversal,
        binding.representation,
      );
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
