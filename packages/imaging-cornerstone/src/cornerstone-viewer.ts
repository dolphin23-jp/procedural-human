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
  axialVoxelKForPatientPlane,
  createAxialSliceStateFromPatientPoint,
  type AxialSliceState,
} from './axial.js';
import {
  assertPatientPlaneOrientationEquivalent,
  assertPatientPlanesEquivalent,
  patientPlaneFromCornerstoneCamera,
  patientPlaneToCornerstoneCamera,
} from './plane.js';
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
 * Browser adapter for TASK-058/059 and TASK-063. Cornerstone-specific objects
 * stay private; callers receive only Patient Space image state.
 */
export class CornerstoneAxialVolumeViewer {
  readonly #element: HTMLDivElement;
  readonly #source: ImagingVolumeSource;
  readonly #transform: ImagePatientTransform;
  readonly #renderingEngine: RenderingEngine;
  readonly #viewportId: string;
  readonly #volumeId: string;
  #currentSlice: AxialSliceState | null = null;
  #currentPlane: PatientImagingPlane | null = null;
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
    this.#transform = new ImagePatientTransform(source.frame);
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
      throw new Error(
        'The current viewport plane is oblique and has no axial source-slice state.',
      );
    }
    return this.#currentSlice;
  }

  get currentPlane(): PatientImagingPlane {
    if (!this.#currentPlane) {
      throw new Error('Imaging viewer has not established a plane yet.');
    }
    return this.#currentPlane;
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

    // An oblique viewport must return to the declared source-plane orientation
    // before display-index navigation has axial source-slice meaning.
    this.#setOrientation(this.#transform.planeAtK(0));
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
    this.#currentPlane = state.plane;
    return state;
  }

  /** Move to one declared axial source plane for TASK-061 compatibility. */
  async setPatientPlane(plane: PatientImagingPlane): Promise<AxialSliceState> {
    this.#assertAlive();
    const targetK = axialVoxelKForPatientPlane(this.#source.frame, plane);
    const target = this.#transform.planeAtK(targetK);
    this.#moveCameraToPlane(target);
    const state = this.#readCurrentSlice();
    if (state.voxelK !== targetK) {
      throw new Error(
        'Cornerstone did not reach the requested Patient Space axial plane.',
      );
    }
    this.#currentSlice = state;
    this.#currentPlane = state.plane;
    return state;
  }

  /**
   * TASK-063 arbitrary MPR. No source voxel-k/display-index is fabricated for
   * an oblique section. The actual camera plane is read back and verified.
   */
  async setImagingPlane(
    plane: PatientImagingPlane,
  ): Promise<PatientImagingPlane> {
    this.#assertAlive();
    this.#moveCameraToPlane(plane);
    this.#assertAlive();
    const readback = this.#readCurrentPlane();
    assertPatientPlanesEquivalent(plane, readback);
    this.#currentSlice = null;
    this.#currentPlane = readback;
    return readback;
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

  #setOrientation(plane: PatientImagingPlane): void {
    const viewport = this.#viewport();
    viewport.setCamera(patientPlaneToCornerstoneCamera(plane));
    viewport.render();
  }

  #moveCameraToPlane(plane: PatientImagingPlane): void {
    const viewport = this.#viewport();
    const camera = viewport.getCamera();
    const { focalPoint, position } = camera;
    if (!focalPoint || !position) {
      throw new Error('Cornerstone viewport camera is unavailable.');
    }
    const distance = Math.hypot(
      position[0] - focalPoint[0],
      position[1] - focalPoint[1],
      position[2] - focalPoint[2],
    );
    if (!Number.isFinite(distance) || distance <= Number.EPSILON) {
      throw new Error('Cornerstone viewport camera distance is invalid.');
    }

    const target = patientPlaneToCornerstoneCamera(plane);
    const origin = plane.origin.value;
    viewport.setCamera({
      ...target,
      focalPoint: [origin.x, origin.y, origin.z],
      position: [
        origin.x + target.viewPlaneNormal[0] * distance,
        origin.y + target.viewPlaneNormal[1] * distance,
        origin.z + target.viewPlaneNormal[2] * distance,
      ],
    });
    viewport.render();
  }

  #readCurrentPlane(): PatientImagingPlane {
    const { focalPoint, viewPlaneNormal, viewUp } =
      this.#viewport().getCamera();
    if (!focalPoint || !viewPlaneNormal || !viewUp) {
      throw new Error('Cornerstone viewport camera plane is unavailable.');
    }
    return patientPlaneFromCornerstoneCamera(
      [focalPoint[0], focalPoint[1], focalPoint[2]],
      [viewPlaneNormal[0], viewPlaneNormal[1], viewPlaneNormal[2]],
      [viewUp[0], viewUp[1], viewUp[2]],
    );
  }

  #readCurrentSlice(): AxialSliceState {
    const viewport = this.#viewport();
    const plane = this.#readCurrentPlane();
    assertPatientPlaneOrientationEquivalent(
      this.#transform.planeAtK(0),
      plane,
    );
    const focalPoint = plane.origin.value;
    return createAxialSliceStateFromPatientPoint(
      this.#source.frame,
      viewport.getSliceIndex(),
      patientSpacePoint(focalPoint.x, focalPoint.y, focalPoint.z),
    );
  }

  #assertAlive(): void {
    if (this.#disposed) {
      throw new Error('Cornerstone imaging viewer has been disposed.');
    }
  }
}
