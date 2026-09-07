import {
  Enums,
  RenderingEngine,
  cache,
  init,
  isCornerstoneInitialized,
  setVolumesForViewports,
  utilities,
  volumeLoader,
  type Types,
  type VolumeViewport,
} from '@cornerstonejs/core';
import {
  ImagePatientTransform,
  type PatientImagingPlane,
} from '@procedural-human/imaging-core';
import { patientSpacePoint } from '@procedural-human/math';
import { toMillimetres } from '@procedural-human/units';
import {
  assertPatientAxialFrame,
  PATIENT_AXIAL_TOLERANCE,
  axialVoxelKForPatientPlane,
  createAxialSliceStateFromPatientPoint,
  type AxialSliceState,
} from './axial.js';
import {
  copyScalarData,
  validateImagingVolumeSource,
  type ImagingVolumeSource,
} from './source.js';

let nextInstanceId = 0;

function ensureCornerstoneInitialized(): void {
  if (!isCornerstoneInitialized()) {
    init();
  }
}

function volumeMetadata(source: ImagingVolumeSource): Types.Metadata {
  const frame = source.frame;
  return {
    BitsAllocated: 16,
    BitsStored: 16,
    SamplesPerPixel: 1,
    HighBit: 15,
    PhotometricInterpretation: 'MONOCHROME2',
    PixelRepresentation: 0,
    Modality: 'OT',
    SeriesInstanceUID: source.id,
    ImageOrientationPatient: [
      frame.directionI.value.x,
      frame.directionI.value.y,
      frame.directionI.value.z,
      frame.directionJ.value.x,
      frame.directionJ.value.y,
      frame.directionJ.value.z,
    ],
    PixelSpacing: [
      toMillimetres(frame.spacing.j),
      toMillimetres(frame.spacing.i),
    ],
    FrameOfReferenceUID: source.frameOfReferenceUID,
    Columns: frame.dimensions.i,
    Rows: frame.dimensions.j,
    voiLut: [
      {
        windowCenter: source.display.windowCenter,
        windowWidth: source.display.windowWidth,
      },
    ],
    VOILUTFunction: 'LINEAR',
  };
}

function removeLocalVolume(volumeId: string): void {
  const volume = cache.getVolume(volumeId);
  const imageIds = volume?.imageIds ? [...volume.imageIds] : [];
  if (volume) {
    cache.removeVolumeLoadObject(volumeId);
  }
  for (const imageId of imageIds) {
    if (cache.getImageLoadObject(imageId)) {
      cache.removeImageLoadObject(imageId, { force: true });
    }
  }
}

/**
 * Browser adapter for TASK-058/059. Cornerstone-specific objects stay private;
 * callers receive only Patient Space slice state.
 */
export class CornerstoneAxialVolumeViewer {
  readonly #element: HTMLDivElement;
  readonly #source: ImagingVolumeSource;
  readonly #renderingEngine: RenderingEngine;
  readonly #viewportId: string;
  readonly #volumeId: string;
  #currentSlice: AxialSliceState | null = null;
  #disposed = false;

  private constructor(
    element: HTMLDivElement,
    source: ImagingVolumeSource,
    renderingEngine: RenderingEngine,
    viewportId: string,
    volumeId: string,
  ) {
    this.#element = element;
    this.#source = source;
    this.#renderingEngine = renderingEngine;
    this.#viewportId = viewportId;
    this.#volumeId = volumeId;
  }

  static async create(
    element: HTMLDivElement,
    inputSource: ImagingVolumeSource,
  ): Promise<CornerstoneAxialVolumeViewer> {
    if (!(element instanceof HTMLDivElement)) {
      throw new TypeError('Cornerstone viewer requires an HTMLDivElement.');
    }
    const source = validateImagingVolumeSource(inputSource);
    assertPatientAxialFrame(source.frame);
    ensureCornerstoneInitialized();

    const instanceId = ++nextInstanceId;
    const renderingEngineId = `ph-imaging-engine-${instanceId}`;
    const viewportId = `ph-axial-viewport-${instanceId}`;
    const volumeId = `ph-local-volume-${instanceId}`;
    const renderingEngine = new RenderingEngine(renderingEngineId);

    try {
      const frame = source.frame;
      volumeLoader.createLocalVolume(volumeId, {
        metadata: volumeMetadata(source),
        dimensions: [
          frame.dimensions.i,
          frame.dimensions.j,
          frame.dimensions.k,
        ],
        spacing: [
          toMillimetres(frame.spacing.i),
          toMillimetres(frame.spacing.j),
          toMillimetres(frame.spacing.k),
        ],
        origin: [
          frame.origin.value.x,
          frame.origin.value.y,
          frame.origin.value.z,
        ],
        direction: [
          frame.directionI.value.x,
          frame.directionI.value.y,
          frame.directionI.value.z,
          frame.directionJ.value.x,
          frame.directionJ.value.y,
          frame.directionJ.value.z,
          frame.directionK.value.x,
          frame.directionK.value.y,
          frame.directionK.value.z,
        ],
        scalarData: copyScalarData(source.scalarData),
      });

      renderingEngine.enableElement({
        viewportId,
        element,
        type: Enums.ViewportType.ORTHOGRAPHIC,
        defaultOptions: {
          orientation: Enums.OrientationAxis.AXIAL,
          background: [0, 0, 0],
        },
      });

      await setVolumesForViewports(
        renderingEngine,
        [{ volumeId }],
        [viewportId],
      );

      const viewer = new CornerstoneAxialVolumeViewer(
        element,
        source,
        renderingEngine,
        viewportId,
        volumeId,
      );
      const viewport = viewer.#viewport();
      const cornerstoneSliceCount = viewport.getNumberOfSlices();
      if (cornerstoneSliceCount !== source.frame.dimensions.k) {
        throw new Error(
          'Cornerstone axial slice count does not match the registered source volume.',
        );
      }

      const initialDisplayIndex = Math.floor((cornerstoneSliceCount - 1) / 2);
      await viewer.setSlice(initialDisplayIndex);
      return viewer;
    } catch (error) {
      renderingEngine.destroy();
      removeLocalVolume(volumeId);
      throw error;
    }
  }

