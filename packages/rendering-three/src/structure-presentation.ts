import type {
  StructureOpacity,
  StructureSelection,
  StructureVisibility,
} from '@procedural-human/rendering-core';
import type { Material, Mesh } from 'three';
import { semanticMeshesFor, ThreeSemanticContext } from './semantic-context.js';

interface MaterialSnapshot {
  readonly original: Material | Material[];
  readonly owned: readonly Material[];
}

export class ThreeStructurePresentation {
  readonly #context: ThreeSemanticContext;
  readonly #materialSnapshots = new Map<Mesh, MaterialSnapshot>();
  #selection: StructureSelection = null;
  #disposed = false;

  constructor(context: ThreeSemanticContext) {
    if (!(context instanceof ThreeSemanticContext)) {
      throw new TypeError('Explicit ThreeSemanticContext is required.');
    }
    this.#context = context;
  }

  setVisibility(visibility: StructureVisibility): void {
    this.#assertActive();
    if (!visibility || typeof visibility.visible !== 'boolean') {
      throw new TypeError('Structure visibility requires an explicit boolean.');
    }
    this.#context.identityFor(visibility.structureId);
    const meshes = semanticMeshesFor(this.#context, visibility.structureId);
    for (const mesh of meshes) mesh.visible = visibility.visible;
  }

  setOpacity(request: StructureOpacity): void {
    this.#assertActive();
    if (
      !request ||
      !Number.isFinite(request.opacity) ||
      request.opacity < 0 ||
      request.opacity > 1
    ) {
      throw new RangeError('Structure opacity must be finite and between 0 and 1.');
    }
    this.#context.identityFor(request.structureId);
    const meshes = semanticMeshesFor(this.#context, request.structureId);
    for (const mesh of meshes) {
      const materials = this.#ownedMaterials(mesh);
      for (const material of materials) {
        material.opacity = request.opacity;
        material.transparent = request.opacity < 1;
        material.depthWrite = request.opacity === 1;
        material.needsUpdate = true;
      }
    }
  }

  setSelection(selection: StructureSelection): void {
    this.#assertActive();
    if (selection !== null) this.#context.identityFor(selection);
    this.#selection = selection;
  }

  selection(): StructureSelection {
    return this.#selection;
  }

  dispose(): void {
    if (this.#disposed) return;
    for (const [mesh, snapshot] of this.#materialSnapshots) {
      mesh.material = snapshot.original;
      for (const material of snapshot.owned) material.dispose();
    }
    this.#materialSnapshots.clear();
    this.#disposed = true;
  }

  #ownedMaterials(mesh: Mesh): readonly Material[] {
    const existing = this.#materialSnapshots.get(mesh);
    if (existing) return existing.owned;
    const original = mesh.material;
    const sources = Array.isArray(original) ? original : [original];
    const owned = Object.freeze(sources.map((material) => material.clone()));
    mesh.material = Array.isArray(original) ? [...owned] : owned[0]!;
    this.#materialSnapshots.set(mesh, { original, owned });
    return owned;
  }

  #assertActive(): void {
    if (this.#disposed) throw new Error('ThreeStructurePresentation is disposed.');
  }
}
