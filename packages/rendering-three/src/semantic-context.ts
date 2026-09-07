/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local Three declarations */
/// <reference path="./three.d.ts" />
import type {
  AnatomicalEntity,
  AnatomicalGraph,
} from '@procedural-human/anatomy';
import type { PatientId, StructureId } from '@procedural-human/core';
import type {
  PatientInstance,
  PatientStructureInstance,
} from '@procedural-human/patient';
import { Mesh, type Object3D } from 'three';

export interface SemanticRenderIdentity {
  readonly patientStructure: PatientStructureInstance;
  readonly anatomicalEntity: AnatomicalEntity;
}

interface BoundEntry {
  readonly identity: SemanticRenderIdentity;
  readonly meshes: Set<Mesh>;
}

interface InternalSemanticRegistry {
  readonly byStructure: Map<StructureId, BoundEntry>;
  readonly byMesh: WeakMap<Mesh, SemanticRenderIdentity>;
}

const registries = new WeakMap<
  ThreeSemanticContext,
  InternalSemanticRegistry
>();

export class ThreeSemanticContext {
  readonly patientId: PatientId;
  readonly #patient: PatientInstance;
  readonly #anatomy: AnatomicalGraph;
  readonly #identities = new Map<StructureId, SemanticRenderIdentity>();

  constructor(patient: PatientInstance, anatomy: AnatomicalGraph) {
    if (!patient || !anatomy) {
      throw new TypeError('PatientInstance and AnatomicalGraph are required.');
    }
    this.patientId = patient.id;
    this.#patient = patient;
    this.#anatomy = anatomy;
    registries.set(this, {
      byStructure: new Map(),
      byMesh: new WeakMap(),
    });
  }

  identityFor(structureId: StructureId): SemanticRenderIdentity {
    const cached = this.#identities.get(structureId);
    if (cached) return cached;
    const patientStructure = this.#patient.structure(structureId);
    if (!patientStructure) {
      throw new Error(`Unknown patient structure: ${structureId}`);
    }
    const anatomicalEntity = this.#anatomy.get(
      patientStructure.canonicalEntityId,
    );
    if (!anatomicalEntity) {
      throw new Error(
        `Missing canonical anatomical entity: ${patientStructure.canonicalEntityId}`,
      );
    }
    const identity = Object.freeze({ patientStructure, anatomicalEntity });
    this.#identities.set(structureId, identity);
    return identity;
  }

  patientStructureIds(): readonly StructureId[] {
    return Object.freeze(
      this.#patient.anatomy.structures.map((structure) => structure.id),
    );
  }
}

function registry(context: ThreeSemanticContext): InternalSemanticRegistry {
  const value = registries.get(context);
  if (!value) throw new Error('Semantic context registry is unavailable.');
  return value;
}

function collectMeshes(objects: readonly Object3D[]): Mesh[] {
  const meshes: Mesh[] = [];
  const seen = new Set<Mesh>();
  for (const object of objects) {
    object.traverse((candidate) => {
      if (candidate instanceof Mesh && !seen.has(candidate)) {
        seen.add(candidate);
        meshes.push(candidate);
      }
    });
  }
  return meshes;
}

export function bindSemanticObjects(
  context: ThreeSemanticContext,
  structureId: StructureId,
  objects: readonly Object3D[],
): {
  readonly identity: SemanticRenderIdentity;
  readonly meshes: readonly Mesh[];
} {
  const identity = context.identityFor(structureId);
  const meshes = collectMeshes(objects);
  if (meshes.length === 0) {
    throw new Error(`Semantic binding for ${structureId} contains no mesh.`);
  }
  const state = registry(context);
  let entry = state.byStructure.get(structureId);
  if (!entry) {
    entry = { identity, meshes: new Set() };
    state.byStructure.set(structureId, entry);
  }

  for (const mesh of meshes) {
    const existing = state.byMesh.get(mesh);
    if (existing && existing.patientStructure.id !== structureId) {
      throw new Error(
        `Render mesh is already bound to ${existing.patientStructure.id}; cannot bind ${structureId}.`,
      );
    }
    state.byMesh.set(mesh, identity);
    entry.meshes.add(mesh);
  }
  return Object.freeze({ identity, meshes: Object.freeze([...meshes]) });
}

export function unbindSemanticMeshes(
  context: ThreeSemanticContext,
  meshes: readonly Mesh[],
): void {
  const state = registry(context);
  for (const mesh of meshes) {
    const identity = state.byMesh.get(mesh);
    if (!identity) continue;
    state.byMesh.delete(mesh);
    const entry = state.byStructure.get(identity.patientStructure.id);
    entry?.meshes.delete(mesh);
    if (entry && entry.meshes.size === 0) {
      state.byStructure.delete(identity.patientStructure.id);
    }
  }
}

export function semanticMeshesFor(
  context: ThreeSemanticContext,
  structureId: StructureId,
): readonly Mesh[] {
  const entry = registry(context).byStructure.get(structureId);
  if (!entry)
    throw new Error(`No render representation bound for ${structureId}.`);
  return Object.freeze([...entry.meshes]);
}

export function allSemanticMeshes(
  context: ThreeSemanticContext,
): readonly Mesh[] {
  const result: Mesh[] = [];
  for (const entry of registry(context).byStructure.values()) {
    result.push(...entry.meshes);
  }
  return Object.freeze(result);
}

export function resolveSemanticObject(
  context: ThreeSemanticContext,
  object: Object3D,
): SemanticRenderIdentity | null {
  if (!(object instanceof Mesh)) return null;
  return registry(context).byMesh.get(object) ?? null;
}
