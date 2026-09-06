import type { BoundaryEntity } from '@procedural-human/anatomy';
import type { EntityId, StructureId } from '@procedural-human/core';
import type { PatientSpacePoint } from '@procedural-human/math';
import { millimetres, type Length } from '@procedural-human/units';
import {
  BoundaryQuery,
  type BoundaryCrossing,
  type RegionSpatialRepresentationAdapter,
  type SpatialRegionId,
} from './boundary-query.js';
import type {
  PatientSpaceSegment,
  SpatialIndexEntry,
  VascularLumenKind,
} from './index.js';
import { partitionRegion, segmentTraversal } from './region-partition.js';

/** Opt-in region binding; multiple regions may share a StructureId. */
export interface SpatialRegionBinding extends SpatialIndexEntry {
  readonly regionId: SpatialRegionId;
  readonly representation: RegionSpatialRepresentationAdapter;
}

/** Resolves geometry through regionId, never through JS object identity. */
export interface PenetrationBoundaryBinding {
  readonly regionId: SpatialRegionId;
  readonly boundary: BoundaryEntity;
}

export interface PenetrationMembership {
  readonly regionId: SpatialRegionId;
  readonly structureId: StructureId;
  readonly canonicalEntityId: EntityId;
  readonly tissue: boolean;
  /** null: no lumen role. Nested null kind: lumen with unknown vascular kind. */
  readonly lumen: {
    readonly vascularLumenKind: VascularLumenKind | null;
  } | null;
}

export interface PenetrationLocation {
  /** p(t) = start + t * (end - start); dimensionless, 0 <= t <= 1. */
  readonly t: number;
  readonly position: PatientSpacePoint;
  readonly distanceFromStart: Length;
}

export interface PenetrationSpan {
  readonly kind: 'span';
  readonly start: PenetrationLocation;
  readonly end: PenetrationLocation;
  /** All simultaneous interior memberships; [] is outside all supplied regions. */
  readonly memberships: readonly PenetrationMembership[];
}

export interface PenetrationTransition {
  readonly kind: 'transition';
  readonly at: PenetrationLocation;
  /** Coincident SETS, sorted by regionId, not a physical sequence. */
  readonly entered: readonly PenetrationMembership[];
  readonly exited: readonly PenetrationMembership[];
  /** Unmodified TASK-039 semantics, including identity, sides and direction. */
  readonly boundaryCrossings: readonly BoundaryCrossing[];
}

export type PenetrationPathElement = PenetrationSpan | PenetrationTransition;

export class PenetrationPathFailure extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PenetrationPathFailure';
  }
}

const compareId = (a: string, b: string): number =>
  a < b ? -1 : a > b ? 1 : 0;

const membershipFor = (binding: SpatialRegionBinding): PenetrationMembership =>
  Object.freeze({
    regionId: binding.regionId,
    structureId: binding.structureId,
    canonicalEntityId: binding.canonicalEntityId,
    tissue: binding.membershipRoles.includes('tissue'),
    lumen: binding.membershipRoles.includes('lumen')
      ? Object.freeze({ vascularLumenKind: binding.vascularLumenKind ?? null })
      : null,
  });

/** Stateless traversal of a fixed patient/asset state, with no event emission. */
export class OrderedPenetrationPathQuery {
  readonly #regions: readonly SpatialRegionBinding[];
  readonly #boundaries: BoundaryQuery;

