/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local Three declarations */
/// <reference path="./three.d.ts" />
import type { StructureId } from '@procedural-human/core';
import { patientSpacePoint } from '@procedural-human/math';
import {
  PatientRenderTransform,
  type CameraIntent,
  type PatientClippingPlane,
  type StructureOpacity,
  type StructureVisibility,
} from '@procedural-human/rendering-core';
import {
  AmbientLight,
  Color,
  DirectionalLight,
  PerspectiveCamera,
  Scene,
  WebGLRenderer,
} from 'three';
import { CameraInputController } from './camera-input.js';
import { ThreeCameraRig } from './camera-rig.js';
import { patientClippingPlaneToThree } from './clipping-plane.js';
import {
  ThreeFixtureScene,
  fixtureGroupFor,
  type FixtureSceneSummary,
} from './fixture-scene.js';
import { createFixtureSemanticContext } from './fixture-semantics.js';
import { ThreeSemanticPicker, type SemanticPickResult } from './picking.js';
import {
  bindSemanticObjects,
  ThreeSemanticContext,
} from './semantic-context.js';
import { ThreeStructurePresentation } from './structure-presentation.js';
import { renderPointToThree } from './three-coordinates.js';
import { createFixtureCamera } from './fixture-view.js';

export { ThreeFixtureScene } from './fixture-scene.js';
export type { FixtureSceneSummary } from './fixture-scene.js';
export {
  createFixtureCoordinateTransform,
  createFixtureDemoClippingPlane,
} from './fixture-coordinates.js';

export interface ThreeFixtureRendererOptions {
  readonly coordinates: PatientRenderTransform;
  readonly semanticContext?: ThreeSemanticContext;
  readonly maximumPixelRatio?: number;
}

export interface ThreeFixtureInputOptions {
  readonly onSelection?: (selection: SemanticPickResult | null) => void;
}

/** Interactive renderer for the explicitly non-medical synthetic fixture. */
export class ThreeFixtureRenderer {
  readonly #canvas: HTMLCanvasElement;
  readonly #coordinates: PatientRenderTransform;
  readonly #renderer: WebGLRenderer;
  readonly #scene: Scene;
  readonly #camera: PerspectiveCamera;
  readonly #fixtureScene: ThreeFixtureScene;
  readonly #context: ThreeSemanticContext;
  readonly #presentation: ThreeStructurePresentation;
  readonly #picker: ThreeSemanticPicker;
  readonly #cameraRig: ThreeCameraRig;
  #input: CameraInputController | null = null;
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
    this.#canvas = canvas;
    this.#coordinates = coordinates;
    this.#context = options.semanticContext ?? createFixtureSemanticContext();
    this.#camera = createFixtureCamera(coordinates);
    this.#cameraRig = new ThreeCameraRig(
      this.#camera,
      coordinates,
      patientSpacePoint(0, 0, 12),
    );
    this.#fixtureScene = new ThreeFixtureScene(coordinates);
    const fixtureGroup = fixtureGroupFor(this.#fixtureScene);
    for (const child of fixtureGroup.children) {
      const structureId = child.userData.structureId as StructureId;
      bindSemanticObjects(this.#context, structureId, [child]);
    }
    this.#presentation = new ThreeStructurePresentation(this.#context);
    this.#picker = new ThreeSemanticPicker(this.#context, coordinates);
    try {
      this.#renderer = new WebGLRenderer({ canvas, antialias: true });
    } catch (error) {
      this.#presentation.dispose();
      this.#fixtureScene.dispose();
      throw error;
    }
    this.#renderer.setPixelRatio(
      Math.min(globalThis.devicePixelRatio ?? 1, maximumPixelRatio),
    );
    this.#scene = new Scene();
    this.#scene.background = new Color(0x101621);
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

  attachInput(options: ThreeFixtureInputOptions = {}): void {
    this.#assertActive();
    this.#input?.dispose();
    this.#input = new CameraInputController(this.#canvas, {
      frame: () => {
        const height = this.#canvas.getBoundingClientRect().height;
        return this.#cameraRig.inputFrame(height);
      },
      emit: (intent) => {
        try {
          this.applyCameraIntent(intent);
        } catch (error) {
          if (intent.type !== 'dolly') throw error;
        }
      },
      onTap: (clientX, clientY) => {
        const selection = this.pickClientPoint(clientX, clientY);
        this.#presentation.setSelection(selection?.patientStructure.id ?? null);
        options.onSelection?.(selection);
      },
    });
  }

  setVisibility(request: StructureVisibility): void {
    this.#presentation.setVisibility(request);
    this.render();
  }

  setOpacity(request: StructureOpacity): void {
    this.#presentation.setOpacity(request);
    this.render();
  }

  setClippingPlane(plane: PatientClippingPlane | null): void {
    this.#assertActive();
    this.#renderer.clippingPlanes =
      plane === null
        ? []
        : [patientClippingPlaneToThree(plane, this.#coordinates)];
    this.render();
  }

  applyCameraIntent(intent: CameraIntent): void {
    this.#assertActive();
    this.#cameraRig.apply(intent);
    this.render();
  }

  pickClientPoint(clientX: number, clientY: number): SemanticPickResult | null {
    this.#assertActive();
    if (![clientX, clientY].every(Number.isFinite)) {
      throw new RangeError('Client picking coordinates must be finite.');
    }
    const rect = this.#canvas.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    const x = ((clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((clientY - rect.top) / rect.height) * 2 + 1;
    return this.#picker.pickNdc(x, y, this.#camera);
  }

  resize(width: number, height: number): void {
    this.#assertActive();
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
    this.#assertActive();
    this.#renderer.render(this.#scene, this.#camera);
  }

  dispose(): void {
    if (this.#disposed) return;
    this.#input?.dispose();
    this.#presentation.dispose();
    this.#fixtureScene.dispose();
    this.#renderer.dispose();
    this.#disposed = true;
  }

  #assertActive(): void {
    if (this.#disposed) throw new Error('ThreeFixtureRenderer is disposed.');
  }
}

export { ThreeSemanticContext } from './semantic-context.js';
export type { SemanticRenderIdentity } from './semantic-context.js';
export { ThreeGlbRuntimeLoader } from './glb-runtime-loader.js';
export type {
  GlbRuntimeAssetDescriptor,
  GlbSemanticBinding,
  ThreeLoadedRenderAsset,
  ThreeLoadedRenderAssetSummary,
} from './glb-runtime-loader.js';
export {
  createFixtureSemanticContext,
  FIXTURE_RENDER_ASSET_ID,
} from './fixture-semantics.js';
export { FIXTURE_STRUCTURE_IDS } from './fixture-ids.js';
export { ThreeStructurePresentation } from './structure-presentation.js';
export { ThreeSemanticPicker } from './picking.js';
export type { SemanticPickResult } from './picking.js';
export { ThreeCameraRig } from './camera-rig.js';
export type { CameraInputFrame } from './camera-rig.js';
export {
  CameraInputController,
  dollyIntentFromPixels,
  orbitIntentsFromScreenDrag,
  panIntentFromScreenDrag,
} from './camera-input.js';
