import {
  patientSpaceDirection,
  type PatientSpaceDirection,
} from '@procedural-human/math';
import {
  createInstrumentInstance,
  createInstrumentPose,
  type InstrumentInstance,
  type InstrumentInstanceId,
  type InstrumentPose,
  type InstrumentPosePosition,
} from './base.js';
import type { NeedleDefinition } from './needle.js';

export interface NeedleTrajectorySample {
  readonly position: InstrumentPosePosition;
  readonly direction: PatientSpaceDirection;
}

export interface NeedleInstance extends InstrumentInstance {
  readonly kind: 'needle';
  /** Needle pose origin is the physical tip in Patient Space. */
  readonly tipPosition: InstrumentPosePosition;
  /** Identity orientation points the needle along Patient Space +Z. */
  readonly tipDirection: PatientSpaceDirection;
  /** Ordered pose-derived tip samples; simulation time is added later by TASK-078. */
  readonly trajectory: readonly NeedleTrajectorySample[];
}

function tipDirectionForPose(pose: InstrumentPose): PatientSpaceDirection {
  const { x, y, z, w } = pose.orientation;
  return patientSpaceDirection(
    2 * (x * z + w * y),
    2 * (y * z - w * x),
    1 - 2 * (x * x + y * y),
  );
}

function sampleForPose(pose: InstrumentPose): NeedleTrajectorySample {
  return Object.freeze({
    position: pose.position,
    direction: tipDirectionForPose(pose),
  });
}

function sameSample(
  left: NeedleTrajectorySample,
  right: NeedleTrajectorySample,
): boolean {
  return (
    left.position.value.x === right.position.value.x &&
    left.position.value.y === right.position.value.y &&
    left.position.value.z === right.position.value.z &&
    left.direction.value.x === right.direction.value.x &&
    left.direction.value.y === right.direction.value.y &&
    left.direction.value.z === right.direction.value.z
  );
}

function freezeNeedleInstance(
  instrument: InstrumentInstance,
  trajectory: readonly NeedleTrajectorySample[],
): NeedleInstance {
  const latest = trajectory[trajectory.length - 1];
  if (!latest) {
    throw new RangeError('Needle trajectory must contain at least one sample.');
  }
  return Object.freeze({
    ...instrument,
    kind: 'needle',
    tipPosition: latest.position,
    tipDirection: latest.direction,
    trajectory: Object.freeze([...trajectory]),
  });
}

export function createNeedleInstance(input: {
  readonly id: InstrumentInstanceId;
  readonly definition: NeedleDefinition;
  readonly pose: InstrumentPose;
}): NeedleInstance {
  const instrument = createInstrumentInstance({
    id: input.id,
    definitionId: input.definition.id,
    pose: input.pose,
  });
  const sample = sampleForPose(instrument.pose);
  return freezeNeedleInstance(instrument, [sample]);
}

export function updateNeedlePose(
  instance: NeedleInstance,
  pose: InstrumentPose,
): NeedleInstance {
  if (instance?.kind !== 'needle') {
    throw new TypeError('Needle instance is required.');
  }
  const nextPose = createInstrumentPose(pose);
  const instrument = createInstrumentInstance({
    id: instance.id,
    definitionId: instance.definitionId,
    pose: nextPose,
  });
  const sample = sampleForPose(instrument.pose);
  const previous = instance.trajectory[instance.trajectory.length - 1];
  const trajectory =
    previous && sameSample(previous, sample)
      ? instance.trajectory
      : [...instance.trajectory, sample];
  return freezeNeedleInstance(instrument, trajectory);
}
