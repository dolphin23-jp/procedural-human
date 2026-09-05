import assert from 'node:assert/strict';
import test from 'node:test';
import {
  AnatomicalGraph,
  createRepresentationBundle,
  provisionalBoundaryRegionReference,
} from '../packages/anatomy/dist/index.js';
import { assetId, contentHash, entityId } from '../packages/core/dist/index.js';

const validation = { level: 'V1', notes: null };
const provenance = {
  sourceClass: 'development-fixture',
  sourceIdentifier: null,
  derivationMethod: null,
  contentHash: contentHash(
    'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  ),
};
const accuracy = {
  identityAccuracy: null,
  topologyAccuracy: null,
  geometryAccuracy: null,
  registrationAccuracy: null,
  diameterAccuracy: null,
  relationshipAccuracy: null,
};

const forearmId = entityId('entity.forearm.left');
const arteryId = entityId('entity.radial-artery.left');
const handId = entityId('entity.hand.left');

const entity = (id, name, relationships = [], representations = []) => ({
  id,
  name,
  type: 'fixture-structure',
  laterality: 'left',
  region: 'distal-forearm',
  relationships,
  representations,
  provenance,
  accuracy,
  validation,
});

test('AnatomicalGraph resolves canonical entities and typed relationships', () => {
  const graph = new AnatomicalGraph([
    entity(forearmId, 'Left forearm'),
    entity(arteryId, 'Left radial artery', [
      { type: 'part_of', targetId: forearmId },
      { type: 'connected_to', targetId: handId },
    ]),
    entity(handId, 'Left hand'),
  ]);

  assert.equal(graph.get(arteryId)?.name, 'Left radial artery');
  assert.equal(graph.relatedFrom(arteryId, 'part_of').length, 1);
  assert.deepEqual(
    graph.relatedEntitiesFrom(arteryId, 'connected_to').map(({ id }) => id),
    [handId],
  );
});

test('AnatomicalGraph rejects duplicate canonical entity ids', () => {
  assert.throws(
    () =>
      new AnatomicalGraph([
        entity(forearmId, 'Left forearm'),
        entity(forearmId, 'Duplicate forearm'),
      ]),
    /Duplicate anatomical entity id/,
  );
});

test('RepresentationBundle preserves schema-compatible descriptors', () => {
  const render = {
    kind: 'renderSurface',
    assetId: assetId('asset.forearm.render'),
  };
  const centerline = {
    kind: 'centerline',
    assetId: assetId('asset.radial-artery.centerline'),
  };

  assert.deepEqual(createRepresentationBundle([render, centerline]), [
    render,
    centerline,
  ]);
  assert.throws(
    () => createRepresentationBundle([render, render]),
    /Duplicate representation kind/,
  );
});

test('Provenance and accuracy represent unknown values explicitly as null', () => {
  const model = entity(arteryId, 'Left radial artery');
  assert.equal(model.provenance.sourceIdentifier, null);
  assert.equal(model.provenance.derivationMethod, null);
  assert.equal(model.accuracy.geometryAccuracy, null);
  assert.equal(model.accuracy.diameterAccuracy, null);
  assert.equal(model.accuracy.relationshipAccuracy, null);
});

test('BoundaryEntity uses explicitly provisional region references only', () => {
  const skin = provisionalBoundaryRegionReference('fixture-skin');
  const softTissue = provisionalBoundaryRegionReference('fixture-soft-tissue');
  const boundary = {
    id: entityId('boundary.fixture.skin-soft-tissue'),
    name: 'Fixture skin-soft tissue boundary',
    separates: [skin, softTissue],
    provenance,
    accuracy,
    validation,
  };

  assert.deepEqual(boundary.separates, ['fixture-skin', 'fixture-soft-tissue']);
  assert.equal(boundary.provenance.sourceClass, 'development-fixture');
});
