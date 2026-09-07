import assert from 'node:assert/strict';
import test from 'node:test';
import { ThreeFixtureScene } from '../packages/rendering-three/dist/index.js';

test('TASK-046 Three scene represents every synthetic fixture structure semantically', () => {
  const scene = new ThreeFixtureScene();
  assert.deepEqual(scene.summary(), {
    structureIds: [
      'structure.fixture.skin',
      'structure.fixture.soft-tissue',
      'structure.fixture.vein',
      'structure.fixture.artery',
    ],
    meshCount: 4,
  });
  scene.dispose();
  scene.dispose();
});
