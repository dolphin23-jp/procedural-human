import { AnatomicalGraph, type AnatomicalEntity } from '@procedural-human/anatomy';
import {
  assetId,
  contentHash,
  entityId,
  patientId,
  version,
} from '@procedural-human/core';
import {
  PatientInstance,
  PatientStructureInstance,
} from '@procedural-human/patient';
import { ThreeSemanticContext } from './semantic-context.js';
import { FIXTURE_STRUCTURE_IDS } from './fixture-ids.js';

export const FIXTURE_RENDER_ASSET_ID = assetId(
  'asset.fixture.synthetic-anatomy-v1.render',
);

const fixtureHash = contentHash(
  '73341e50ca931296a5bc33a20f02cd3c5308642bc7f887d2fed8d389d4230a6d',
);

const accuracy = Object.freeze({
  identityAccuracy: null,
  topologyAccuracy: null,
  geometryAccuracy: null,
  registrationAccuracy: null,
  diameterAccuracy: null,
  relationshipAccuracy: null,
});

function fixtureEntity(
  id: string,
  name: string,
  type: string,
): AnatomicalEntity {
  return Object.freeze({
    id: entityId(id),
    name,
    type,
    laterality: 'not-applicable',
    region: 'synthetic-anatomy-v1',
    relationships: Object.freeze([]),
    representations: Object.freeze([
      Object.freeze({
        kind: 'renderSurface' as const,
        assetId: FIXTURE_RENDER_ASSET_ID,
      }),
    ]),
    provenance: Object.freeze({
      sourceClass: 'development-fixture',
      sourceIdentifier: 'synthetic-anatomy-v1',
      derivationMethod:
        'hand-authored primitive/GLB geometry for software testing',
      contentHash: fixtureHash,
    }),
    accuracy,
    validation: Object.freeze({
      level: 'V0',
      notes: 'Non-medical development fixture; not educational anatomy.',
    }),
  });
}

export function createFixtureSemanticContext(): ThreeSemanticContext {
  const entities = [
    fixtureEntity('entity.fixture.skin', 'Fixture Skin', 'fixture-tissue'),
    fixtureEntity(
      'entity.fixture.soft-tissue',
      'Fixture Soft Tissue',
      'fixture-tissue',
    ),
    fixtureEntity('entity.fixture.vein', 'Fixture Vein', 'fixture-vessel'),
    fixtureEntity('entity.fixture.artery', 'Fixture Artery', 'fixture-vessel'),
  ] as const;
  const anatomy = new AnatomicalGraph(entities);
  const structures = [
    new PatientStructureInstance({
      id: FIXTURE_STRUCTURE_IDS.skin,
      canonicalEntityId: entities[0].id,
      representationAssetIds: [FIXTURE_RENDER_ASSET_ID],
    }),
    new PatientStructureInstance({
      id: FIXTURE_STRUCTURE_IDS.softTissue,
      canonicalEntityId: entities[1].id,
      representationAssetIds: [FIXTURE_RENDER_ASSET_ID],
    }),
    new PatientStructureInstance({
      id: FIXTURE_STRUCTURE_IDS.vein,
      canonicalEntityId: entities[2].id,
      representationAssetIds: [FIXTURE_RENDER_ASSET_ID],
    }),
    new PatientStructureInstance({
      id: FIXTURE_STRUCTURE_IDS.artery,
      canonicalEntityId: entities[3].id,
      representationAssetIds: [FIXTURE_RENDER_ASSET_ID],
    }),
  ] as const;
  const patient = new PatientInstance({
    id: patientId('patient.fixture.synthetic-anatomy-v1'),
    morphology: { mode: 'static' },
    anatomy: {
      canonicalAnatomy: {
        assetId: FIXTURE_RENDER_ASSET_ID,
        version: version('1'),
        contentHash: fixtureHash,
      },
      structures,
    },
  });
  return new ThreeSemanticContext(patient, anatomy);
}
