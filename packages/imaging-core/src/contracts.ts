import type { AssetId, PatientId } from '@procedural-human/core';
import type {
  PatientSpaceDirection,
  PatientSpacePoint,
} from '@procedural-human/math';
import type { Length } from '@procedural-human/units';

export type ImagingSourceType = 'acquired' | 'synthetic' | 'hybrid';

/** Geometry of a single sampled 2D image, not an implied 3D volume. */
export interface PlanarImagingFrame {
  readonly kind: 'plane-2d';
  readonly indexConvention: 'zero-based-sample-centers';
  /** Center of sample (0,0), in the observation patient's space (mm). */
  readonly origin: PatientSpacePoint;
  /** Increasing column index within a row. Dimensionless patient direction. */
  readonly directionI: PatientSpaceDirection;
  /** Increasing row index within a column. Dimensionless patient direction. */
  readonly directionJ: PatientSpaceDirection;
  readonly spacing: { readonly i: Length; readonly j: Length };
  readonly dimensions: { readonly i: number; readonly j: number };
}

/** One regular orthogonal 3D lattice; never inferred from an irregular stack. */
export interface VolumeImagingFrame {
  readonly kind: 'volume-3d';
  readonly indexConvention: 'zero-based-sample-centers';
  /** Center of voxel (0,0,0), in the observation patient's space (mm). */
  readonly origin: PatientSpacePoint;
  readonly directionI: PatientSpaceDirection;
  readonly directionJ: PatientSpaceDirection;
  readonly directionK: PatientSpaceDirection;
  /** Sign of det[Di Dj Dk]; descending slice order may be left-handed. */
  readonly handedness: 'right' | 'left';
  /** Positive center-to-center spacing; k spacing is not slice thickness. */
  readonly spacing: {
    readonly i: Length;
    readonly j: Length;
    readonly k: Length;
  };
  readonly dimensions: {
    readonly i: number;
    readonly j: number;
    readonly k: number;
  };
}

export type ImagingFrame = PlanarImagingFrame | VolumeImagingFrame;

/** Oriented imaging plane; no clipping half-space, pixel size, or thickness. */
export interface PatientImagingPlane {
  readonly kind: 'patient-imaging-plane';
  readonly origin: PatientSpacePoint;
  readonly directionI: PatientSpaceDirection;
  readonly directionJ: PatientSpaceDirection;
  /** Derived as normalized Di cross Dj; not necessarily the volume's +k. */
  readonly normal: PatientSpaceDirection;
}

export interface ImagePixelCoordinate {
  readonly space: 'image-pixel';
  readonly i: number;
  readonly j: number;
}

/**
 * Runtime observation reference, not a new serialized manifest schema.
 * id/assetId/sourceType/registrationStatus correspond to patient-manifest v1.
 * assetId resolves source lineage, hashes and validation through asset manifests.
 * No source pixels, anatomy, or renderer objects are owned here.
 */
interface ObservationReference {
  readonly id: string;
  readonly patientId: PatientId;
  readonly assetId: AssetId;
  readonly sourceType: ImagingSourceType;
  /** Upstream registration identifier, null when unavailable. */
  readonly registrationId: string | null;
}

export type ImagingObservation = ObservationReference &
  (
    | {
        readonly registrationStatus: 'registered';
        /** Explicit geometry in this patient's space; may contain independent planes. */
        readonly frames: readonly ImagingFrame[];
      }
    | {
        readonly registrationStatus: 'unregistered' | 'unknown';
        /** Unknown registration must not provide fabricated patient geometry. */
        readonly frames: null;
      }
  );
