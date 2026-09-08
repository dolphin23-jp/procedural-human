declare const normalizedControlBrand: unique symbol;

/** Dimensionless device intent axis in [-1, 1]; not a medical spatial quantity. */
export type NormalizedControlAxis = number & {
  readonly [normalizedControlBrand]: 'NormalizedControlAxis';
};

/** Dimensionless device intent magnitude in [0, 1]. */
export type NormalizedControlMagnitude = number & {
  readonly [normalizedControlBrand]: 'NormalizedControlMagnitude';
};

export type NeedleControlIntent =
  | {
      readonly type: 'translate';
      readonly lateral: NormalizedControlAxis;
      readonly vertical: NormalizedControlAxis;
    }
  | {
      readonly type: 'rotate';
      readonly yaw: NormalizedControlAxis;
      readonly pitch: NormalizedControlAxis;
    }
  | {
      readonly type: 'advance';
      readonly amount: NormalizedControlMagnitude;
    }
  | {
      readonly type: 'retract';
      readonly amount: NormalizedControlMagnitude;
    };

export function normalizedControlAxis(value: number): NormalizedControlAxis {
  if (!Number.isFinite(value) || value < -1 || value > 1) {
    throw new RangeError(
      'Normalized control axis must be finite and within [-1, 1].',
    );
  }
  return value as NormalizedControlAxis;
}

export function normalizedControlMagnitude(
  value: number,
): NormalizedControlMagnitude {
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    throw new RangeError(
      'Normalized control magnitude must be finite and within [0, 1].',
    );
  }
  return value as NormalizedControlMagnitude;
}

export function needleTranslationIntent(
  lateral: number,
  vertical: number,
): NeedleControlIntent {
  return Object.freeze({
    type: 'translate',
    lateral: normalizedControlAxis(lateral),
    vertical: normalizedControlAxis(vertical),
  });
}

export function needleRotationIntent(
  yaw: number,
  pitch: number,
): NeedleControlIntent {
  return Object.freeze({
    type: 'rotate',
    yaw: normalizedControlAxis(yaw),
    pitch: normalizedControlAxis(pitch),
  });
}

export function needleAdvanceIntent(amount: number): NeedleControlIntent {
  return Object.freeze({
    type: 'advance',
    amount: normalizedControlMagnitude(amount),
  });
}

export function needleRetractIntent(amount: number): NeedleControlIntent {
  return Object.freeze({
    type: 'retract',
    amount: normalizedControlMagnitude(amount),
  });
}
