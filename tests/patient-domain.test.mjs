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

const makePatient = () => {
  const vein = new PatientStructureInstance({
    id: structureId('structure.fixture.vein'),
    canonicalEntityId: entityId('entity.fixture.vein'),
    representationAssetIds: [assetId('asset.fixture.vein')],
  });

  return {
    vein,
    patient: new PatientInstance({
      id: patientId('patient.fixture'),
      morphology: { mode: 'static' },
      anatomy: {
        canonicalAnatomy: {
          assetId: assetId('asset.fixture.anatomy'),
          version: version('1'),
          contentHash: hash,
        },
        structures: [vein],
      },
    }),
  };
};

test('patient structures start intact and mutate only through transition service', () => {
  const { patient, vein } = makePatient();
  assert.deepEqual(vein.medicalState, { integrity: 'intact' });

  const transitions = new PatientStateTransitionService(patient);
  const first = transitions.apply({
    structureId: vein.id,
    transition: 'puncture',
  });
  assert.equal(first.changed, true);
  assert.deepEqual(first.previousState, { integrity: 'intact' });
  assert.deepEqual(first.currentState, { integrity: 'punctured' });
  assert.deepEqual(vein.medicalState, { integrity: 'punctured' });

  const second = transitions.apply({
    structureId: vein.id,
    transition: 'puncture',
  });
  assert.equal(second.changed, false);
});

test('patient rejects duplicate patient structure ids', () => {
  const structure = new PatientStructureInstance({
    id: structureId('structure.fixture.same'),
    canonicalEntityId: entityId('entity.fixture.same'),
    representationAssetIds: [],
  });

  assert.throws(
    () =>
      new PatientInstance({
        id: patientId('patient.fixture'),
        morphology: { mode: 'static' },
        anatomy: {
          canonicalAnatomy: {
            assetId: assetId('asset.fixture.anatomy'),
            version: version('1'),
            contentHash: hash,
          },
          structures: [structure, structure],
        },
      }),
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
  assert.equal(physiology.complianceFor(structure), null);
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
