import type { PatientId, StructureId } from '@procedural-human/core';
import type {
  PatientSpacePoint,
  PatientSpaceVector,
} from '@procedural-human/math';
import type { Angle, Length } from '@procedural-human/units';

export { PatientRenderTransform } from './coordinates.js';
export type { PatientRenderTransformConfig } from './coordinates.js';

declare const opacityBrand: unique symbol;

/** Dimensionless presentation alpha: 0 is transparent; 1 is opaque. */
export type Opacity = number & { readonly [opacityBrand]: 'Opacity' };

/** Reject invalid input rather than silently clamping it. */
export function opacity(value: number): Opacity {
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    throw new RangeError('Opacity must be a finite number between 0 and 1.');
  }
  return value as Opacity;
}

export interface StructureVisibility {
  readonly structureId: StructureId;
  readonly visible: boolean;
}

export interface StructureOpacity {
  readonly structureId: StructureId;
  readonly opacity: Opacity;
}

/** Single semantic selection in the API's patient; null explicitly clears it. */
export type StructureSelection = StructureId | null;

/**
 * Patient-space plane through origin (mm), with a finite unit normal.
 * Keep points p for which dot(normal, p - origin) >= 0, including the plane.
 * This clips presentation only; it never cuts anatomy or changes queries.
 */
export interface PatientClippingPlane {
  readonly origin: PatientSpacePoint;
  readonly normal: PatientSpaceVector;
}

/** Device-independent intents; all spatial values are in Patient Space. */
export type CameraIntent =
  | {
      readonly type: 'orbit';
      readonly pivot: PatientSpacePoint;
      /** Finite unit axis; positive angle follows the right-hand rule. */
      readonly axis: PatientSpaceVector;
      readonly angle: Angle;
    }
  | {
      readonly type: 'pan';
      /** Translate camera and its target by this displacement in mm. */
      readonly offset: PatientSpaceVector;
    }
  | {
      readonly type: 'dolly';
      /** Signed travel along the viewing direction in mm; positive is forward. */
      readonly distance: Length;
    }
  | {
      readonly type: 'focus';
      /** Aim at this point without changing camera position. */
      readonly target: PatientSpacePoint;
    };

/**
 * Presentation-only port bound to one patient by the composition root.
 * Structure IDs resolve within that patient, across all render representations.
 * Unknown IDs and invalid spatial inputs must fail explicitly in adapters.
 */
export interface RenderingPresentationApi {
  readonly patientId: PatientId;
  setVisibility(visibility: StructureVisibility): void;
  setOpacity(opacity: StructureOpacity): void;
  setSelection(selection: StructureSelection): void;
  /** Replace the active plane; null disables clipping. */
  setClippingPlane(plane: PatientClippingPlane | null): void;
  applyCameraIntent(intent: CameraIntent): void;
}
