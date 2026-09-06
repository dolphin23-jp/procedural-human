export * from './penetration-path.js';
export * from './boundary-query.js';
import { DistanceQuery, type DistanceQueryResult } from './distance-query.js';
import {
  OrderedPenetrationPathQuery,
  type PenetrationBoundaryBinding,
  type PenetrationPathElement,
  type SpatialRegionBinding,
} from './penetration-path.js';
import type {
  RegionSpatialRepresentationAdapter,
  SpatialPointLocation,
} from './boundary-query.js';
import type { EntityId, StructureId } from '@procedural-human/core';
import type { PatientSpacePoint } from '@procedural-human/math';
import {
  millimetres,
  toMillimetres,
  type Length,
} from '@procedural-human/units';

export interface PatientSpaceSegment {
  readonly start: PatientSpacePoint;
  readonly end: PatientSpacePoint;
}

export const patientSpaceSegment = (
  start: PatientSpacePoint,
  end: PatientSpacePoint,
): PatientSpaceSegment => Object.freeze({ start, end });

/**
 * Geometry capability implemented by a patient-space representation adapter.
 *
 * This contract deliberately does not assign anatomical, lumen, boundary,
 * entry/exit, ordering, or procedure meaning to the returned geometry. Those
 * semantics belong to later Spatial Query tasks.
 */
export interface SpatialRepresentationAdapter {
  containsPoint(point: PatientSpacePoint): boolean;
  intersectSegment(segment: PatientSpaceSegment): readonly PatientSpacePoint[];
  distanceToPoint(point: PatientSpacePoint): Length;
}

export interface PatientSpaceBoundingBox {
  readonly min: PatientSpacePoint;
  readonly max: PatientSpacePoint;
}

export interface BoundedSpatialRepresentationAdapter
  extends SpatialRepresentationAdapter {
  readonly bounds: PatientSpaceBoundingBox;
}

export type SpatialMembershipRole = 'tissue' | 'lumen';
export type VascularLumenKind = 'venous' | 'arterial';

export interface SpatialIndexEntry {
  readonly structureId: StructureId;
  readonly canonicalEntityId: EntityId;
  readonly name: string;
  readonly membershipRoles: readonly SpatialMembershipRole[];
  /**
   * Explicit vascular semantics for a lumen representation.
   * Spatial never infers this from names, IDs, geometry, or renderer metadata.
   */
  readonly vascularLumenKind?: VascularLumenKind;
  readonly representation: BoundedSpatialRepresentationAdapter;
}

const coordinate = (point: PatientSpacePoint, axis: 'x' | 'y' | 'z') =>
  point.value[axis];

const pointInBounds = (
  point: PatientSpacePoint,
  bounds: PatientSpaceBoundingBox,
): boolean =>
  coordinate(point, 'x') >= coordinate(bounds.min, 'x') &&
  coordinate(point, 'x') <= coordinate(bounds.max, 'x') &&
  coordinate(point, 'y') >= coordinate(bounds.min, 'y') &&
  coordinate(point, 'y') <= coordinate(bounds.max, 'y') &&
  coordinate(point, 'z') >= coordinate(bounds.min, 'z') &&
  coordinate(point, 'z') <= coordinate(bounds.max, 'z');

const segmentBounds = (
  segment: PatientSpaceSegment,
): PatientSpaceBoundingBox => ({
  min: {
    space: 'patient',
    kind: 'point',
    value: {
      x: Math.min(segment.start.value.x, segment.end.value.x),
      y: Math.min(segment.start.value.y, segment.end.value.y),
      z: Math.min(segment.start.value.z, segment.end.value.z),
    },
  },
  max: {
    space: 'patient',
    kind: 'point',
    value: {
      x: Math.max(segment.start.value.x, segment.end.value.x),
      y: Math.max(segment.start.value.y, segment.end.value.y),
      z: Math.max(segment.start.value.z, segment.end.value.z),
    },
  },
});

const boundsOverlap = (
  left: PatientSpaceBoundingBox,
  right: PatientSpaceBoundingBox,
): boolean =>
  left.min.value.x <= right.max.value.x &&
  left.max.value.x >= right.min.value.x &&
  left.min.value.y <= right.max.value.y &&
  left.max.value.y >= right.min.value.y &&
  left.min.value.z <= right.max.value.z &&
  left.max.value.z >= right.min.value.z;

