import {
  patientSpaceVector,
  type PatientSpaceDirection,
} from '@procedural-human/math';
import type { CameraIntent } from '@procedural-human/rendering-core';
import { millimetres, radians } from '@procedural-human/units';
import type { CameraInputFrame } from './camera-rig.js';
import { patientOffsetFromScreenDrag } from './camera-rig.js';

export interface CameraInputControllerOptions {
  readonly frame: () => CameraInputFrame;
  readonly emit: (intent: CameraIntent) => void;
  readonly onTap?: (clientX: number, clientY: number) => void;
  readonly orbitRadiansPerPixel?: number;
  readonly wheelDollyScale?: number;
}

interface PointerSample {
  readonly x: number;
  readonly y: number;
}

function orbitIntent(
  frame: CameraInputFrame,
  axis: PatientSpaceDirection,
  angle: number,
): CameraIntent {
  return {
    type: 'orbit',
    pivot: frame.pivot,
    axis,
    angle: radians(angle),
  };
}

export function orbitIntentsFromScreenDrag(
  frame: CameraInputFrame,
  deltaX: number,
  deltaY: number,
  radiansPerPixel = 0.008,
): readonly CameraIntent[] {
  if (
    ![deltaX, deltaY, radiansPerPixel].every(Number.isFinite) ||
    radiansPerPixel <= 0
  ) {
    throw new RangeError('Orbit drag values must be finite and scale positive.');
  }
  return Object.freeze([
    orbitIntent(frame, frame.screenUp, -deltaX * radiansPerPixel),
    orbitIntent(frame, frame.screenRight, -deltaY * radiansPerPixel),
  ]);
}

export function panIntentFromScreenDrag(
  frame: CameraInputFrame,
  deltaX: number,
  deltaY: number,
): CameraIntent {
  return {
    type: 'pan',
    offset: patientOffsetFromScreenDrag(frame, deltaX, deltaY),
  };
}

export function dollyIntentFromPixels(
  frame: CameraInputFrame,
  pixels: number,
  multiplier = 1,
): CameraIntent {
  if (![pixels, multiplier].every(Number.isFinite) || multiplier <= 0) {
    throw new RangeError('Dolly input values must be finite and multiplier positive.');
  }
  return {
    type: 'dolly',
    distance: millimetres(pixels * frame.millimetresPerPixel * multiplier),
  };
}

export class CameraInputController {
  readonly #canvas: HTMLCanvasElement;
  readonly #options: CameraInputControllerOptions;
  readonly #pointers = new Map<number, PointerSample>();
  readonly #start = new Map<number, PointerSample>();
  readonly #previousTouchAction: string;
  #disposed = false;

