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

export interface SpatialIndexEntry {
  readonly structureId: StructureId;
  readonly canonicalEntityId: EntityId;
  readonly name: string;
  readonly membershipRoles: readonly SpatialMembershipRole[];
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

export interface PointQueryResult {
  readonly structures: readonly SpatialMatch[];
  readonly tissues: readonly SpatialMatch[];
  readonly lumens: readonly SpatialMatch[];
}

const matchFor = (entry: SpatialIndexEntry): SpatialMatch =>
  Object.freeze({
    structureId: entry.structureId,
    canonicalEntityId: entry.canonicalEntityId,
    name: entry.name,
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
      .map(matchFor);

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

export interface AxisAlignedBoxDescriptor {
  readonly center: PatientSpacePoint;
  readonly size: readonly [Length, Length, Length];
}

export class AxisAlignedBoxSpatialAdapter
  implements BoundedSpatialRepresentationAdapter
{
  readonly bounds: PatientSpaceBoundingBox;

  constructor(descriptor: AxisAlignedBoxDescriptor) {
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
  }

  containsPoint(point: PatientSpacePoint): boolean {
    return pointInBounds(point, this.bounds);
  }

  intersectSegment(segment: PatientSpaceSegment): readonly PatientSpacePoint[] {
    let near = 0;
    let far = 1;

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

    const parameters: number[] = [];
    const startInside = this.containsPoint(segment.start);
    const endInside = this.containsPoint(segment.end);
    if (!startInside && near >= 0 && near <= 1) {
      parameters.push(near);
    }
    if (!endInside && far >= 0 && far <= 1 && far !== near) {
      parameters.push(far);
    }

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
  implements BoundedSpatialRepresentationAdapter
{
  readonly #center: PatientSpacePoint;
  readonly #radiusMm: number;
  readonly #halfLengthMm: number;
  readonly bounds: PatientSpaceBoundingBox;

  constructor(descriptor: XAxisCylinderDescriptor) {
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
