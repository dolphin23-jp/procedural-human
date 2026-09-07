import {
  createVolumeImagingFrame,
  type VolumeImagingFrame,
} from '@procedural-human/imaging-core';

export type CornerstoneScalarData =
  | Uint8Array
  | Int16Array
  | Uint16Array
  | Float32Array;

export interface ImagingVolumeProvenance {
  readonly sourceClass: string;
  readonly sourceIdentifier: string;
  readonly validationLevel: string;
  readonly notes: string;
}

export interface ImagingVolumeSource {
  readonly id: string;
  readonly frameOfReferenceUID: string;
  readonly frame: VolumeImagingFrame;
  readonly scalarData: CornerstoneScalarData;
  readonly display: {
    readonly windowCenter: number;
    readonly windowWidth: number;
  };
  readonly provenance: ImagingVolumeProvenance;
}

function nonempty(value: string, name: string): void {
  if (typeof value !== 'string' || !value.trim()) {
    throw new TypeError(`${name} must be a nonempty string.`);
  }
}

function isSupportedScalarData(value: unknown): value is CornerstoneScalarData {
  return (
    value instanceof Uint8Array ||
    value instanceof Int16Array ||
    value instanceof Uint16Array ||
    value instanceof Float32Array
  );
}

/**
 * Validates the neutral project-side description before any Cornerstone object
 * is created. Pixel buffers remain ordinary typed arrays; Cornerstone types do
 * not cross this boundary.
 */
export function validateImagingVolumeSource(
  source: ImagingVolumeSource,
): ImagingVolumeSource {
  if (!source) {
    throw new TypeError('Imaging volume source is required.');
  }
  nonempty(source.id, 'Imaging volume source id');
  nonempty(source.frameOfReferenceUID, 'Frame of reference UID');
  nonempty(source.provenance?.sourceClass, 'Source class');
  nonempty(source.provenance?.sourceIdentifier, 'Source identifier');
  nonempty(source.provenance?.validationLevel, 'Validation level');
  nonempty(source.provenance?.notes, 'Validation notes');

  const frame = createVolumeImagingFrame(source.frame);
  if (!isSupportedScalarData(source.scalarData)) {
    throw new TypeError('Unsupported scalar buffer type.');
  }

  const expectedSamples =
    frame.dimensions.i * frame.dimensions.j * frame.dimensions.k;
  if (
    !Number.isSafeInteger(expectedSamples) ||
    source.scalarData.length !== expectedSamples
  ) {
    throw new RangeError(
      'Scalar buffer length must exactly match the declared volume dimensions.',
    );
  }

  const { windowCenter, windowWidth } = source.display ?? {};
  if (
    !Number.isFinite(windowCenter) ||
    !Number.isFinite(windowWidth) ||
    windowWidth <= 0
  ) {
    throw new RangeError(
      'Display window center must be finite and width must be positive.',
    );
  }

  return Object.freeze({
    id: source.id,
    frameOfReferenceUID: source.frameOfReferenceUID,
    frame,
    scalarData: source.scalarData,
    display: Object.freeze({ windowCenter, windowWidth }),
    provenance: Object.freeze({ ...source.provenance }),
  });
}

export function copyScalarData(
  scalarData: CornerstoneScalarData,
): CornerstoneScalarData {
  return scalarData.slice() as CornerstoneScalarData;
}
