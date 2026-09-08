import {
  needleAdvanceIntent,
  needleRetractIntent,
  needleRotationIntent,
  needleTranslationIntent,
  type NeedleControlIntent,
} from '@procedural-human/instruments';

export interface MouseNeedleInputOptions {
  readonly emit: (intent: NeedleControlIntent) => void;
}

function clampAxis(value: number): number {
  return Math.max(-1, Math.min(1, value));
}

function clampMagnitude(value: number): number {
  return Math.max(0, Math.min(1, value));
}

/**
 * Browser-only mouse adapter. It emits normalized domain intents and never
 * reads or mutates NeedleInstance, anatomy, rendering, or procedure state.
 */
export class MouseNeedleInputAdapter {
  readonly #element: HTMLElement;
  readonly #emit: (intent: NeedleControlIntent) => void;
  #pointerId: number | null = null;
  #lastX = 0;
  #lastY = 0;

  constructor(element: HTMLElement, options: MouseNeedleInputOptions) {
    this.#element = element;
    this.#emit = options.emit;
    element.addEventListener('pointerdown', this.#onPointerDown);
    element.addEventListener('pointermove', this.#onPointerMove);
    element.addEventListener('pointerup', this.#onPointerUp);
    element.addEventListener('pointercancel', this.#onPointerUp);
    element.addEventListener('wheel', this.#onWheel, { passive: false });
  }

  dispose(): void {
    this.#element.removeEventListener('pointerdown', this.#onPointerDown);
    this.#element.removeEventListener('pointermove', this.#onPointerMove);
    this.#element.removeEventListener('pointerup', this.#onPointerUp);
    this.#element.removeEventListener('pointercancel', this.#onPointerUp);
    this.#element.removeEventListener('wheel', this.#onWheel);
    this.#pointerId = null;
  }

  readonly #onPointerDown = (event: PointerEvent): void => {
    if (event.pointerType !== 'mouse' || event.button !== 0) return;
    this.#pointerId = event.pointerId;
    this.#lastX = event.clientX;
    this.#lastY = event.clientY;
    this.#element.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  readonly #onPointerMove = (event: PointerEvent): void => {
    if (event.pointerType !== 'mouse' || this.#pointerId !== event.pointerId) {
      return;
    }
    const rect = this.#element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const dx = clampAxis((event.clientX - this.#lastX) / rect.width);
    const dy = clampAxis((event.clientY - this.#lastY) / rect.height);
    this.#lastX = event.clientX;
    this.#lastY = event.clientY;
    if (dx === 0 && dy === 0) return;

    this.#emit(
      event.shiftKey
        ? needleRotationIntent(dx, dy)
        : needleTranslationIntent(dx, -dy),
    );
    event.preventDefault();
  };

  readonly #onPointerUp = (event: PointerEvent): void => {
    if (this.#pointerId !== event.pointerId) return;
    if (this.#element.hasPointerCapture(event.pointerId)) {
      this.#element.releasePointerCapture(event.pointerId);
    }
    this.#pointerId = null;
  };

  readonly #onWheel = (event: WheelEvent): void => {
    if (event.deltaY === 0) return;
    const amount = clampMagnitude(Math.abs(event.deltaY) / 100);
    this.#emit(
      event.deltaY < 0
        ? needleAdvanceIntent(amount)
        : needleRetractIntent(amount),
    );
    event.preventDefault();
  };
}