export class BasicSpatialIndex {
  readonly #entries: readonly SpatialIndexEntry[];

  constructor(entries: readonly SpatialIndexEntry[]) {
    for (const entry of entries) {
      if (
        entry.vascularLumenKind !== undefined &&
        !entry.membershipRoles.includes('lumen')
      ) {
        throw new Error(
          'Vascular lumen classification requires lumen membership',
        );
      }
    }
    this.#entries = Object.freeze([...entries]);
  }

  candidatesForPoint(point: PatientSpacePoint): readonly SpatialIndexEntry[] {
    return this.#entries.filter((entry) =>
      pointInBounds(point, entry.representation.bounds),
    );
  }

  candidatesForSegment(
    segment: PatientSpaceSegment,
  ): readonly SpatialIndexEntry[] {
    const queryBounds = segmentBounds(segment);
    return this.#entries.filter((entry) =>
      boundsOverlap(queryBounds, entry.representation.bounds),
    );
  }
}

export interface SpatialMatch {
  readonly structureId: StructureId;
  readonly canonicalEntityId: EntityId;
  readonly name: string;
}

export interface LumenSpatialMatch extends SpatialMatch {
  /**
   * null means lumen membership is known but no venous/arterial semantic
   * classification was supplied. The query does not guess.
   */
  readonly vascularLumenKind: VascularLumenKind | null;
}

export interface PointQueryResult {
  readonly structures: readonly SpatialMatch[];
  readonly tissues: readonly SpatialMatch[];
  readonly lumens: readonly LumenSpatialMatch[];
}

const matchFor = (entry: SpatialIndexEntry): SpatialMatch =>
  Object.freeze({
    structureId: entry.structureId,
    canonicalEntityId: entry.canonicalEntityId,
    name: entry.name,
  });

const lumenMatchFor = (entry: SpatialIndexEntry): LumenSpatialMatch =>
  Object.freeze({
    ...matchFor(entry),
    vascularLumenKind: entry.vascularLumenKind ?? null,
  });

export class PointQuery {
  readonly #index: BasicSpatialIndex;

  constructor(index: BasicSpatialIndex) {
    this.#index = index;
  }

  execute(point: PatientSpacePoint): PointQueryResult {
    const containing = this.#index
      .candidatesForPoint(point)
      .filter((entry) => entry.representation.containsPoint(point));

    const structures = containing.map(matchFor);
    const tissues = containing
      .filter((entry) => entry.membershipRoles.includes('tissue'))
      .map(matchFor);
    const lumens = containing
      .filter((entry) => entry.membershipRoles.includes('lumen'))
      .map(lumenMatchFor);

    return Object.freeze({
      structures: Object.freeze(structures),
      tissues: Object.freeze(tissues),
      lumens: Object.freeze(lumens),
    });
  }
}

export interface SegmentQueryHit extends SpatialMatch {
  readonly intersections: readonly PatientSpacePoint[];
}

export class SegmentQuery {
  readonly #index: BasicSpatialIndex;

  constructor(index: BasicSpatialIndex) {
    this.#index = index;
  }

  execute(segment: PatientSpaceSegment): readonly SegmentQueryHit[] {
    const hits: SegmentQueryHit[] = [];

    for (const entry of this.#index.candidatesForSegment(segment)) {
      const intersections = entry.representation.intersectSegment(segment);
      if (intersections.length === 0) {
        continue;
      }
      hits.push(
        Object.freeze({
          ...matchFor(entry),
          intersections: Object.freeze([...intersections]),
        }),
      );
    }

    return Object.freeze(hits);
  }
}

const patientPoint = (x: number, y: number, z: number): PatientSpacePoint => ({
  space: 'patient',
  kind: 'point',
  value: { x, y, z },
});

const pointAlongSegment = (
  segment: PatientSpaceSegment,
  t: number,
): PatientSpacePoint =>
  patientPoint(
    segment.start.value.x + (segment.end.value.x - segment.start.value.x) * t,
    segment.start.value.y + (segment.end.value.y - segment.start.value.y) * t,
    segment.start.value.z + (segment.end.value.z - segment.start.value.z) * t,
  );

