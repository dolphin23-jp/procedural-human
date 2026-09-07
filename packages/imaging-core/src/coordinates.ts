import {
  imageVoxelCoordinate,
  patientSpacePoint,
  type ImageVoxelCoordinate,
  type PatientSpacePoint,
  type Vec3,
} from '@procedural-human/math';
import { toMillimetres } from '@procedural-human/units';
import type {
  ImagePixelCoordinate,
  PatientImagingPlane,
  PlanarImagingFrame,
  VolumeImagingFrame,
} from './contracts.js';
import {
  checkedPoint,
  createPatientImagingPlane,
  createPlanarImagingFrame,
  createVolumeImagingFrame,
  cross,
  dot,
  finite,
  IMAGE_PLANE_TOLERANCE_MM,
} from './geometry.js';

function delta(point: PatientSpacePoint, origin: PatientSpacePoint): Vec3 {
  checkedPoint(point);
  const value = {
    x: point.value.x - origin.value.x,
    y: point.value.y - origin.value.y,
    z: point.value.z - origin.value.z,
  };
  finite([value.x, value.y, value.z]);
  return value;
}

/** Continuous sample-center coordinates, deliberately not clamped to a buffer. */
export function imagePixelCoordinate(
  i: number,
  j: number,
): ImagePixelCoordinate {
  finite([i, j]);
  return { space: 'image-pixel', i, j };
}

/** Image <-> Patient math only. Configuration is validated, copied and frozen. */
export class ImagePatientTransform {
  readonly frame: VolumeImagingFrame;
  readonly #dualI: Vec3;
  readonly #dualJ: Vec3;
  readonly #dualK: Vec3;
  readonly #determinant: number;

  constructor(frame: VolumeImagingFrame) {
    this.frame = createVolumeImagingFrame(frame);
    const { directionI: i, directionJ: j, directionK: k } = this.frame;
    this.#dualI = cross(j.value, k.value);
    this.#dualJ = cross(k.value, i.value);
    this.#dualK = cross(i.value, j.value);
    this.#determinant = dot(i.value, this.#dualI);
    Object.freeze(this);
  }
  voxelToPatient(voxel: ImageVoxelCoordinate): PatientSpacePoint {
    if (!voxel || voxel.space !== 'image-voxel')
      throw new TypeError('Expected image-voxel coordinate.');
    finite([voxel.i, voxel.j, voxel.k]);
    const f = this.frame;
    const i = voxel.i * toMillimetres(f.spacing.i);
    const j = voxel.j * toMillimetres(f.spacing.j);
    const k = voxel.k * toMillimetres(f.spacing.k);
    finite([i, j, k]);
    return checkedPoint(
      patientSpacePoint(
        f.origin.value.x +
          i * f.directionI.value.x +
          j * f.directionJ.value.x +
          k * f.directionK.value.x,
        f.origin.value.y +
          i * f.directionI.value.y +
          j * f.directionJ.value.y +
          k * f.directionK.value.y,
        f.origin.value.z +
          i * f.directionI.value.z +
          j * f.directionJ.value.z +
          k * f.directionK.value.z,
      ),
    );
  }
  patientToVoxel(point: PatientSpacePoint): ImageVoxelCoordinate {
    const v = delta(point, this.frame.origin);
    // True inverse of the supplied basis, including accepted rounding residuals.
    // Transpose alone is only exact for an exactly orthonormal basis.
    const i =
      dot(v, this.#dualI) /
      this.#determinant /
      toMillimetres(this.frame.spacing.i);
    const j =
      dot(v, this.#dualJ) /
      this.#determinant /
      toMillimetres(this.frame.spacing.j);
    const k =
      dot(v, this.#dualK) /
      this.#determinant /
      toMillimetres(this.frame.spacing.k);
    finite([i, j, k]);
    return imageVoxelCoordinate(i, j, k);
  }
  /** Plane at continuous k; normal is Di cross Dj, even with descending k. */
  planeAtK(k: number): PatientImagingPlane {
    return createPatientImagingPlane({
      ...this.frame,
      origin: this.voxelToPatient(imageVoxelCoordinate(0, 0, k)),
    });
  }
}

/** 2D inverse exists only on this plane; never silently projects distant points. */
export class ImagePlaneTransform {
  readonly frame: PlanarImagingFrame;
  readonly plane: PatientImagingPlane;
  constructor(frame: PlanarImagingFrame) {
    this.frame = createPlanarImagingFrame(frame);
    this.plane = createPatientImagingPlane(this.frame);
    Object.freeze(this);
  }
  pixelToPatient(pixel: ImagePixelCoordinate): PatientSpacePoint {
    if (!pixel || pixel.space !== 'image-pixel')
      throw new TypeError('Expected image-pixel coordinate.');
    finite([pixel.i, pixel.j]);
    const f = this.frame;
    const i = pixel.i * toMillimetres(f.spacing.i),
      j = pixel.j * toMillimetres(f.spacing.j);
    finite([i, j]);
    return checkedPoint(
      patientSpacePoint(
        f.origin.value.x + i * f.directionI.value.x + j * f.directionJ.value.x,
        f.origin.value.y + i * f.directionI.value.y + j * f.directionJ.value.y,
        f.origin.value.z + i * f.directionI.value.z + j * f.directionJ.value.z,
      ),
    );
  }
  patientToPixel(point: PatientSpacePoint): ImagePixelCoordinate {
    const v = delta(point, this.frame.origin);
    const residual = dot(v, this.plane.normal.value);
    finite([residual]);
    if (Math.abs(residual) > IMAGE_PLANE_TOLERANCE_MM)
      throw new RangeError(
        'Patient point is outside the imaging plane tolerance.',
      );
    const a = this.frame.directionI.value,
      b = this.frame.directionJ.value;
    const aa = dot(a, a),
      ab = dot(a, b),
      bb = dot(b, b);
    const determinant = aa * bb - ab * ab;
    return imagePixelCoordinate(
      (dot(v, a) * bb - dot(v, b) * ab) /
        determinant /
        toMillimetres(this.frame.spacing.i),
      (dot(v, b) * aa - dot(v, a) * ab) /
        determinant /
        toMillimetres(this.frame.spacing.j),
    );
  }
}
