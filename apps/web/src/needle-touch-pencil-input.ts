import {
  needleAdvanceIntent,
  needleRetractIntent,
  needleRotationIntent,
  needleTranslationIntent,
  type NeedleControlIntent,
} from '@procedural-human/instruments';

export type TouchPencilNeedleControlMode =
  | 'translate'
  | 'rotate'
  | 'advance';

export interface TouchPencilNeedleInputOptions {
  readonly emit: (intent: NeedleControlIntent) => void;
  readonly mode?: TouchPencilNeedleControlMode;
}

const touchPencilModes = new Set<TouchPencilNeedleControlMode>([
  'translate',
  'rotate',
  'advance',
]);

function clampAxis(value: number): number {
  return Math.max(-1, Math.min(1, value));
}

function clampMagnitude(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function isInteractiveControl(target: EventTarget | null): boolean {
  return (
    target instanceof Element &&
    target.closest('button, input, select, textarea, a') !== null
  );
}

function isTouchOrPencil(event: PointerEvent): boolean {
  return event.pointerType === 'touch' || event.pointerType === 'pen';
}

/**
 * Browser-only touch/Apple Pencil adapter. Pressure is intentionally ignored.
 * A selected UI mode maps one primary pointer drag to normalized domain intent.
 */
export class TouchPencilNeedleInputAdapter {
  readonly #element: HTMLElement;
  readonly #emit: (intent: NeedleControlIntent) => void;
  #mode: TouchPencilNeedleControlMode;
  #pointerId: number | null = null;
  #lastX = 0;
  #lastY = 0;

  constructor(element: HTMLElement, options: TouchPencilNeedleInputOptions) {
    this.#element = element;
    this.#emit = options.emit;
    this.#mode = options.mode ?? 'translate';
    this.setMode(this.#mode);
    element.addEventListener('pointerdown', this.#onPointerDown);
    element.addEventListener('pointermove', this.#onPointerMove);
    element.addEventListener('pointerup', this.#onPointerUp);
    element.addEventListener('pointercancel', this.#onPointerUp);
  }

  setMode(mode: TouchPencilNeedleControlMode): void {
    if (!touchPencilModes.has(mode)) {
      throw new TypeError('Unknown touch/Pencil needle control mode.');
    }
    this.#mode = mode;
  }

  dispose(): void {
    this.#element.removeEventListener('pointerdown', this.#onPointerDown);
    this.#element.removeEventListener('pointermove', this.#onPointerMove);
    this.#element.removeEventListener('pointerup', this.#onPointerUp);
    this.#element.removeEventListener('pointercancel', this.#onPointerUp);
    this.#pointerId = null;
  }

  readonly #onPointerDown = (event: PointerEvent): void => {
    if (
      !isTouchOrPencil(event) ||
      !event.isPrimary ||
      isInteractiveControl(event.target)
    ) {
      return;
    }
    this.#pointerId = event.pointerId;
    this.#lastX = event.clientX;
    this.#lastY = event.clientY;
    this.#element.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  readonly #onPointerMove = (event: PointerEvent): void => {
    if (
      !isTouchOrPencil(event) ||
      !event.isPrimary ||
      this.#pointerId !== event.pointerId
    ) {
      return;
    }
    const rect = this.#element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const dx = clampAxis((event.clientX - this.#lastX) / rect.width);
    const dy = clampAxis((event.clientY - this.#lastY) / rect.height);
    this.#lastX = event.clientX;
    this.#lastY = event.clientY;

    if (this.#mode === 'translate') {
      if (dx === 0 && dy === 0) return;
      this.#emit(needleTranslationIntent(dx, -dy));
    } else if (this.#mode === 'rotate') {
      if (dx === 0 && dy === 0) return;
      this.#emit(needleRotationIntent(dx, dy));
    } else {
      if (dy === 0) return;
      const amount = clampMagnitude(Math.abs(dy));
      this.#emit(
        dy < 0 ? needleAdvanceIntent(amount) : needleRetractIntent(amount),
      );
    }
    event.preventDefault();
  };

  readonly #onPointerUp = (event: PointerEvent): void => {
    if (this.#pointerId !== event.pointerId) return;
    if (this.#element.hasPointerCapture(event.pointerId)) {
      this.#element.releasePointerCapture(event.pointerId);
    }
    this.#pointerId = null;
  };
}