const squaredDistance = (
  point: PatientSpacePoint,
  x: number,
  y: number,
  z: number,
): number => {
  const dx = point.value.x - x;
  const dy = point.value.y - y;
  const dz = point.value.z - z;
  return dx * dx + dy * dy + dz * dz;
};

const assertRegionBounds = (bounds: PatientSpaceBoundingBox): void => {
  for (const axis of ['x', 'y', 'z'] as const) {
    if (
      !Number.isFinite(bounds.min.value[axis]) ||
      !Number.isFinite(bounds.max.value[axis]) ||
      bounds.min.value[axis] >= bounds.max.value[axis]
    ) {
      throw new Error(
        'Region bounds must be finite and have resolvable positive extent',
      );
    }
  }
};

export interface AxisAlignedBoxDescriptor {
  readonly center: PatientSpacePoint;
  readonly size: readonly [Length, Length, Length];
}

export class AxisAlignedBoxSpatialAdapter
  implements RegionSpatialRepresentationAdapter
{
  readonly bounds: PatientSpaceBoundingBox;

  constructor(descriptor: AxisAlignedBoxDescriptor) {
    if (
      !descriptor.size.every(
        (size) =>
          Number.isFinite(toMillimetres(size)) && toMillimetres(size) > 0,
      )
    ) {
      throw new Error('Box region sizes must be finite positive Length values');
    }
    const halfX = toMillimetres(descriptor.size[0]) / 2;
    const halfY = toMillimetres(descriptor.size[1]) / 2;
    const halfZ = toMillimetres(descriptor.size[2]) / 2;
    this.bounds = Object.freeze({
      min: patientPoint(
        descriptor.center.value.x - halfX,
        descriptor.center.value.y - halfY,
        descriptor.center.value.z - halfZ,
      ),
      max: patientPoint(
        descriptor.center.value.x + halfX,
        descriptor.center.value.y + halfY,
        descriptor.center.value.z + halfZ,
      ),
    });
    assertRegionBounds(this.bounds);
  }

  containsPoint(point: PatientSpacePoint): boolean {
    return pointInBounds(point, this.bounds);
  }

  classifyPoint(point: PatientSpacePoint): SpatialPointLocation {
    if (!this.containsPoint(point)) return 'outside';
    return (['x', 'y', 'z'] as const).some(
      (axis) =>
        point.value[axis] === this.bounds.min.value[axis] ||
        point.value[axis] === this.bounds.max.value[axis],
    )
      ? 'boundary'
      : 'inside';
  }

  intersectSegment(segment: PatientSpaceSegment): readonly PatientSpacePoint[] {
    let near = -Infinity;
    let far = Infinity;

    for (const axis of ['x', 'y', 'z'] as const) {
      const start = segment.start.value[axis];
      const direction = segment.end.value[axis] - start;
      const min = this.bounds.min.value[axis];
      const max = this.bounds.max.value[axis];

      if (direction === 0) {
        if (start < min || start > max) {
          return Object.freeze([]);
        }
        continue;
      }

      const first = (min - start) / direction;
      const second = (max - start) / direction;
      const axisNear = Math.min(first, second);
      const axisFar = Math.max(first, second);
      near = Math.max(near, axisNear);
      far = Math.min(far, axisFar);
      if (near > far) {
        return Object.freeze([]);
      }
    }

    // All contacts, including endpoints and the ends of boundary overlaps.
    const parameters = [near, far].filter((t) => t >= 0 && t <= 1);
    if (this.classifyPoint(segment.start) === 'boundary') parameters.push(0);
    if (this.classifyPoint(segment.end) === 'boundary') parameters.push(1);
    parameters.sort((left, right) => left - right);

    return Object.freeze(parameters.map((t) => pointAlongSegment(segment, t)));
  }

  distanceToPoint(point: PatientSpacePoint): Length {
    const dx = Math.max(
      this.bounds.min.value.x - point.value.x,
      0,
      point.value.x - this.bounds.max.value.x,
    );
    const dy = Math.max(
      this.bounds.min.value.y - point.value.y,
      0,
      point.value.y - this.bounds.max.value.y,
    );
    const dz = Math.max(
      this.bounds.min.value.z - point.value.z,
      0,
      point.value.z - this.bounds.max.value.z,
    );
    return millimetres(Math.sqrt(dx * dx + dy * dy + dz * dz));
  }
}

