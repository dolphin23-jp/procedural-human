import type { AssetId, ContentHash, EntityId } from '@procedural-human/core';

export type Laterality =
  | 'left'
  | 'right'
  | 'bilateral'
  | 'midline'
  | 'not-applicable'
  | 'unknown';

export type AnatomicalRelationshipType =
  | 'part_of'
  | 'branch_of'
  | 'adjacent_to'
  | 'connected_to';

export interface AnatomicalRelationship {
  readonly type: AnatomicalRelationshipType;
  readonly targetId: EntityId;
}

export type SourceClass =
  | 'acquired'
  | 'cadaver-derived'
  | 'atlas-derived'
  | 'literature-derived'
  | 'algorithm-derived'
  | 'human-edited'
  | 'ai-inferred'
  | 'synthetic'
  | 'development-fixture';

export type ValidationLevel = 'V0' | 'V1' | 'V2' | 'V3' | 'V4';

export interface ValidationStatus {
  readonly level: ValidationLevel;
  readonly notes: string | null;
}

export interface Provenance {
  readonly sourceClass: SourceClass;
  readonly sourceIdentifier: string | null;
  readonly derivationMethod: string | null;
  readonly contentHash: ContentHash | null;
}

export interface AccuracyProfile {
  readonly identityAccuracy: string | null;
  readonly topologyAccuracy: string | null;
  readonly geometryAccuracy: string | null;
  readonly registrationAccuracy: string | null;
  readonly diameterAccuracy: string | null;
  readonly relationshipAccuracy: string | null;
}

export type RepresentationKind =
  | 'renderSurface'
  | 'collisionSurface'
  | 'segmentationVolume'
  | 'lumenVolume'
  | 'centerline';

export interface RepresentationDescriptor {
  readonly kind: RepresentationKind;
  readonly assetId: AssetId;
}

export type RepresentationBundle = readonly RepresentationDescriptor[];

export interface AnatomicalEntity {
  readonly id: EntityId;
  readonly name: string;
  readonly type: string;
  readonly laterality: Laterality;
  readonly region: string;
  readonly relationships: readonly AnatomicalRelationship[];
  readonly representations: RepresentationBundle;
  readonly provenance: Provenance;
  readonly accuracy: AccuracyProfile;
  readonly validation: ValidationStatus;
}

declare const provisionalBoundaryRegionReferenceBrand: unique symbol;

/**
 * TASK-028-only reference for the two named regions a boundary separates.
 * It intentionally carries no inside/outside, lumen, traversal, or entry/exit
 * semantics. Spatial interpretation remains owned by later Spatial Query tasks.
 */
export type ProvisionalBoundaryRegionReference = string & {
  readonly [provisionalBoundaryRegionReferenceBrand]: 'ProvisionalBoundaryRegionReference';
};

export const provisionalBoundaryRegionReference = (
  value: string,
): ProvisionalBoundaryRegionReference => value as ProvisionalBoundaryRegionReference;

export interface BoundaryEntity {
  readonly id: EntityId;
  readonly name: string;
  readonly separates: readonly [
    ProvisionalBoundaryRegionReference,
    ProvisionalBoundaryRegionReference,
  ];
  readonly provenance: Provenance;
  readonly accuracy: AccuracyProfile;
  readonly validation: ValidationStatus;
}

export class AnatomicalGraph {
  readonly #entities: ReadonlyMap<EntityId, AnatomicalEntity>;

  constructor(entities: readonly AnatomicalEntity[]) {
    const byId = new Map<EntityId, AnatomicalEntity>();
    for (const entity of entities) {
      if (byId.has(entity.id)) {
        throw new Error(`Duplicate anatomical entity id: ${entity.id}`);
      }
      byId.set(entity.id, entity);
    }
    this.#entities = byId;
  }

  get(id: EntityId): AnatomicalEntity | undefined {
    return this.#entities.get(id);
  }

  has(id: EntityId): boolean {
    return this.#entities.has(id);
  }

  relatedFrom(
    id: EntityId,
    type?: AnatomicalRelationshipType,
  ): readonly AnatomicalRelationship[] {
    const entity = this.#entities.get(id);
    if (!entity) {
      return [];
    }
    return type
      ? entity.relationships.filter(
          (relationship) => relationship.type === type,
        )
      : entity.relationships;
  }

  relatedEntitiesFrom(
    id: EntityId,
    type?: AnatomicalRelationshipType,
  ): readonly AnatomicalEntity[] {
    return this.relatedFrom(id, type)
      .map((relationship) => this.#entities.get(relationship.targetId))
      .filter((entity): entity is AnatomicalEntity => entity !== undefined);
  }
}

export const createRepresentationBundle = (
  descriptors: readonly RepresentationDescriptor[],
): RepresentationBundle => {
  const seen = new Set<RepresentationKind>();
  for (const descriptor of descriptors) {
    if (seen.has(descriptor.kind)) {
      throw new Error(`Duplicate representation kind: ${descriptor.kind}`);
    }
    seen.add(descriptor.kind);
  }
  return [...descriptors];
};
