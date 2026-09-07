/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local Three declarations */
/// <reference path="./three.d.ts" />
import { structureId, type StructureId } from '@procedural-human/core';
import { PatientRenderTransform } from '@procedural-human/rendering-core';
import {
  BoxGeometry,
  CylinderGeometry,
  Group,
  Mesh,
  MeshStandardMaterial,
} from 'three';
import { patientToThreeMatrix } from './three-coordinates.js';

const FIXTURE_STRUCTURE_IDS = Object.freeze({
  skin: structureId('structure.fixture.skin'),
  softTissue: structureId('structure.fixture.soft-tissue'),
  vein: structureId('structure.fixture.vein'),
  artery: structureId('structure.fixture.artery'),
});

export interface FixtureSceneSummary {
  readonly structureIds: readonly StructureId[];
  readonly meshCount: number;
}

interface FixtureMeshDescriptor {
  readonly id: StructureId;
  readonly name: string;
  readonly shape:
    | { readonly kind: 'box'; readonly size: readonly [number, number, number] }
    | {
        readonly kind: 'x-cylinder';
        readonly radius: number;
        readonly length: number;
      };
  readonly center: readonly [number, number, number];
  readonly color: number;
  readonly opacity: number;
}

/* Fixture vertices and centers are Patient Space millimetres. */
const fixtureMeshes: readonly FixtureMeshDescriptor[] = Object.freeze([
  {
    id: FIXTURE_STRUCTURE_IDS.skin,
    name: 'Fixture Skin',
    shape: { kind: 'box', size: [100, 80, 2] },
    center: [0, 0, 0],
    color: 0xe7b8a0,
    opacity: 0.48,
  },
  {
    id: FIXTURE_STRUCTURE_IDS.softTissue,
    name: 'Fixture Soft Tissue',
    shape: { kind: 'box', size: [100, 80, 30] },
    center: [0, 0, 16],
    color: 0xe8c45f,
    opacity: 0.22,
  },
  {
    id: FIXTURE_STRUCTURE_IDS.vein,
    name: 'Fixture Vein',
    shape: { kind: 'x-cylinder', radius: 3, length: 70 },
    center: [0, -10, 10],
    color: 0x2f80ed,
    opacity: 0.92,
  },
  {
    id: FIXTURE_STRUCTURE_IDS.artery,
    name: 'Fixture Artery',
    shape: { kind: 'x-cylinder', radius: 3, length: 70 },
    center: [0, 10, 15],
    color: 0xd64545,
    opacity: 0.92,
  },
]);

function makeFixtureMesh(descriptor: FixtureMeshDescriptor): Mesh {
  const geometry =
    descriptor.shape.kind === 'box'
      ? new BoxGeometry(...descriptor.shape.size)
      : new CylinderGeometry(
          descriptor.shape.radius,
          descriptor.shape.radius,
          descriptor.shape.length,
          32,
        );
  const material = new MeshStandardMaterial({
    color: descriptor.color,
    opacity: descriptor.opacity,
    transparent: descriptor.opacity < 1,
    depthWrite: descriptor.opacity === 1,
    roughness: 0.72,
    metalness: 0,
  });
  const mesh = new Mesh(geometry, material);
  mesh.name = descriptor.name;
  mesh.userData = { structureId: descriptor.id };
  mesh.position.set(...descriptor.center);
  if (descriptor.shape.kind === 'x-cylinder') mesh.rotation.z = Math.PI / 2;
  return mesh;
}

export function createFixtureGroup(coordinates: PatientRenderTransform): Group {
  if (!(coordinates instanceof PatientRenderTransform)) {
    throw new TypeError('Explicit PatientRenderTransform is required.');
  }
  const group = new Group();
  group.name = 'Synthetic anatomy fixture v1';
  group.matrixAutoUpdate = false;
  group.matrix.copy(patientToThreeMatrix(coordinates));
  group.add(...fixtureMeshes.map(makeFixtureMesh));
  return group;
}

function disposeFixtureGroup(group: Group): void {
  for (const child of group.children) {
    if (!(child instanceof Mesh)) continue;
    child.geometry.dispose();
    const materials = Array.isArray(child.material)
      ? child.material
      : [child.material];
    for (const material of materials) material.dispose();
  }
}

const fixtureGroups = new WeakMap<ThreeFixtureScene, Group>();

/** Owns the Three.js scene objects for the non-medical synthetic fixture. */
export class ThreeFixtureScene {
  readonly #fixture: Group;
  #disposed = false;

  constructor(coordinates: PatientRenderTransform) {
    this.#fixture = createFixtureGroup(coordinates);
    fixtureGroups.set(this, this.#fixture);
  }

  summary(): FixtureSceneSummary {
    return Object.freeze({
      structureIds: Object.freeze(
        this.#fixture.children.map(
          (child) => child.userData.structureId as StructureId,
        ),
      ),
      meshCount: this.#fixture.children.length,
    });
  }

  dispose(): void {
    if (this.#disposed) return;
    disposeFixtureGroup(this.#fixture);
    this.#disposed = true;
  }
}

export function fixtureGroupFor(scene: ThreeFixtureScene): Group {
  const group = fixtureGroups.get(scene);
  if (!group) throw new Error('Fixture scene graph is unavailable.');
  return group;
}