export interface XAxisCylinderDescriptor {
  readonly center: PatientSpacePoint;
  readonly radius: Length;
  readonly length: Length;
}

export class XAxisCylinderSpatialAdapter
  implements RegionSpatialRepresentationAdapter
{
  readonly #center: PatientSpacePoint;
  readonly #radiusMm: number;
  readonly #halfLengthMm: number;
  readonly bounds: PatientSpaceBoundingBox;

  constructor(descriptor: XAxisCylinderDescriptor) {
    if (
      ![descriptor.radius, descriptor.length].every(
        (size) =>
          Number.isFinite(toMillimetres(size)) && toMillimetres(size) > 0,
      )
    ) {
      throw new Error(
        'Cylinder region dimensions must be finite positive Length values',
      );
    }
    this.#center = descriptor.center;
    this.#radiusMm = toMillimetres(descriptor.radius);
    this.#halfLengthMm = toMillimetres(descriptor.length) / 2;
    this.bounds = Object.freeze({
      min: patientPoint(
        descriptor.center.value.x - this.#halfLengthMm,
        descriptor.center.value.y - this.#radiusMm,
        descriptor.center.value.z - this.#radiusMm,
      ),
      max: patientPoint(
        descriptor.center.value.x + this.#halfLengthMm,
        descriptor.center.value.y + this.#radiusMm,
        descriptor.center.value.z + this.#radiusMm,
      ),
    });
    assertRegionBounds(this.bounds);
  }

  containsPoint(point: PatientSpacePoint): boolean {
    const axial = Math.abs(point.value.x - this.#center.value.x);
    const dy = point.value.y - this.#center.value.y;
    const dz = point.value.z - this.#center.value.z;
    return (
      axial <= this.#halfLengthMm &&
      dy * dy + dz * dz <= this.#radiusMm * this.#radiusMm
    );
  }

  classifyPoint(point: PatientSpacePoint): SpatialPointLocation {
    if (!this.containsPoint(point)) return 'outside';
    const axial = Math.abs(point.value.x - this.#center.value.x);
    const dy = point.value.y - this.#center.value.y;
    const dz = point.value.z - this.#center.value.z;
    return axial === this.#halfLengthMm ||
      dy * dy + dz * dz === this.#radiusMm * this.#radiusMm
      ? 'boundary'
      : 'inside';
  }

  intersectSegment(segment: PatientSpaceSegment): readonly PatientSpacePoint[] {
    const sx = segment.start.value.x;
    const sy = segment.start.value.y - this.#center.value.y;
    const sz = segment.start.value.z - this.#center.value.z;
    const dx = segment.end.value.x - segment.start.value.x;
    const dy = segment.end.value.y - segment.start.value.y;
    const dz = segment.end.value.z - segment.start.value.z;
    const parameters: number[] = [];

    const a = dy * dy + dz * dz;
    const b = 2 * (sy * dy + sz * dz);
    const c = sy * sy + sz * sz - this.#radiusMm * this.#radiusMm;
    if (a !== 0) {
      const discriminant = b * b - 4 * a * c;
      if (discriminant >= 0) {
        const root = Math.sqrt(discriminant);
        for (const t of [(-b - root) / (2 * a), (-b + root) / (2 * a)]) {
          if (t < 0 || t > 1) {
            continue;
          }
          const x = sx + dx * t;
          if (
            Math.abs(x - this.#center.value.x) <= this.#halfLengthMm &&
            !parameters.includes(t)
          ) {
            parameters.push(t);
          }
        }
      }
    }

    if (dx !== 0) {
      for (const capX of [
        this.#center.value.x - this.#halfLengthMm,
        this.#center.value.x + this.#halfLengthMm,
      ]) {
        const t = (capX - sx) / dx;
        if (t < 0 || t > 1 || parameters.includes(t)) {
          continue;
        }
        const y = sy + dy * t;
        const z = sz + dz * t;
        if (y * y + z * z <= this.#radiusMm * this.#radiusMm) {
          parameters.push(t);
        }
      }
    }

    parameters.sort((left, right) => left - right);
    return Object.freeze(parameters.map((t) => pointAlongSegment(segment, t)));
  }

  distanceToPoint(point: PatientSpacePoint): Length {
    if (this.containsPoint(point)) {
      return millimetres(0);
    }

    const clampedX = Math.min(
      this.#center.value.x + this.#halfLengthMm,
      Math.max(this.#center.value.x - this.#halfLengthMm, point.value.x),
    );
    const dy = point.value.y - this.#center.value.y;
    const dz = point.value.z - this.#center.value.z;
    const radialDistance = Math.sqrt(dy * dy + dz * dz);
    const radialScale =
      radialDistance === 0 ? 0 : Math.min(1, this.#radiusMm / radialDistance);
    const closestY = this.#center.value.y + dy * radialScale;
    const closestZ = this.#center.value.z + dz * radialScale;

    return millimetres(
      Math.sqrt(squaredDistance(point, clampedX, closestY, closestZ)),
    );
  }
}

/**
 * Small consumer-facing Spatial Query contract.
 *
 * Consumers ask one shared service for patient-space anatomical knowledge.
 * Low-level indexes and specialized query classes remain implementation details
 * of Spatial composition and are not required by downstream packages.
 */
export interface SpatialQueryApi {
  queryPoint(point: PatientSpacePoint): PointQueryResult;
  querySegment(segment: PatientSpaceSegment): readonly PenetrationPathElement[];
  distanceTo(
    point: PatientSpacePoint,
    structureId: StructureId,
  ): DistanceQueryResult;
}

/**
 * Composition input for SpatialQueryService.
 *
 * regions are the authoritative occupancy bindings used by point and ordered
 * segment queries. distanceEntries is optional when one region unambiguously
 * supplies the distance representation for each StructureId. Supplying it is
 * required when a structure has multiple regions or a different distance
 * representation, so the service never guesses which representation to measure.
 */
export interface SpatialQueryServiceConfig {
  readonly regions: readonly SpatialRegionBinding[];
  readonly boundaries?: readonly PenetrationBoundaryBinding[];
  readonly distanceEntries?: readonly SpatialIndexEntry[];
}

const snapshotIndexEntry = <T extends SpatialIndexEntry>(entry: T): T =>
  Object.freeze({
    ...entry,
    membershipRoles: Object.freeze([...entry.membershipRoles]),
  }) as T;

/**
 * Stateless facade over the deterministic Spatial Query capabilities built in
 * TASK-035 through TASK-042. It emits no Interaction events and performs no
 * procedure evaluation or medical-state mutation.
 */
export class SpatialQueryService implements SpatialQueryApi {
  readonly #pointQuery: PointQuery;
  readonly #segmentQuery: OrderedPenetrationPathQuery;
  readonly #distanceQuery: DistanceQuery;

  constructor(config: SpatialQueryServiceConfig) {
    const regions: readonly SpatialRegionBinding[] = Object.freeze(
      config.regions.map((region) => snapshotIndexEntry(region)),
    );
    const distanceEntries: readonly SpatialIndexEntry[] = Object.freeze(
      (config.distanceEntries ?? regions).map((entry) =>
        snapshotIndexEntry(entry),
      ),
    );

    this.#pointQuery = new PointQuery(new BasicSpatialIndex(regions));
    this.#segmentQuery = new OrderedPenetrationPathQuery(
      regions,
      config.boundaries ?? [],
    );
    this.#distanceQuery = new DistanceQuery(distanceEntries);
  }

  queryPoint(point: PatientSpacePoint): PointQueryResult {
    return this.#pointQuery.execute(point);
  }

  querySegment(
    segment: PatientSpaceSegment,
  ): readonly PenetrationPathElement[] {
    return this.#segmentQuery.execute(segment);
  }

  distanceTo(
    point: PatientSpacePoint,
    structureId: StructureId,
  ): DistanceQueryResult {
    return this.#distanceQuery.execute(point, structureId);
  }
}