  constructor(
    regions: readonly SpatialRegionBinding[],
    boundaries: readonly PenetrationBoundaryBinding[] = [],
  ) {
    const byRegion = new Map<SpatialRegionId, SpatialRegionBinding>();
    for (const region of regions) {
      if (byRegion.has(region.regionId))
        throw new PenetrationPathFailure(
          `Duplicate region binding: ${region.regionId}`,
        );
      if (typeof region.representation.classifyPoint !== 'function')
        throw new PenetrationPathFailure(
          'Representation lacks region classification',
        );
      if (
        region.membershipRoles.some(
          (role) => role !== 'tissue' && role !== 'lumen',
        )
      )
        throw new PenetrationPathFailure('Invalid membership role');
      if (region.vascularLumenKind !== undefined) {
        if (!region.membershipRoles.includes('lumen'))
          throw new PenetrationPathFailure(
            'Vascular lumen classification requires lumen membership',
          );
        if (
          region.vascularLumenKind !== 'venous' &&
          region.vascularLumenKind !== 'arterial'
        )
          throw new PenetrationPathFailure(
            'Invalid vascular lumen classification',
          );
      }
      byRegion.set(
        region.regionId,
        Object.freeze({
          ...region,
          membershipRoles: Object.freeze([...region.membershipRoles]),
        }),
      );
    }
    this.#regions = Object.freeze(
      [...byRegion.values()].sort((a, b) => compareId(a.regionId, b.regionId)),
    );
    // TASK-039's complete-region-surface restriction remains confined to this
    // binding bridge. The output model does not require every region to have a
    // boundary, nor every future boundary to describe a finite-thickness volume.
    this.#boundaries = new BoundaryQuery(
      boundaries.map(({ regionId, boundary }) => {
        const region = byRegion.get(regionId);
        if (!region)
          throw new PenetrationPathFailure(
            `Unknown boundary region: ${regionId}`,
          );
        return {
          regionId,
          boundary,
          structureId: region.structureId,
          representation: region.representation,
        };
      }),
    );
  }

  execute(segment: PatientSpaceSegment): readonly PenetrationPathElement[] {
    const traversal = segmentTraversal(segment);
    if (traversal.lengthMm === 0) return Object.freeze([]);
    const partitions = this.#regions.map((region) => {
      const partition = partitionRegion(traversal, region.representation);
      if (partition.states.includes('boundary'))
        throw new PenetrationPathFailure(
          `Boundary overlap cannot define an interior traversal: ${region.regionId}`,
        );
      return { ...partition, membership: membershipFor(region), cursor: 0 };
    });
    const crossings = this.#boundaries.execute(segment);
    const knots = [
      ...new Set([0, 1, ...partitions.flatMap((p) => p.knots)]),
    ].sort((a, b) => a - b);
    const location = (t: number): PenetrationLocation => {
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
    const span = (
      start: PenetrationLocation,
      end: PenetrationLocation,
      memberships: readonly PenetrationMembership[],
    ): PenetrationSpan =>
      Object.freeze({ kind: 'span', start, end, memberships });
    const elements: PenetrationPathElement[] = [];
    let previous: PenetrationSpan | undefined;
    for (let i = 0; i < knots.length - 1; i += 1) {
      const left = knots[i]!;
      const right = knots[i + 1]!;
      // Each region was classified on its own complete geometric partition.
      // Splitting those constant cells at other regions' knots needs no probing,
      // and cannot lose a thin region to an unrelated sampling scale.
      const memberships = Object.freeze(
        partitions.flatMap((partition) => {
          while (partition.knots[partition.cursor + 1]! <= left)
            partition.cursor += 1;
          return partition.states[partition.cursor] === 'inside'
            ? [partition.membership]
            : [];
        }),
      );
      const start = location(left);
      const end = location(right);
      if (previous) {
        const beforeIds = new Set(previous.memberships.map((m) => m.regionId));
        const afterIds = new Set(memberships.map((m) => m.regionId));
        const entered = Object.freeze(
          memberships.filter((m) => !beforeIds.has(m.regionId)),
        );
        const exited = Object.freeze(
          previous.memberships.filter((m) => !afterIds.has(m.regionId)),
        );
        const boundaryCrossings = Object.freeze(
          crossings.filter((crossing) => crossing.t === left),
        );
        if (
          entered.length === 0 &&
          exited.length === 0 &&
          boundaryCrossings.length === 0
        ) {
          // Isolated contacts with unchanged open-interval occupancy are not
          // penetration transitions. They do not split the output span.
          previous = span(previous.start, end, memberships);
          elements[elements.length - 1] = previous;
          continue;
        }
        elements.push(
          Object.freeze({
            kind: 'transition',
            at: start,
            entered,
            exited,
            boundaryCrossings,
          }),
        );
      }
      previous = span(start, end, memberships);
      elements.push(previous);
    }
    return Object.freeze(elements);
  }
}
