/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local Three declarations */
/// <reference path="./three.d.ts" />
import { patientSpacePoint } from '@procedural-human/math';
import { PatientRenderTransform } from '@procedural-human/rendering-core';
import {
  AmbientLight,
  Color,
  DirectionalLight,
  PerspectiveCamera,
  Scene,
  WebGLRenderer,
} from 'three';
import {
  ThreeFixtureScene,
  fixtureGroupFor,
  type FixtureSceneSummary,
} from './fixture-scene.js';
import { renderPointToThree } from './three-coordinates.js';
import { createFixtureCamera } from './fixture-view.js';

export { ThreeFixtureScene } from './fixture-scene.js';
export type { FixtureSceneSummary } from './fixture-scene.js';
export { createFixtureCoordinateTransform } from './fixture-coordinates.js';

export interface ThreeFixtureRendererOptions {
  readonly coordinates: PatientRenderTransform;
  readonly maximumPixelRatio?: number;
}

/** Static TASK-046 adapter. Camera input and presentation commands arrive later. */
export class ThreeFixtureRenderer {
  readonly #renderer: WebGLRenderer;
  readonly #scene: Scene;
  readonly #camera: PerspectiveCamera;
  readonly #fixtureScene: ThreeFixtureScene;
  #disposed = false;

  constructor(canvas: HTMLCanvasElement, options: ThreeFixtureRendererOptions) {
    const coordinates = options?.coordinates;
    if (!(coordinates instanceof PatientRenderTransform)) {
      throw new TypeError('Explicit PatientRenderTransform is required.');
    }
    const maximumPixelRatio = options.maximumPixelRatio ?? 2;
    if (!Number.isFinite(maximumPixelRatio) || maximumPixelRatio <= 0) {
      throw new RangeError(
        'Maximum pixel ratio must be finite and greater than zero.',
      );
    }
    // Validate the coordinate-dependent view and geometry before allocating WebGL.
    this.#camera = createFixtureCamera(coordinates);
    this.#fixtureScene = new ThreeFixtureScene(coordinates);
    try {
      this.#renderer = new WebGLRenderer({ canvas, antialias: true });
    } catch (error) {
      this.#fixtureScene.dispose();
      throw error;
    }
    this.#renderer.setPixelRatio(
      Math.min(globalThis.devicePixelRatio ?? 1, maximumPixelRatio),
    );
    this.#scene = new Scene();
    this.#scene.background = new Color(0x101621);
    const fixtureGroup = fixtureGroupFor(this.#fixtureScene);
    this.#scene.add(fixtureGroup);
    const point = (x: number, y: number, z: number) =>
      renderPointToThree(
        coordinates.patientPointToRender(patientSpacePoint(x, y, z)),
      );
    const ambient = new AmbientLight(0xffffff, 1.25);
    const key = new DirectionalLight(0xffffff, 2.4);
    key.position.copy(point(70, -45, 110));
    key.target.position.copy(point(0, 0, 0));
    const fill = new DirectionalLight(0x82aaff, 1.1);
    fill.position.copy(point(-60, 45, 55));
    fill.target.position.copy(point(0, 0, 0));
    this.#scene.add(ambient, key, key.target, fill, fill.target);
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