  constructor(canvas: HTMLCanvasElement, options: CameraInputControllerOptions) {
    if (!canvas || !options?.frame || !options.emit) {
      throw new TypeError('Canvas, frame provider and CameraIntent sink are required.');
    }
    this.#canvas = canvas;
    this.#options = options;
    this.#previousTouchAction = canvas.style.touchAction;
    canvas.style.touchAction = 'none';
    canvas.addEventListener('pointerdown', this.#pointerDown);
    canvas.addEventListener('pointermove', this.#pointerMove);
    canvas.addEventListener('pointerup', this.#pointerUp);
    canvas.addEventListener('pointercancel', this.#pointerUp);
    canvas.addEventListener('wheel', this.#wheel, { passive: false });
  }

  dispose(): void {
    if (this.#disposed) return;
    this.#canvas.removeEventListener('pointerdown', this.#pointerDown);
    this.#canvas.removeEventListener('pointermove', this.#pointerMove);
    this.#canvas.removeEventListener('pointerup', this.#pointerUp);
    this.#canvas.removeEventListener('pointercancel', this.#pointerUp);
    this.#canvas.removeEventListener('wheel', this.#wheel);
    this.#canvas.style.touchAction = this.#previousTouchAction;
    this.#pointers.clear();
    this.#start.clear();
    this.#disposed = true;
  }

  readonly #pointerDown = (event: PointerEvent): void => {
    const sample = { x: event.clientX, y: event.clientY };
    this.#pointers.set(event.pointerId, sample);
    this.#start.set(event.pointerId, sample);
    this.#canvas.setPointerCapture(event.pointerId);
  };

  readonly #pointerMove = (event: PointerEvent): void => {
    const previous = this.#pointers.get(event.pointerId);
    if (!previous) return;
    const before = new Map(this.#pointers);
    const current = { x: event.clientX, y: event.clientY };
    this.#pointers.set(event.pointerId, current);
    const frame = this.#options.frame();
    const pointers = [...this.#pointers.entries()];

    if (pointers.length >= 2) {
      const [first, second] = pointers;
      if (!first || !second) return;
      const firstBefore = before.get(first[0]);
      const secondBefore = before.get(second[0]);
      if (!firstBefore || !secondBefore) return;
      const previousMidX = (firstBefore.x + secondBefore.x) / 2;
      const previousMidY = (firstBefore.y + secondBefore.y) / 2;
      const currentMidX = (first[1].x + second[1].x) / 2;
      const currentMidY = (first[1].y + second[1].y) / 2;
      const previousDistance = Math.hypot(
        firstBefore.x - secondBefore.x,
        firstBefore.y - secondBefore.y,
      );
      const currentDistance = Math.hypot(
        first[1].x - second[1].x,
        first[1].y - second[1].y,
      );
      const pan = panIntentFromScreenDrag(
        frame,
        currentMidX - previousMidX,
        currentMidY - previousMidY,
      );
      this.#options.emit(pan);
      const pinchPixels = currentDistance - previousDistance;
      if (Math.abs(pinchPixels) > 0.01) {
        this.#options.emit(dollyIntentFromPixels(frame, pinchPixels, 1.4));
      }
      return;
    }

    const deltaX = current.x - previous.x;
    const deltaY = current.y - previous.y;
    if (event.pointerType === 'mouse' && event.shiftKey) {
      this.#options.emit(panIntentFromScreenDrag(frame, deltaX, deltaY));
      return;
    }
    for (const intent of orbitIntentsFromScreenDrag(
      frame,
      deltaX,
      deltaY,
      this.#options.orbitRadiansPerPixel ?? 0.008,
    )) {
      this.#options.emit(intent);
    }
  };

  readonly #pointerUp = (event: PointerEvent): void => {
    const start = this.#start.get(event.pointerId);
    const current = this.#pointers.get(event.pointerId);
    if (
      start &&
      current &&
      this.#pointers.size === 1 &&
      Math.hypot(current.x - start.x, current.y - start.y) < 5
    ) {
      this.#options.onTap?.(event.clientX, event.clientY);
    }
    this.#pointers.delete(event.pointerId);
    this.#start.delete(event.pointerId);
    if (this.#canvas.hasPointerCapture(event.pointerId)) {
      this.#canvas.releasePointerCapture(event.pointerId);
    }
  };

  readonly #wheel = (event: WheelEvent): void => {
    event.preventDefault();
    const frame = this.#options.frame();
    this.#options.emit(
      dollyIntentFromPixels(
        frame,
        -event.deltaY,
        this.#options.wheelDollyScale ?? 0.5,
      ),
    );
  };
}

export function combineDirectionsAsOffset(
  first: PatientSpaceDirection,
  firstMillimetres: number,
  second: PatientSpaceDirection,
  secondMillimetres: number,
) {
  const a = first.value;
  const b = second.value;
  return patientSpaceVector(
    a.x * firstMillimetres + b.x * secondMillimetres,
    a.y * firstMillimetres + b.y * secondMillimetres,
    a.z * firstMillimetres + b.z * secondMillimetres,
  );
}
