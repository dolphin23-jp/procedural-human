/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local Three declarations */
/// <reference path="./three.d.ts" />
import type { PatientSpacePoint } from '@procedural-human/math';
import type { PatientRenderTransform } from '@procedural-human/rendering-core';
import type { PerspectiveCamera } from 'three';
import { Raycaster, Vector2 } from 'three';
import {
  allSemanticMeshes,
  resolveSemanticObject,
  type SemanticRenderIdentity,
  ThreeSemanticContext,
} from './semantic-context.js';
import { threePointToRender } from './three-coordinates.js';

export interface SemanticPickResult extends SemanticRenderIdentity {
  readonly patientPoint: PatientSpacePoint;
  readonly distanceRenderUnits: number;
}

export class ThreeSemanticPicker {
  readonly #context: ThreeSemanticContext;
  readonly #coordinates: PatientRenderTransform;
  readonly #raycaster = new Raycaster();

  constructor(
    context: ThreeSemanticContext,
    coordinates: PatientRenderTransform,
  ) {
    if (!(context instanceof ThreeSemanticContext)) {
      throw new TypeError('Explicit ThreeSemanticContext is required.');
    }
    this.#context = context;
    this.#coordinates = coordinates;
  }

  pickNdc(
    x: number,
    y: number,
    camera: PerspectiveCamera,
  ): SemanticPickResult | null {
    if (![x, y].every(Number.isFinite) || x < -1 || x > 1 || y < -1 || y > 1) {
      throw new RangeError(
        'Picking coordinates must be finite NDC values in [-1, 1].',
      );
    }
    this.#raycaster.setFromCamera(new Vector2(x, y), camera);
    const candidates = allSemanticMeshes(this.#context).filter(
      (mesh) => mesh.visible,
    );
    const intersections = this.#raycaster.intersectObjects(candidates, false);
    for (const intersection of intersections) {
      const identity = resolveSemanticObject(
        this.#context,
        intersection.object,
      );
      if (!identity) continue;
      return Object.freeze({
        ...identity,
        patientPoint: this.#coordinates.renderPointToPatient(
          threePointToRender(intersection.point),
        ),
        distanceRenderUnits: intersection.distance,
      });
    }
    return null;
  }
}
