/* eslint-disable @typescript-eslint/triple-slash-reference -- adapter-local Three declarations */
/// <reference path="./three.d.ts" />
import {
  patientSpaceDirection,
  patientSpacePoint,
  patientSpaceVector,
  renderSpaceDirection,
  type PatientSpaceDirection,
  type PatientSpacePoint,
} from '@procedural-human/math';
import type {
  CameraIntent,
  PatientRenderTransform,
} from '@procedural-human/rendering-core';
import {
  toMillimetres,
  toRadians,
} from '@procedural-human/units';
import { PerspectiveCamera, Quaternion, Vector3 } from 'three';
import {
  renderPointToThree,
  renderVectorToThree,
} from './three-coordinates.js';

export interface CameraInputFrame {
  readonly pivot: PatientSpacePoint;
  readonly screenRight: PatientSpaceDirection;
  readonly screenUp: PatientSpaceDirection;
  readonly millimetresPerPixel: number;
}

export class ThreeCameraRig {
  readonly #camera: PerspectiveCamera;
  readonly #coordinates: PatientRenderTransform;
  readonly #target: Vector3;

  constructor(
    camera: PerspectiveCamera,
    coordinates: PatientRenderTransform,
    initialTarget: PatientSpacePoint,
  ) {
    this.#camera = camera;
    this.#coordinates = coordinates;
    this.#target = renderPointToThree(
      coordinates.patientPointToRender(initialTarget),
    );
    this.#lookAtTarget();
  }

  apply(intent: CameraIntent): void {
    switch (intent.type) {
      case 'orbit':
        this.#orbit(intent);
        break;
      case 'pan': {
        const offset = renderVectorToThree(
          this.#coordinates.patientVectorToRender(intent.offset),
        );
        this.#camera.position.add(offset);
        this.#target.add(offset);
        this.#lookAtTarget();
        break;
      }
      case 'dolly': {
        const millimetres = toMillimetres(intent.distance);
        if (!Number.isFinite(millimetres)) {
          throw new RangeError('Camera dolly distance must be finite.');
        }
        const mmPerUnit = toMillimetres(
          this.#coordinates.config.millimetresPerRenderUnit,
        );
        const direction = this.#target.clone().sub(this.#camera.position);
        const currentDistance = direction.length();
        if (!Number.isFinite(currentDistance) || currentDistance <= 0) {
          throw new Error('Camera view direction is not usable.');
        }
        direction.normalize();
        const travel = millimetres / mmPerUnit;
        const nextDistance = currentDistance - travel;
        if (!Number.isFinite(nextDistance) || nextDistance <= this.#camera.near * 2) {
          throw new RangeError('Camera dolly would cross the focus target or near plane.');
        }
        this.#camera.position.add(direction.multiplyScalar(travel));
        this.#lookAtTarget();
        break;
      }
      case 'focus':
        this.#target.copy(
          renderPointToThree(
            this.#coordinates.patientPointToRender(intent.target),
          ),
        );
        this.#lookAtTarget();
        break;
      default: {
        const unreachable: never = intent;
        return unreachable;
      }
    }
  }

  inputFrame(viewportHeight: number): CameraInputFrame {
    if (!Number.isFinite(viewportHeight) || viewportHeight <= 0) {
      throw new RangeError('Viewport height must be finite and positive.');
    }
    const view = this.#target.clone().sub(this.#camera.position);
    const distanceRenderUnits = view.length();
    if (!Number.isFinite(distanceRenderUnits) || distanceRenderUnits <= 0) {
      throw new Error('Camera view direction is not usable.');
    }
    view.normalize();
    const up = this.#camera.up.clone().normalize();
    const right = new Vector3().crossVectors(view, up).normalize();
    const screenUp = new Vector3().crossVectors(right, view).normalize();
    const rightPatient = this.#coordinates.renderDirectionToPatient(
      renderSpaceDirection(right.x, right.y, right.z),
    );
    const upPatient = this.#coordinates.renderDirectionToPatient(
      renderSpaceDirection(screenUp.x, screenUp.y, screenUp.z),
    );
    const mmPerUnit = toMillimetres(
      this.#coordinates.config.millimetresPerRenderUnit,
    );
    const distanceMm = distanceRenderUnits * mmPerUnit;
    const verticalSpanMm =
      2 * distanceMm * Math.tan((this.#camera.fov * Math.PI) / 360);
    return Object.freeze({
      pivot: this.targetPatientPoint(),
      screenRight: rightPatient,
      screenUp: upPatient,
      millimetresPerPixel: verticalSpanMm / viewportHeight,
    });
  }

  targetPatientPoint(): PatientSpacePoint {
    return this.#coordinates.renderPointToPatient({
      space: 'render',
      kind: 'point',
      value: {
        x: this.#target.x,
        y: this.#target.y,
        z: this.#target.z,
      },
    });
  }

  #orbit(intent: Extract<CameraIntent, { readonly type: 'orbit' }>): void {
    const angle = toRadians(intent.angle);
    if (!Number.isFinite(angle)) {
      throw new RangeError('Camera orbit angle must be finite.');
    }
    const axis = this.#coordinates.patientDirectionToRender(intent.axis).value;
    const pivot = renderPointToThree(
      this.#coordinates.patientPointToRender(intent.pivot),
    );
    const quaternion = new Quaternion().setFromAxisAngle(
      new Vector3(axis.x, axis.y, axis.z),
      angle,
    );
    this.#camera.position.sub(pivot).applyQuaternion(quaternion).add(pivot);
    this.#target.sub(pivot).applyQuaternion(quaternion).add(pivot);
    this.#camera.up.applyQuaternion(quaternion).normalize();
    this.#lookAtTarget();
  }

  #lookAtTarget(): void {
    this.#camera.lookAt(this.#target.x, this.#target.y, this.#target.z);
  }
}

export function patientOffsetFromScreenDrag(
  frame: CameraInputFrame,
  deltaX: number,
  deltaY: number,
) {
  if (![deltaX, deltaY].every(Number.isFinite)) {
    throw new RangeError('Screen drag must be finite.');
  }
  const right = frame.screenRight.value;
  const up = frame.screenUp.value;
  const scale = frame.millimetresPerPixel;
  return patientSpaceVector(
    (-deltaX * right.x + deltaY * up.x) * scale,
    (-deltaX * right.y + deltaY * up.y) * scale,
    (-deltaX * right.z + deltaY * up.z) * scale,
  );
}

export function canonicalPatientDirections() {
  return Object.freeze({
    x: patientSpaceDirection(1, 0, 0),
    y: patientSpaceDirection(0, 1, 0),
    z: patientSpaceDirection(0, 0, 1),
    origin: patientSpacePoint(0, 0, 0),
  });
}
