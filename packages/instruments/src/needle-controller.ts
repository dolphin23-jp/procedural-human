import { toRadians, toMillimetres, type Angle, type Length } from '@procedural-human/units';
import {
  createInstrumentPose,
  type InstrumentPoseOrientation,
  type InstrumentPosePosition,
} from './base.js';
import type { NeedleControlIntent } from './needle-control-intent.js';
import {
  type NeedleInstance,
  updateNeedlePose,
} from './needle-instance.js';

export interface NeedleMotionControllerConfig {
  /** Maximum Patient Space lateral/vertical displacement per full-scale intent. */
  readonly translationStep: Length;
  /** Maximum Patient Space rotation per full-scale yaw/pitch intent. */
  readonly rotationStep: Angle;
  /** Maximum tip-axis travel per full-scale advance/retract intent. */
  readonly advanceStep: Length;
}

function positiveLength(value: Length, label: string): Length {
  const millimetres = toMillimetres(value);
  if (!Number.isFinite(millimetres) || millimetres <= 0) {
    throw new RangeError(`${label} must be finite and greater than zero.`);
  }
  return value;
}

function positiveAngle(value: Angle): Angle {
  const radians = toRadians(value);
  if (!Number.isFinite(radians) || radians <= 0) {
    throw new RangeError(
      'Needle rotation step must be finite and greater than zero.',
    );
  }
  return value;
}

function posePosition(
  position: InstrumentPosePosition,
  x: number,
  y: number,
  z: number,
): InstrumentPosePosition {
  return {
    space: position.space,
    kind: position.kind,
    value: { x, y, z },
  };
}

function axisAngle(
  x: number,
  y: number,
  z: number,
  angle: number,
): InstrumentPoseOrientation {
  const half = angle / 2;
  const sine = Math.sin(half);
  return { x: x * sine, y: y * sine, z: z * sine, w: Math.cos(half) };
}

function multiply(
  left: InstrumentPoseOrientation,
  right: InstrumentPoseOrientation,
): InstrumentPoseOrientation {
  return {
    x:
      left.w * right.x +
      left.x * right.w +
      left.y * right.z -
      left.z * right.y,
    y:
      left.w * right.y -
      left.x * right.z +
      left.y * right.w +
      left.z * right.x,
    z:
      left.w * right.z +
      left.x * right.y -
      left.y * right.x +
      left.z * right.w,
    w:
      left.w * right.w -
      left.x * right.x -
      left.y * right.y -
      left.z * right.z,
  };
}

export class NeedleMotionController {
  readonly #translationStepMillimetres: number;
  readonly #rotationStepRadians: number;
  readonly #advanceStepMillimetres: number;

  constructor(config: NeedleMotionControllerConfig) {
    this.#translationStepMillimetres = toMillimetres(
      positiveLength(config.translationStep, 'Needle translation step'),
    );
    this.#rotationStepRadians = toRadians(positiveAngle(config.rotationStep));
    this.#advanceStepMillimetres = toMillimetres(
      positiveLength(config.advanceStep, 'Needle advance step'),
    );
  }

  apply(instance: NeedleInstance, intent: NeedleControlIntent): NeedleInstance {
    if (instance?.kind !== 'needle') {
      throw new TypeError('Needle instance is required.');
    }

    const { x, y, z } = instance.tipPosition.value;
    if (intent.type === 'translate') {
      return updateNeedlePose(
        instance,
        createInstrumentPose({
          position: posePosition(
            instance.tipPosition,
            x + intent.lateral * this.#translationStepMillimetres,
            y + intent.vertical * this.#translationStepMillimetres,
            z,
          ),
          orientation: instance.pose.orientation,
        }),
      );
    }

    if (intent.type === 'advance' || intent.type === 'retract') {
      const sign = intent.type === 'advance' ? 1 : -1;
      const distance = sign * intent.amount * this.#advanceStepMillimetres;
      const direction = instance.tipDirection.value;
      return updateNeedlePose(
        instance,
        createInstrumentPose({
          position: posePosition(
            instance.tipPosition,
            x + direction.x * distance,
            y + direction.y * distance,
            z + direction.z * distance,
          ),
          orientation: instance.pose.orientation,
        }),
      );
    }

    // Patient-axis rotations are deterministic: yaw (+Y) is applied first,
    // followed by pitch (+X). Deltas are left-multiplied into the current pose.
    const yaw = axisAngle(0, 1, 0, intent.yaw * this.#rotationStepRadians);
    const pitch = axisAngle(1, 0, 0, intent.pitch * this.#rotationStepRadians);
    const orientation = multiply(pitch, multiply(yaw, instance.pose.orientation));
    return updateNeedlePose(
      instance,
      createInstrumentPose({
        position: instance.tipPosition,
        orientation,
      }),
    );
  }
}
