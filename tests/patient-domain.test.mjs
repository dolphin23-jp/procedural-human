import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  assetId,
  contentHash,
  entityId,
  patientId,
  structureId,
  version,
} from '../packages/core/dist/index.js';
import { StaticUnavailablePhysiology } from '../packages/physiology/dist/index.js';
import {
  PatientInstance,
  PatientStateTransitionService,
  PatientStructureInstance,
} from '../packages/patient/dist/index.js';
import { patientSpacePoint } from '../packages/math/dist/index.js';

const hash = contentHash(`sha256:${'0'.repeat(64)}`);

const makeVein = () =>
  new PatientStructureInstance({
    id: structureId('structure.fixture.vein'),
    canonicalEntityId: entityId('entity.fixture.vein'),
    representationAssetIds: [assetId('asset.fixture.vein')],
  });

const makePatientFromStructures = (id, structures) =>
  new PatientInstance({
    id: patientId(id),
    morphology: { mode: 'static' },
    anatomy: {
      canonicalAnatomy: {
        assetId: assetId('asset.fixture.anatomy'),
        version: version('1'),
        contentHash: hash,
      },
      structures,
    },
  });

const makePatient = (id = 'patient.fixture') => {
  const vein = makeVein();
  return {
    vein,
    patient: makePatientFromStructures(id, [vein]),
  };
};

test('two PatientInstance objects own isolated runtime medical state', () => {
  const sharedStructureDefinition = makeVein();
  const firstPatient = makePatientFromStructures('patient.fixture.first', [
    sharedStructureDefinition,
  ]);
  const secondPatient = makePatientFromStructures('patient.fixture.second', [
    sharedStructureDefinition,
  ]);

  const transitions = new PatientStateTransitionService(firstPatient);
  transitions.apply({
    structureId: sharedStructureDefinition.id,
    transition: 'puncture',
  });

  assert.deepEqual(firstPatient.medicalStateFor(sharedStructureDefinition.id), {
    integrity: 'punctured',
  });
  assert.deepEqual(
    secondPatient.medicalStateFor(sharedStructureDefinition.id),
    {
      integrity: 'intact',
    },
  );
});

test('runtime medical state reads are immutable snapshots', () => {
  const { patient, vein } = makePatient();
  const returnedState = patient.medicalStateFor(vein.id);

  assert.equal(Object.isFrozen(returnedState), true);
  assert.throws(() => {
    returnedState.integrity = 'punctured';
  }, TypeError);
  assert.deepEqual(patient.medicalStateFor(vein.id), { integrity: 'intact' });
});

test('puncture state changes only through PatientStateTransitionService', () => {
  const { patient, vein } = makePatient();

  assert.equal('medicalState' in vein, false);
  assert.equal(Object.isFrozen(vein), true);
  assert.throws(() => {
    vein.medicalState = { integrity: 'punctured' };
  }, TypeError);
  assert.deepEqual(patient.medicalStateFor(vein.id), { integrity: 'intact' });

  const transitions = new PatientStateTransitionService(patient);
  const result = transitions.apply({
    structureId: vein.id,
    transition: 'puncture',
  });

  assert.equal(result.changed, true);
  assert.deepEqual(patient.medicalStateFor(vein.id), {
    integrity: 'punctured',
  });
});

test('repeated puncture remains deterministic and idempotent', () => {
  const { patient, vein } = makePatient();
  const transitions = new PatientStateTransitionService(patient);

  const first = transitions.apply({
    structureId: vein.id,
    transition: 'puncture',
  });
  assert.equal(first.changed, true);
  assert.deepEqual(first.previousState, { integrity: 'intact' });
  assert.deepEqual(first.currentState, { integrity: 'punctured' });

  const second = transitions.apply({
    structureId: vein.id,
    transition: 'puncture',
  });
  assert.equal(second.changed, false);
  assert.deepEqual(second.previousState, { integrity: 'punctured' });
  assert.deepEqual(second.currentState, { integrity: 'punctured' });
  assert.deepEqual(patient.medicalStateFor(vein.id), {
    integrity: 'punctured',
  });
});

test('patient rejects duplicate patient structure ids', () => {
  const first = new PatientStructureInstance({
    id: structureId('structure.fixture.same'),
    canonicalEntityId: entityId('entity.fixture.first'),
    representationAssetIds: [],
  });
  const second = new PatientStructureInstance({
    id: structureId('structure.fixture.same'),
    canonicalEntityId: entityId('entity.fixture.second'),
    representationAssetIds: [],
  });

  assert.throws(
    () => makePatientFromStructures('patient.fixture', [first, second]),
    /Duplicate patient structure id/,
  );
});

test('static physiology exposes explicit unavailable values', () => {
  const physiology = new StaticUnavailablePhysiology();
  const structure = structureId('structure.fixture.vein');
  const position = patientSpacePoint(0, 0, 0);

  assert.equal(physiology.pressureAt(structure, position), null);
  assert.equal(physiology.velocityAt(structure, position), null);
  assert.equal(physiology.flowFor(structure), null);
  assert.equal(physiology.cardiacPhase(), null);
  assert.equal(physiology.respiratoryPhase(), null);
  assert.equal('complianceFor' in physiology, false);
});

test('synthetic anatomy fixture remains explicitly non-medical', async () => {
  const fixturePath = fileURLToPath(
    new URL('../fixtures/anatomy/synthetic-anatomy-v1.json', import.meta.url),
  );
  const fixture = JSON.parse(await fs.readFile(fixturePath, 'utf8'));

  assert.equal(fixture.provenance.sourceClass, 'development-fixture');
  assert.deepEqual(
    fixture.entities.map((entity) => entity.geometry.shape),
    ['slab', 'slab', 'cylinder', 'cylinder'],
  );
  assert.deepEqual(
    fixture.entities.map((entity) => entity.id),
    [
      'entity.fixture.skin',
      'entity.fixture.soft-tissue',
      'entity.fixture.vein',
      'entity.fixture.artery',
    ],
  );
});
