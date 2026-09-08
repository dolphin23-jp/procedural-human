import {
  ImagePatientTransform,
  IMAGE_BASIS_TOLERANCE,
  createPatientImagingPlane,
  type AxialImagingViewport,
  type AxialSliceState,
  type PatientImagingPlane,
  type PatientPlaneImagingViewport,
  type VolumeImagingFrame,
} from '@procedural-human/imaging-core';
import type { PatientClippingPlane } from '@procedural-human/rendering-core';

class ImagingPlaneCommandPreconditionError extends Error {}

export interface ImagingPlaneSyncState {
  /** Present only when the current image plane is one declared axial source slice. */
  readonly slice: AxialSliceState | null;
  /** Authoritative current image/3D plane, including arbitrary oblique MPR. */
  readonly plane: PatientImagingPlane | null;
  readonly clippingEnabled: boolean;
  readonly error: string | null;
}

/**
 * TASK-060/061/063 composition, not SimulationSession lifecycle (TASK-082).
 * Both ports and the explicit image frame must refer to the same Patient Space.
 * Commands are serialized; readback is the only committed plane. Rendering never
 * writes back to the image port, so acknowledgements cannot form a feedback loop.
 */
export class ImagingPlaneSynchronizer {
  readonly #image: AxialImagingViewport & PatientPlaneImagingViewport;
  readonly #render: {
    setClippingPlane(plane: PatientClippingPlane | null): void;
  };
  readonly #transform: ImagePatientTransform;
  readonly #changed: (state: ImagingPlaneSyncState) => void;
  #state: ImagingPlaneSyncState;
  #tail: Promise<void> = Promise.resolve();
  #disposed = false;

  constructor(options: {
    image: AxialImagingViewport & PatientPlaneImagingViewport;
    render: { setClippingPlane(plane: PatientClippingPlane | null): void };
    frame: VolumeImagingFrame;
    onChange: (state: ImagingPlaneSyncState) => void;
  }) {
    this.#image = options.image;
    this.#render = options.render;
    this.#transform = new ImagePatientTransform(options.frame);
    this.#changed = options.onChange;
    this.#state = Object.freeze({
      slice: null,
      plane: null,
      clippingEnabled: true,
      error: null,
    });
    this.#commitSlice(options.image.currentSlice);
  }

  get state(): ImagingPlaneSyncState {
    return this.#state;
  }

  setImageSlice(displayIndex: number): Promise<void> {
    return this.#enqueue(
      () => this.#image.setSlice(displayIndex),
      (slice) => this.#commitSlice(slice),
    );
  }

  scrollImage(delta: number): Promise<void> {
    return this.#enqueue(
      () => {
        if (!Number.isSafeInteger(delta))
          throw new ImagingPlaneCommandPreconditionError(
            'Slice delta must be an integer.',
          );
        const current = this.#state.slice;
        if (!current) {
          throw new ImagingPlaneCommandPreconditionError(
            'Axial scrolling is unavailable while an oblique image plane is active.',
          );
        }
        const index = current.displayIndex + delta;
        // Explicit UI navigation policy: stop at either end; never wrap.
        const bounded = Math.max(
          0,
          Math.min(this.#transform.frame.dimensions.k - 1, index),
        );
        return this.#image.setSlice(bounded);
      },
      (slice) => this.#commitSlice(slice),
    );
  }

  async setPatientPlane(plane: PatientImagingPlane): Promise<void> {
    // Copy now so callers cannot mutate a queued request.
    const copy = createPatientImagingPlane(plane);
    if (
      plane.kind !== 'patient-imaging-plane' ||
      !plane.normal ||
      ['x', 'y', 'z'].some((axis) => {
        const key = axis as 'x' | 'y' | 'z';
        return (
          !Number.isFinite(plane.normal.value[key]) ||
          Math.abs(plane.normal.value[key] - copy.normal.value[key]) >
            IMAGE_BASIS_TOLERANCE
        );
      })
    ) {
      return Promise.reject(
        new TypeError('Imaging plane normal must match its basis.'),
      );
    }
    return this.#enqueue(
      () => this.#image.setImagingPlane(copy),
      (readback) => this.#commitPlane(readback),
    );
  }

  /** Touch-friendly 3D control for one declared source sample plane. */
  setPlaneAtVoxelK(k: number): Promise<void> {
    if (
      !Number.isSafeInteger(k) ||
      k < 0 ||
      k >= this.#transform.frame.dimensions.k
    ) {
      return Promise.reject(
        new RangeError('3D plane voxel k is outside the source volume.'),
      );
    }
    const plane = this.#transform.planeAtK(k);
    return this.#enqueue(
      () => this.#image.setPatientPlane(plane),
      (slice) => this.#commitSlice(slice),
    );
  }

  setClippingEnabled(enabled: boolean): void {
    this.#assertAlive();
    this.#render.setClippingPlane(enabled ? (this.#state.plane ?? null) : null);
    this.#state = Object.freeze({ ...this.#state, clippingEnabled: enabled });
    this.#changed(this.#state);
  }

  dispose(): void {
    if (this.#disposed) return;
    this.#disposed = true;
    this.#render.setClippingPlane(null);
  }

  #enqueue<T>(
    command: () => Promise<T>,
    commit: (value: T) => void,
  ): Promise<void> {
    const operation = this.#tail.then(async () => {
      this.#assertAlive();
      try {
        const value = await command();
        this.#assertAlive();
        commit(value);
      } catch (error) {
        if (
          !this.#disposed &&
          !(error instanceof ImagingPlaneCommandPreconditionError)
        ) {
          // A failed readback may follow a camera mutation. Never leave a stale
          // 3D plane presented as synchronized with that image.
          this.#render.setClippingPlane(null);
          this.#state = Object.freeze({
            ...this.#state,
            slice: null,
            plane: null,
            error:
              error instanceof Error
                ? error.message
                : 'Image/3D synchronization failed.',
          });
          this.#changed(this.#state);
        }
        throw error;
      }
    });
    // Keep the queue usable after rejection; the caller still receives the error.
    this.#tail = operation.then(
      () => undefined,
      () => undefined,
    );
    return operation;
  }

  #commitSlice(slice: AxialSliceState): void {
    const plane = createPatientImagingPlane(slice.plane);
    const copy = Object.freeze({ ...slice, plane });
    this.#render.setClippingPlane(this.#state.clippingEnabled ? plane : null);
    this.#state = Object.freeze({
      ...this.#state,
      slice: copy,
      plane,
      error: null,
    });
    this.#changed(this.#state);
  }

  #commitPlane(readback: PatientImagingPlane): void {
    const plane = createPatientImagingPlane(readback);
    this.#render.setClippingPlane(this.#state.clippingEnabled ? plane : null);
    this.#state = Object.freeze({
      ...this.#state,
      slice: null,
      plane,
      error: null,
    });
    this.#changed(this.#state);
  }

  #assertAlive(): void {
    if (this.#disposed)
      throw new Error('Imaging plane synchronizer has been disposed.');
  }
}
