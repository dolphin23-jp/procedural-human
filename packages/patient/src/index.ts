import type {
  AssetId,
  ContentHash,
  EntityId,
  PatientId,
  StructureId,
  Version,
} from '@procedural-human/core';

export interface CanonicalAnatomyReference {
  readonly assetId: AssetId;
  readonly version: Version;
  readonly contentHash: ContentHash;
}

export interface PatientMorphology {
  readonly mode: 'static';
}

export type MedicalIntegrityState = 'intact' | 'punctured';

export interface RuntimeMedicalState {
  readonly integrity: MedicalIntegrityState;
}

const structureState = new WeakMap<PatientStructureInstance, RuntimeMedicalState>();

export interface PatientStructureDescriptor {
  readonly id: StructureId;
  readonly canonicalEntityId: EntityId;
  readonly representationAssetIds: readonly AssetId[];
  readonly initialMedicalState?: RuntimeMedicalState;
}

export class PatientStructureInstance {
  readonly id: StructureId;
  readonly canonicalEntityId: EntityId;
  readonly representationAssetIds: readonly AssetId[];

  constructor(descriptor: PatientStructureDescriptor) {
    this.id = descriptor.id;
    this.canonicalEntityId = descriptor.canonicalEntityId;
    this.representationAssetIds = [...descriptor.representationAssetIds];
    structureState.set(
      this,
      descriptor.initialMedicalState ?? { integrity: 'intact' },
    );
  }

  get medicalState(): RuntimeMedicalState {
    const state = structureState.get(this);
    if (!state) {
      throw new Error(`Missing medical state for structure: ${this.id}`);
    }
    return state;
  }
}

export interface PatientAnatomy {
  readonly canonicalAnatomy: CanonicalAnatomyReference;
  readonly structures: readonly PatientStructureInstance[];
}

export interface PatientInstanceDescriptor {
  readonly id: PatientId;
  readonly morphology: PatientMorphology;
  readonly anatomy: PatientAnatomy;
}

export class PatientInstance {
  readonly id: PatientId;
  readonly morphology: PatientMorphology;
  readonly anatomy: PatientAnatomy;
  readonly #structures: ReadonlyMap<StructureId, PatientStructureInstance>;

  constructor(descriptor: PatientInstanceDescriptor) {
    this.id = descriptor.id;
    this.morphology = descriptor.morphology;
    this.anatomy = {
      canonicalAnatomy: descriptor.anatomy.canonicalAnatomy,
      structures: [...descriptor.anatomy.structures],
    };

    const structures = new Map<StructureId, PatientStructureInstance>();
    for (const structure of this.anatomy.structures) {
      if (structures.has(structure.id)) {
        throw new Error(`Duplicate patient structure id: ${structure.id}`);
      }
      structures.set(structure.id, structure);
    }
    this.#structures = structures;
  }

  structure(id: StructureId): PatientStructureInstance | undefined {
    return this.#structures.get(id);
  }
}

export interface StateTransitionRequest {
  readonly structureId: StructureId;
  readonly transition: 'puncture';
}

export interface StateTransitionResult {
  readonly structureId: StructureId;
  readonly previousState: RuntimeMedicalState;
  readonly currentState: RuntimeMedicalState;
  readonly changed: boolean;
}

export class PatientStateTransitionService {
  readonly #patient: PatientInstance;

  constructor(patient: PatientInstance) {
    this.#patient = patient;
  }

  apply(request: StateTransitionRequest): StateTransitionResult {
    const structure = this.#patient.structure(request.structureId);
    if (!structure) {
      throw new Error(`Unknown patient structure: ${request.structureId}`);
    }

    const previousState = structure.medicalState;
    if (request.transition === 'puncture') {
      if (previousState.integrity === 'punctured') {
        return {
          structureId: structure.id,
          previousState,
          currentState: previousState,
          changed: false,
        };
      }

      const currentState: RuntimeMedicalState = { integrity: 'punctured' };
      structureState.set(structure, currentState);
      return {
        structureId: structure.id,
        previousState,
        currentState,
        changed: true,
      };
    }
  }
}
