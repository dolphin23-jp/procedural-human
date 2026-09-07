import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { assetId } from '../packages/core/dist/index.js';
import { PatientStructureInstance } from '../packages/patient/dist/index.js';
import {
  FIXTURE_STRUCTURE_IDS,
  ThreeGlbRuntimeLoader,
  createFixtureCoordinateTransform,
  createFixtureSemanticContext,
} from '../packages/rendering-three/dist/index.js';
import { loadedAssetGroupFor } from '../packages/rendering-three/dist/glb-runtime-loader.js';

const descriptorFor = (context) => ({
  assetId: assetId('asset.fixture.synthetic-anatomy-v1.glb'),
  patientId: context.patientId,
  coordinateSpace: 'patient-mm',
  bindings: [
    {
      renderBindingKey: 'fixture.skin.surface',
      structureId: FIXTURE_STRUCTURE_IDS.skin,
    },
    {
      renderBindingKey: 'fixture.soft-tissue.surface',
      structureId: FIXTURE_STRUCTURE_IDS.softTissue,
    },
    {
      renderBindingKey: 'fixture.vein.surface',
      structureId: FIXTURE_STRUCTURE_IDS.vein,
    },
    {
      renderBindingKey: 'fixture.artery.surface',
      structureId: FIXTURE_STRUCTURE_IDS.artery,
    },
  ],
});

async function fixtureBuffer() {
  const buffer = await readFile('fixtures/rendering/synthetic-anatomy-v1.glb');
  return buffer.buffer.slice(
    buffer.byteOffset,
    buffer.byteOffset + buffer.byteLength,
  );
}

test('TASK-048 GLB loader resolves explicit runtime keys to patient and canonical semantic identities', async () => {
  const context = createFixtureSemanticContext();
  const loader = new ThreeGlbRuntimeLoader(
    context,
    createFixtureCoordinateTransform(),
  );
  const asset = await loader.loadFromArrayBuffer(
    await fixtureBuffer(),
    descriptorFor(context),
  );

  assert.deepEqual(asset.summary(), {
    assetId: 'asset.fixture.synthetic-anatomy-v1.glb',
    structureIds: [
      'structure.fixture.skin',
      'structure.fixture.soft-tissue',
      'structure.fixture.vein',
      'structure.fixture.artery',
    ],
    meshCount: 4,
  });
  const identities = asset.semanticIdentities();
  assert.ok(
    identities.every(
      (identity) =>
        identity.patientStructure instanceof PatientStructureInstance,
    ),
  );
  assert.deepEqual(
    identities.map((identity) => identity.anatomicalEntity.name),
    ['Fixture Skin', 'Fixture Soft Tissue', 'Fixture Vein', 'Fixture Artery'],
  );

  const root = loadedAssetGroupFor(asset);
  assert.equal(root.matrixAutoUpdate, false);
  const gltfScene = root.children[0];
  // The fixture deliberately lies in node names. Explicit bindings must win.
  assert.equal(gltfScene.children[0].name, 'radial_artery');
  assert.equal(identities[0].patientStructure.id, 'structure.fixture.skin');

  asset.dispose();
  asset.dispose();
  assert.throws(() => loadedAssetGroupFor(asset), /disposed/);
});

test('TASK-048 GLB loader fails closed on missing, duplicate, unknown or cross-patient semantic binding', async () => {
  const context = createFixtureSemanticContext();
  const loader = new ThreeGlbRuntimeLoader(
    context,
    createFixtureCoordinateTransform(),
  );
  const data = await fixtureBuffer();

  const missing = descriptorFor(context);
  missing.bindings = missing.bindings.slice(0, 3);
  await assert.rejects(
    loader.loadFromArrayBuffer(data, missing),
    /unbound renderBindingKey/,
  );

  const duplicate = descriptorFor(context);
  duplicate.bindings = [
    ...duplicate.bindings,
    {
      renderBindingKey: 'fixture.skin.surface',
      structureId: FIXTURE_STRUCTURE_IDS.vein,
    },
  ];
  await assert.rejects(
    loader.loadFromArrayBuffer(data, duplicate),
    /Duplicate GLB renderBindingKey/,
  );

  const wrongPatient = {
    ...descriptorFor(context),
    patientId: 'patient.other',
  };
  await assert.rejects(
    loader.loadFromArrayBuffer(data, wrongPatient),
    /patient binding mismatch/,
  );

  const wrongStructure = descriptorFor(context);
  wrongStructure.bindings = wrongStructure.bindings.map((binding, index) =>
    index === 0
      ? { ...binding, structureId: 'structure.fixture.does-not-exist' }
      : binding,
  );
  await assert.rejects(
    loader.loadFromArrayBuffer(data, wrongStructure),
    /Unknown patient structure/,
  );

  await assert.rejects(
    loader.loadFromArrayBuffer(data, {
      ...descriptorFor(context),
      coordinateSpace: 'render',
    }),
    /coordinateSpace/,
  );
});
