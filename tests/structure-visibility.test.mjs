import assert from 'node:assert/strict';
import test from 'node:test';
import {
  FIXTURE_STRUCTURE_IDS,
  ThreeStructurePresentation,
  createFixtureCoordinateTransform,
  createFixtureSemanticContext,
} from '../packages/rendering-three/dist/index.js';
import { createFixtureGroup } from '../packages/rendering-three/dist/fixture-scene.js';
import {
  bindSemanticObjects,
  semanticMeshesFor,
} from '../packages/rendering-three/dist/semantic-context.js';

function boundFixture() {
  const context = createFixtureSemanticContext();
  const group = createFixtureGroup(createFixtureCoordinateTransform());
  for (const mesh of group.children) {
    bindSemanticObjects(context, mesh.userData.structureId, [mesh]);
  }
  return { context, group };
}

test('TASK-049 visibility changes every bound representation and nothing semantic', () => {
  const { context, group } = boundFixture();
  const presentation = new ThreeStructurePresentation(context);
  const veinIdentity = context.identityFor(FIXTURE_STRUCTURE_IDS.vein);
  const veinStructure = veinIdentity.patientStructure;
  const veinEntity = veinIdentity.anatomicalEntity;

  presentation.setVisibility({
    structureId: FIXTURE_STRUCTURE_IDS.vein,
    visible: false,
  });

  assert.ok(
    semanticMeshesFor(context, FIXTURE_STRUCTURE_IDS.vein).every(
      (mesh) => mesh.visible === false,
    ),
  );
  assert.equal(
    context.identityFor(FIXTURE_STRUCTURE_IDS.vein).patientStructure,
    veinStructure,
  );
  assert.equal(
    context.identityFor(FIXTURE_STRUCTURE_IDS.vein).anatomicalEntity,
    veinEntity,
  );
  assert.ok(
    group.children
      .filter(
        (mesh) => mesh.userData.structureId !== FIXTURE_STRUCTURE_IDS.vein,
      )
      .every((mesh) => mesh.visible),
  );

  presentation.setVisibility({
    structureId: FIXTURE_STRUCTURE_IDS.vein,
    visible: true,
  });
  assert.ok(
    semanticMeshesFor(context, FIXTURE_STRUCTURE_IDS.vein).every(
      (mesh) => mesh.visible,
    ),
  );
});

test('TASK-049 visibility fails closed for invalid or unbound structures', () => {
  const { context } = boundFixture();
  const presentation = new ThreeStructurePresentation(context);
  assert.throws(
    () =>
      presentation.setVisibility({
        structureId: FIXTURE_STRUCTURE_IDS.skin,
        visible: 'yes',
      }),
    /explicit boolean/,
  );
  assert.throws(
    () =>
      presentation.setVisibility({
        structureId: 'structure.fixture.unknown',
        visible: false,
      }),
    /Unknown patient structure/,
  );

  const fresh = createFixtureSemanticContext();
  const freshPresentation = new ThreeStructurePresentation(fresh);
  assert.throws(
    () =>
      freshPresentation.setVisibility({
        structureId: FIXTURE_STRUCTURE_IDS.skin,
        visible: false,
      }),
    /No render representation bound/,
  );
});
