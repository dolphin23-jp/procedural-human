/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local Three declarations */
/// <reference path="./three.d.ts" />
import type { AssetId, PatientId, StructureId } from '@procedural-human/core';
import { PatientRenderTransform } from '@procedural-human/rendering-core';
import { Group, Mesh, type Material } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import {
  bindSemanticObjects,
  unbindSemanticMeshes,
  type SemanticRenderIdentity,
  ThreeSemanticContext,
} from './semantic-context.js';
import { patientToThreeMatrix } from './three-coordinates.js';

export interface GlbSemanticBinding {
  readonly renderBindingKey: string;
  readonly structureId: StructureId;
}

export interface GlbRuntimeAssetDescriptor {
  readonly assetId: AssetId;
  readonly patientId: PatientId;
  /** TASK-048 accepts only geometry authored in Patient Space millimetres. */
  readonly coordinateSpace: 'patient-mm';
  readonly bindings: readonly GlbSemanticBinding[];
}

export interface ThreeLoadedRenderAssetSummary {
  readonly assetId: AssetId;
  readonly structureIds: readonly StructureId[];
  readonly meshCount: number;
}

export interface ThreeLoadedRenderAsset {
  readonly assetId: AssetId;
  semanticIdentities(): readonly SemanticRenderIdentity[];
  summary(): ThreeLoadedRenderAssetSummary;
  dispose(): void;
}

interface LoadedState {
  readonly root: Group;
  readonly context: ThreeSemanticContext;
  readonly boundMeshes: readonly Mesh[];
  disposed: boolean;
}

const loadedStates = new WeakMap<ThreeLoadedRenderAssetImpl, LoadedState>();

class ThreeLoadedRenderAssetImpl implements ThreeLoadedRenderAsset {
  readonly assetId: AssetId;
  readonly #identities: readonly SemanticRenderIdentity[];
  readonly #structureIds: readonly StructureId[];
  readonly #meshCount: number;

  constructor(
    assetId: AssetId,
    identities: readonly SemanticRenderIdentity[],
    structureIds: readonly StructureId[],
    meshCount: number,
  ) {
    this.assetId = assetId;
    this.#identities = Object.freeze([...identities]);
    this.#structureIds = Object.freeze([...structureIds]);
    this.#meshCount = meshCount;
  }

  semanticIdentities(): readonly SemanticRenderIdentity[] {
    return this.#identities;
  }

  summary(): ThreeLoadedRenderAssetSummary {
    return Object.freeze({
      assetId: this.assetId,
      structureIds: this.#structureIds,
      meshCount: this.#meshCount,
    });
  }

  dispose(): void {
    const state = loadedStates.get(this);
    if (!state || state.disposed) return;
    unbindSemanticMeshes(state.context, state.boundMeshes);

    const geometries = new Set<{ dispose(): void }>();
    const materials = new Set<Material>();
    state.root.traverse((object) => {
      if (!(object instanceof Mesh)) return;
      geometries.add(object.geometry);
      const meshMaterials = Array.isArray(object.material)
        ? object.material
        : [object.material];
      for (const material of meshMaterials) materials.add(material);
    });
    for (const geometry of geometries) geometry.dispose();
    for (const material of materials) material.dispose();
    state.root.parent?.remove(state.root);
    state.disposed = true;
  }
}

function createLoadedAsset(
  assetId: AssetId,
  root: Group,
  context: ThreeSemanticContext,
  identities: readonly SemanticRenderIdentity[],
  structureIds: readonly StructureId[],
  boundMeshes: readonly Mesh[],
): ThreeLoadedRenderAsset {
  const asset = new ThreeLoadedRenderAssetImpl(
    assetId,
    identities,
    structureIds,
    boundMeshes.length,
  );
  loadedStates.set(asset, {
    root,
    context,
    boundMeshes: Object.freeze([...boundMeshes]),
    disposed: false,
  });
  return asset;
}

export function loadedAssetGroupFor(asset: ThreeLoadedRenderAsset): Group {
  if (!(asset instanceof ThreeLoadedRenderAssetImpl)) {
    throw new TypeError('Asset was not created by ThreeGlbRuntimeLoader.');
  }
  const state = loadedStates.get(asset);
  if (!state || state.disposed) throw new Error('Loaded GLB asset is disposed.');
  return state.root;
}

