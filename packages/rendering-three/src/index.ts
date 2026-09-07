/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local declarations for untyped Three.js */
/// <reference path="./three.d.ts" />

import { structureId, type StructureId } from '@procedural-human/core';
import {
  AmbientLight,
  BoxGeometry,
  Color,
  CylinderGeometry,
  DirectionalLight,
  Group,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  Scene,
  WebGLRenderer,
} from 'three';

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
export interface ThreeFixtureRendererOptions {
  readonly maximumPixelRatio?: number;
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

/* Renderer-local fixture geometry. Patient/render conversion starts in TASK-047. */
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

function createFixtureGroup(): Group {
  const group = new Group();
  group.name = 'Synthetic anatomy fixture v1';
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

  constructor() {
    this.#fixture = createFixtureGroup();
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

/** Static TASK-046 adapter. Camera input and presentation commands arrive later. */
export class ThreeFixtureRenderer {
  readonly #renderer: WebGLRenderer;
  readonly #scene: Scene;
  readonly #camera: PerspectiveCamera;
  readonly #fixtureScene: ThreeFixtureScene;
  #disposed = false;

  constructor(
    canvas: HTMLCanvasElement,
    options: ThreeFixtureRendererOptions = {},
  ) {
    const maximumPixelRatio = options.maximumPixelRatio ?? 2;
    if (!Number.isFinite(maximumPixelRatio) || maximumPixelRatio <= 0) {
      throw new RangeError(
        'Maximum pixel ratio must be finite and greater than zero.',
      );
    }
    this.#renderer = new WebGLRenderer({ canvas, antialias: true });
    this.#renderer.setPixelRatio(
      Math.min(globalThis.devicePixelRatio ?? 1, maximumPixelRatio),
    );
    this.#scene = new Scene();
    this.#scene.background = new Color(0x101621);
    this.#fixtureScene = new ThreeFixtureScene();
    const fixtureGroup = fixtureGroups.get(this.#fixtureScene);
    if (!fixtureGroup) throw new Error('Fixture scene graph is unavailable.');
    this.#scene.add(fixtureGroup);
    this.#camera = new PerspectiveCamera(34, 1, 0.1, 500);
    this.#camera.position.set(105, -105, 85);
    this.#camera.lookAt(0, 0, 12);
    const ambient = new AmbientLight(0xffffff, 1.25);
    const key = new DirectionalLight(0xffffff, 2.4);
    key.position.set(70, -45, 110);
    const fill = new DirectionalLight(0x82aaff, 1.1);
    fill.position.set(-60, 45, 55);
    this.#scene.add(ambient, key, fill);
  }

  summary(): FixtureSceneSummary {
    return this.#fixtureScene.summary();
  }

  resize(width: number, height: number): void {
    if (this.#disposed) throw new Error('ThreeFixtureRenderer is disposed.');
    if (!Number.isFinite(width) || width <= 0)
      throw new RangeError(
        'Renderer width must be finite and greater than zero.',
      );
    if (!Number.isFinite(height) || height <= 0)
      throw new RangeError(
        'Renderer height must be finite and greater than zero.',
      );
    this.#renderer.setSize(width, height, false);
    this.#camera.aspect = width / height;
    this.#camera.updateProjectionMatrix();
    this.#renderer.render(this.#scene, this.#camera);
  }

  render(): void {
    if (this.#disposed) throw new Error('ThreeFixtureRenderer is disposed.');
    this.#renderer.render(this.#scene, this.#camera);
  }

  dispose(): void {
    if (this.#disposed) return;
    this.#fixtureScene.dispose();
    this.#renderer.dispose();
    this.#disposed = true;
  }
}
