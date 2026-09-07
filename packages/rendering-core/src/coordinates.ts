import {
  patientSpacePoint,
  patientSpaceVector,
  renderSpacePoint,
  renderSpaceVector,
  type PatientSpacePoint,
  type PatientSpaceVector,
  type Quaternion,
  type RenderSpacePoint,
  type RenderSpaceVector,
  type Vec3,
} from '@procedural-human/math';
import { toMillimetres, type Length } from '@procedural-human/units';

export interface PatientRenderTransformConfig {
  /** Patient-space location mapped to render (0,0,0); coordinates are mm. */
  readonly patientOrigin: PatientSpacePoint;
  /** Unit quaternion mapping patient axes to render axes (right-handed). */
  readonly patientToRenderRotation: Quaternion;
  /** Positive physical length represented by one render unit. */
  readonly millimetresPerRenderUnit: Length;
}

function finite(value: Vec3): void {
  if (!value || ![value.x, value.y, value.z].every(Number.isFinite)) {
    throw new RangeError('Coordinate components must be finite.');
  }
}

function tagged(
  value:
    | PatientSpacePoint
    | PatientSpaceVector
    | RenderSpacePoint
    | RenderSpaceVector,
  space: 'patient' | 'render',
  kind: 'point' | 'vector',
): void {
  if (!value || value.space !== space || value.kind !== kind) {
    throw new TypeError(`Expected ${space}-space ${kind}.`);
  }
  finite(value.value);
}

function rotate(v: Vec3, q: Quaternion): Vec3 {
  const tx = 2 * (q.y * v.z - q.z * v.y);
  const ty = 2 * (q.z * v.x - q.x * v.z);
  const tz = 2 * (q.x * v.y - q.y * v.x);
  const result = {
    x: v.x + q.w * tx + q.y * tz - q.z * ty,
    y: v.y + q.w * ty + q.z * tx - q.x * tz,
    z: v.z + q.w * tz + q.x * ty - q.y * tx,
  };
  finite(result);
  return result;
}

/** Immutable similarity transform: r = R * (p - origin) / mmPerUnit. */
export class PatientRenderTransform {
  readonly config: PatientRenderTransformConfig;
  readonly #inverseRotation: Quaternion;

  constructor(config: PatientRenderTransformConfig) {
    if (!config)
      throw new TypeError(
        'Patient/render transform configuration is required.',
      );
    tagged(config.patientOrigin, 'patient', 'point');
    const scale = toMillimetres(config.millimetresPerRenderUnit);
    if (!Number.isFinite(scale) || scale <= 0 || !Number.isFinite(1 / scale)) {
      throw new RangeError(
        'Millimetres per render unit must be positive, finite and invertible.',
      );
    }
    const q = config.patientToRenderRotation;
    if (!q || ![q.x, q.y, q.z, q.w].every(Number.isFinite)) {
      throw new RangeError(
        'Patient-to-render rotation must be a finite unit quaternion.',
      );
    }
    const norm = Math.hypot(q.x, q.y, q.z, q.w);
    if (Math.abs(norm - 1) > 1e-12) {
      throw new RangeError(
        'Patient-to-render rotation must be a unit quaternion.',
      );
    }
    // Correct only floating-point normalization error, never arbitrary rotations.
    const rotation = Object.freeze({
      x: q.x / norm,
      y: q.y / norm,
      z: q.z / norm,
      w: q.w / norm,
    });
    this.config = Object.freeze({
      patientOrigin: Object.freeze({
        ...config.patientOrigin,
        value: Object.freeze({ ...config.patientOrigin.value }),
      }),
      patientToRenderRotation: rotation,
      millimetresPerRenderUnit: config.millimetresPerRenderUnit,
    });
    this.#inverseRotation = Object.freeze({
      x: -rotation.x,
      y: -rotation.y,
      z: -rotation.z,
      w: rotation.w,
    });
    Object.freeze(this);
  }

  patientPointToRender(point: PatientSpacePoint): RenderSpacePoint {
    tagged(point, 'patient', 'point');
    const o = this.config.patientOrigin.value;
    const v = this.patientVectorToRender(
      patientSpaceVector(
        point.value.x - o.x,
        point.value.y - o.y,
        point.value.z - o.z,
      ),
    );
    return renderSpacePoint(v.value.x, v.value.y, v.value.z);
  }

  renderPointToPatient(point: RenderSpacePoint): PatientSpacePoint {
    tagged(point, 'render', 'point');
    const v = this.renderVectorToPatient(
      renderSpaceVector(point.value.x, point.value.y, point.value.z),
    );
    const o = this.config.patientOrigin.value;
    const result = patientSpacePoint(
      v.value.x + o.x,
      v.value.y + o.y,
      v.value.z + o.z,
    );
    finite(result.value);
    return result;
  }

  patientVectorToRender(vector: PatientSpaceVector): RenderSpaceVector {
    tagged(vector, 'patient', 'vector');
    const scale = toMillimetres(this.config.millimetresPerRenderUnit);
    const v = rotate(
      {
        x: vector.value.x / scale,
        y: vector.value.y / scale,
        z: vector.value.z / scale,
      },
      this.config.patientToRenderRotation,
    );
    return renderSpaceVector(v.x, v.y, v.z);
  }

  renderVectorToPatient(vector: RenderSpaceVector): PatientSpaceVector {
    tagged(vector, 'render', 'vector');
    const v = rotate(vector.value, this.#inverseRotation);
    const scale = toMillimetres(this.config.millimetresPerRenderUnit);
    const result = patientSpaceVector(v.x * scale, v.y * scale, v.z * scale);
    finite(result.value);
    return result;
  }
}
