import type { StructureVisibility } from '@procedural-human/rendering-core';
import { semanticMeshesFor, ThreeSemanticContext } from './semantic-context.js';

export class ThreeStructurePresentation {
  readonly #context: ThreeSemanticContext;

  constructor(context: ThreeSemanticContext) {
    if (!(context instanceof ThreeSemanticContext)) {
      throw new TypeError('Explicit ThreeSemanticContext is required.');
    }
    this.#context = context;
  }

  setVisibility(visibility: StructureVisibility): void {
    if (!visibility || typeof visibility.visible !== 'boolean') {
      throw new TypeError('Structure visibility requires an explicit boolean.');
    }
    this.#context.identityFor(visibility.structureId);
    const meshes = semanticMeshesFor(this.#context, visibility.structureId);
    for (const mesh of meshes) mesh.visible = visibility.visible;
  }
}
