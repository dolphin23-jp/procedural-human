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

const initialMedicalStateAccess = Symbol('initialMedicalStateAccess');
const patientRuntimeStateAccess = Symbol('patientRuntimeStateAccess');

const snapshot = (integrity: MedicalIntegrityState): RuntimeMedicalState =>
  Object.freeze({ integrity });

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
  readonly #initialIntegrity: MedicalIntegrityState;

  constructor(descriptor: PatientStructureDescriptor) {
    this.id = descriptor.id;
    this.canonicalEntityId = descriptor.canonicalEntityId;
    this.representationAssetIds = Object.freeze([
      ...descriptor.representationAssetIds,
    ]);
    this.#initialIntegrity = descriptor.initialMedicalState?.integrity ?? 'intact';
    Object.freeze(this);
  }

  [initialMedicalStateAccess](): MedicalIntegrityState {
    return this.#initialIntegrity;
  }
}

class PatientRuntimeState {
  readonly #integrityByStructure: Map<StructureId, MedicalIntegrityState>;

  constructor(structures: readonly PatientStructureInstance[]) {
    this.#integrityByStructure = new Map(
      structures.map((structure) => [
        structure.id,
        structure[initialMedicalStateAccess](),
      ]),
    );
  }

  read(structureId: StructureId): RuntimeMedicalState {
    const integrity = this.#integrityByStructure.get(structureId);
    if (!integrity) {
      throw new Error(`Unknown patient structure: ${structureId}`);
    }
    return snapshot(integrity);
  }

  puncture(structureId: StructureId): StateTransitionResult {
    const previousState = this.read(structureId);
    if (previousState.integrity === 'punctured') {
      return Object.freeze({
        structureId,
        previousState,
        currentState: previousState,
        changed: false,
      });
    }

    this.#integrityByStructure.set(structureId, 'punctured');
    const currentState = this.read(structureId);
    return Object.freeze({
      structureId,
      previousState,
      currentState,
      changed: true,
    });
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
  readonly #runtimeState: PatientRuntimeState;

  constructor(descriptor: PatientInstanceDescriptor) {
    this.id = descriptor.id;
    this.morphology = descriptor.morphology;

    const structures = new Map<StructureId, PatientStructureInstance>();
    for (const structure of descriptor.anatomy.structures) {
      if (structures.has(structure.id)) {
        throw new Error(`Duplicate patient structure id: ${structure.id}`);
      }
      structures.set(structure.id, structure);
    }

    const structureList = Object.freeze([...structures.values()]);
    this.anatomy = Object.freeze({
      canonicalAnatomy: Object.freeze({ ...descriptor.anatomy.canonicalAnatomy }),
      structures: structureList,
    });
    this.#structures = structures;
    this.#runtimeState = new PatientRuntimeState(structureList);
  }

  structure(id: StructureId): PatientStructureInstance | undefined {
    return this.#structures.get(id);
  }

  medicalStateFor(id: StructureId): RuntimeMedicalState {
    return this.#runtimeState.read(id);
  }

  [patientRuntimeStateAccess](): PatientRuntimeState {
    return this.#runtimeState;
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
  readonly #runtimeState: PatientRuntimeState;

  constructor(patient: PatientInstance) {
    this.#runtimeState = patient[patientRuntimeStateAccess]();
  }

  apply(request: StateTransitionRequest): StateTransitionResult {
    return this.#runtimeState.puncture(request.structureId);
  }
}