  get sliceCount(): number {
    return this.#source.frame.dimensions.k;
  }

  get currentSlice(): AxialSliceState {
    if (!this.#currentSlice) {
      throw new Error('Axial viewer has not established a slice yet.');
    }
    return this.#currentSlice;
  }

  get source(): ImagingVolumeSource {
    return this.#source;
  }

  async setSlice(displayIndex: number): Promise<AxialSliceState> {
    this.#assertAlive();
    if (
      !Number.isSafeInteger(displayIndex) ||
      displayIndex < 0 ||
      displayIndex >= this.sliceCount
    ) {
      throw new RangeError(
        'Requested axial display index is outside the volume.',
      );
    }

    await utilities.jumpToSlice(this.#element, {
      imageIndex: displayIndex,
      volumeId: this.#volumeId,
    });
    this.#assertAlive();
    const state = this.#readCurrentSlice();
    if (state.displayIndex !== displayIndex) {
      throw new Error(
        'Cornerstone did not reach the requested axial display slice.',
      );
    }
    this.#currentSlice = state;
    return state;
  }

  /** Translate along the axial normal, preserving pan, zoom and camera distance. */
  async setPatientPlane(plane: PatientImagingPlane): Promise<AxialSliceState> {
    this.#assertAlive();
    const targetK = axialVoxelKForPatientPlane(this.#source.frame, plane);
    const viewport = this.#viewport();
    const { focalPoint, position } = viewport.getCamera();
    if (!focalPoint || !position) {
      throw new Error('Cornerstone axial viewport camera is unavailable.');
    }
    const target = new ImagePatientTransform(this.#source.frame).planeAtK(
      targetK,
    );
    const dz = target.origin.value.z - focalPoint[2];
    viewport.setCamera({
      focalPoint: [focalPoint[0], focalPoint[1], focalPoint[2] + dz],
      position: [position[0], position[1], position[2] + dz],
    });
    viewport.render();
    const state = this.#readCurrentSlice();
    if (state.voxelK !== targetK) {
      throw new Error(
        'Cornerstone did not reach the requested Patient Space plane.',
      );
    }
    this.#currentSlice = state;
    return state;
  }

  resize(): void {
    this.#assertAlive();
    // The second argument is keepCamera, preserving the synchronized plane.
    this.#renderingEngine.resize(true, true);
  }

  dispose(): void {
    if (this.#disposed) {
      return;
    }
    this.#disposed = true;
    this.#renderingEngine.destroy();
    removeLocalVolume(this.#volumeId);
  }

  #viewport(): VolumeViewport {
    return this.#renderingEngine.getViewport<VolumeViewport>(this.#viewportId);
  }

  #readCurrentSlice(): AxialSliceState {
    const viewport = this.#viewport();
    const { focalPoint, viewPlaneNormal } = viewport.getCamera();
    if (
      !viewPlaneNormal ||
      !viewPlaneNormal.every(Number.isFinite) ||
      Math.abs(viewPlaneNormal[0]) > PATIENT_AXIAL_TOLERANCE ||
      Math.abs(viewPlaneNormal[1]) > PATIENT_AXIAL_TOLERANCE ||
      Math.abs(Math.abs(viewPlaneNormal[2]) - 1) > PATIENT_AXIAL_TOLERANCE
    ) {
      throw new Error('Cornerstone viewport is no longer patient-axial.');
    }
    if (!focalPoint) {
      throw new Error('Cornerstone axial viewport has no focal point.');
    }
    return createAxialSliceStateFromPatientPoint(
      this.#source.frame,
      viewport.getSliceIndex(),
      patientSpacePoint(focalPoint[0], focalPoint[1], focalPoint[2]),
    );
  }

  #assertAlive(): void {
    if (this.#disposed) {
      throw new Error('Cornerstone axial viewer has been disposed.');
    }
  }
}
