import type { StructureId } from '@procedural-human/core';
import type { PatientSpacePoint } from '@procedural-human/math';
import { millimetres, toMillimetres, type Length } from '@procedural-human/units';
import type { SpatialIndexEntry } from './index.js';

export interface DistanceQueryResult {
  readonly structureId: SpatialIndexEntry['structureId'];
  readonly canonicalEntityId: SpatialIndexEntry['canonicalEntityId'];
  readonly name: string;
  /** Unsigned distance to the bound spatial representation. */
  readonly distance: Length;
}

export class DistanceQueryFailure extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DistanceQueryFailure';
  }
}

const axes = ['x', 'y', 'z'] as const;

const assertPatientPoint = (point: PatientSpacePoint): void => {
  if (
    point.space !== 'patient' ||
    point.kind !== 'point' ||
    !axes.every((axis) => Number.isFinite(point.value[axis]))
  ) {
    throw new DistanceQueryFailure(
      'Expected finite patient-space coordinates in millimetres',
    );
  }
};

/**
 * Stateless distance query for an explicitly identified patient structure.
 *
 * The query delegates geometry to the structure's bound representation and
 * preserves semantic identity. It does not infer targets from names, choose a
 * nearest structure, assign boundary semantics, or produce signed distance.
 */
export class DistanceQuery {
  readonly #entriesByStructure: ReadonlyMap<StructureId, SpatialIndexEntry>;

  constructor(entries: readonly SpatialIndexEntry[]) {
    const byStructure = new Map<StructureId, SpatialIndexEntry>();
    for (const entry of entries) {
      if (byStructure.has(entry.structureId)) {
        throw new DistanceQueryFailure(
          `Duplicate structure binding: ${entry.structureId}`,
        );
      }
      byStructure.set(entry.structureId, entry);
    }
    this.#entriesByStructure = byStructure;
  }

  execute(
    point: PatientSpacePoint,
    structureId: StructureId,
  ): DistanceQueryResult {
    assertPatientPoint(point);
    const entry = this.#entriesByStructure.get(structureId);
    if (!entry) {
      throw new DistanceQueryFailure(`Unknown structure: ${structureId}`);
    }

    const distanceMm = toMillimetres(entry.representation.distanceToPoint(point));
    if (!Number.isFinite(distanceMm) || distanceMm < 0) {
      throw new DistanceQueryFailure(
        `Representation returned invalid distance for ${structureId}`,
      );
    }

    return Object.freeze({
      structureId: entry.structureId,
      canonicalEntityId: entry.canonicalEntityId,
      name: entry.name,
      distance: millimetres(distanceMm),
    });
  }
}