function validateDescriptor(
  descriptor: GlbRuntimeAssetDescriptor,
  context: ThreeSemanticContext,
): ReadonlyMap<string, GlbSemanticBinding> {
  if (!descriptor) throw new TypeError('GLB runtime asset descriptor is required.');
  if (descriptor.patientId !== context.patientId) {
    throw new Error(
      `GLB patient binding mismatch: expected ${context.patientId}, received ${descriptor.patientId}.`,
    );
  }
  if (descriptor.coordinateSpace !== 'patient-mm') {
    throw new Error(
      'GLB coordinateSpace must explicitly be "patient-mm" for TASK-048.',
    );
  }
  if (!Array.isArray(descriptor.bindings) || descriptor.bindings.length === 0) {
    throw new Error('GLB requires at least one explicit semantic binding.');
  }
  const byKey = new Map<string, GlbSemanticBinding>();
  for (const binding of descriptor.bindings) {
    const key = binding.renderBindingKey;
    if (typeof key !== 'string' || key.trim().length === 0) {
      throw new TypeError('GLB renderBindingKey must be a non-empty string.');
    }
    if (byKey.has(key)) {
      throw new Error(`Duplicate GLB renderBindingKey: ${key}`);
    }
    context.identityFor(binding.structureId);
    byKey.set(key, binding);
  }
  return byKey;
}

export class ThreeGlbRuntimeLoader {
  readonly #context: ThreeSemanticContext;
  readonly #coordinates: PatientRenderTransform;
  readonly #loader = new GLTFLoader();

  constructor(
    context: ThreeSemanticContext,
    coordinates: PatientRenderTransform,
  ) {
    if (!(context instanceof ThreeSemanticContext)) {
      throw new TypeError('Explicit ThreeSemanticContext is required.');
    }
    if (!(coordinates instanceof PatientRenderTransform)) {
      throw new TypeError('Explicit PatientRenderTransform is required.');
    }
    this.#context = context;
    this.#coordinates = coordinates;
  }

  async loadFromUrl(
    url: string,
    descriptor: GlbRuntimeAssetDescriptor,
  ): Promise<ThreeLoadedRenderAsset> {
    if (typeof url !== 'string' || url.trim().length === 0) {
      throw new TypeError('GLB URL must be a non-empty string.');
    }
    const bindings = validateDescriptor(descriptor, this.#context);
    const gltf = await this.#loader.loadAsync(url);
    return this.#bindScene(gltf.scene, descriptor, bindings);
  }

  async loadFromArrayBuffer(
    data: ArrayBuffer,
    descriptor: GlbRuntimeAssetDescriptor,
    resourcePath = '',
  ): Promise<ThreeLoadedRenderAsset> {
    if (!(data instanceof ArrayBuffer)) {
      throw new TypeError('GLB data must be an ArrayBuffer.');
    }
    const bindings = validateDescriptor(descriptor, this.#context);
    const gltf = await this.#loader.parseAsync(data, resourcePath);
    return this.#bindScene(gltf.scene, descriptor, bindings);
  }

  #bindScene(
    scene: Group,
    descriptor: GlbRuntimeAssetDescriptor,
    bindings: ReadonlyMap<string, GlbSemanticBinding>,
  ): ThreeLoadedRenderAsset {
    const objectsByKey = new Map<string, Group[] | Mesh[]>();
    scene.traverse((object) => {
      const rawKey = object.userData.renderBindingKey;
      if (rawKey === undefined) return;
      if (typeof rawKey !== 'string' || rawKey.trim().length === 0) {
        throw new TypeError('GLB extras.renderBindingKey must be a non-empty string.');
      }
      if (!bindings.has(rawKey)) {
        throw new Error(
          `GLB declares unbound renderBindingKey "${rawKey}"; mesh/node names are never used as fallback identity.`,
        );
      }
      const existing = objectsByKey.get(rawKey);
      if (existing) {
        (existing as (Group | Mesh)[]).push(object as Group | Mesh);
      } else {
        objectsByKey.set(rawKey, [object as Group | Mesh]);
      }
    });

    const identities: SemanticRenderIdentity[] = [];
    const structureIds: StructureId[] = [];
    const boundMeshes: Mesh[] = [];
    try {
      for (const [key, binding] of bindings) {
        const objects = objectsByKey.get(key);
        if (!objects || objects.length === 0) {
          throw new Error(
            `GLB is missing explicit renderBindingKey "${key}" for ${binding.structureId}.`,
          );
        }
        const result = bindSemanticObjects(
          this.#context,
          binding.structureId,
          objects,
        );
        identities.push(result.identity);
        structureIds.push(binding.structureId);
        boundMeshes.push(...result.meshes);
      }
    } catch (error) {
      unbindSemanticMeshes(this.#context, boundMeshes);
      throw error;
    }

    const root = new Group();
    root.name = `GLB derived render asset: ${descriptor.assetId}`;
    root.matrixAutoUpdate = false;
    root.matrix.copy(patientToThreeMatrix(this.#coordinates));
    root.add(scene);
    return createLoadedAsset(
      descriptor.assetId,
      root,
      this.#context,
      identities,
      structureIds,
      boundMeshes,
    );
  }
}
