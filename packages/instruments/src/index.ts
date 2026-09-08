declare const instrumentIdentifierBrand: unique symbol;

type InstrumentIdentifier<Kind extends string> = string & {
  readonly [instrumentIdentifierBrand]: Kind;
};

export type InstrumentDefinitionId =
  InstrumentIdentifier<'InstrumentDefinitionId'>;
export type InstrumentInstanceId = InstrumentIdentifier<'InstrumentInstanceId'>;
export type InstrumentPartId = InstrumentIdentifier<'InstrumentPartId'>;

/** Tagged Patient Space point, structurally compatible with math PatientSpacePoint. */
export interface InstrumentPosePosition {
  readonly space: 'patient';
  readonly kind: 'point';
  readonly value: {
    readonly x: number;
    readonly y: number;
    readonly z: number;
  };
}

/** Technology-neutral unit quaternion, structurally compatible with math Quaternion. */
export interface InstrumentPoseOrientation {
  readonly x: number;
  readonly y: number;
  readonly z: number;
  readonly w: number;
}

export interface InstrumentPart {
  readonly id: InstrumentPartId;
  readonly name: string;
  readonly parentPartId: InstrumentPartId | null;
}

export interface InstrumentDefinition {
  readonly id: InstrumentDefinitionId;
  readonly name: string;
  readonly parts: readonly InstrumentPart[];
}

export interface InstrumentPose {
  readonly position: InstrumentPosePosition;
  readonly orientation: InstrumentPoseOrientation;
}

export interface InstrumentInstance {
  readonly id: InstrumentInstanceId;
  readonly definitionId: InstrumentDefinitionId;
  readonly pose: InstrumentPose;
}

function nonEmptyIdentifier<Kind extends string>(
  value: string,
  label: string,
): InstrumentIdentifier<Kind> {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new TypeError(`${label} must be a non-empty string.`);
  }
  return value as InstrumentIdentifier<Kind>;
}

function nonEmptyName(value: string, label: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new TypeError(`${label} must be a non-empty string.`);
  }
  return value;
}

function copyPatientSpacePoint(
  point: InstrumentPosePosition,
): InstrumentPosePosition {
  if (
    point?.space !== 'patient' ||
    point.kind !== 'point' ||
    ![point.value?.x, point.value?.y, point.value?.z].every(Number.isFinite)
  ) {
    throw new TypeError(
      'Instrument pose position must be a finite Patient Space point.',
    );
  }
  return Object.freeze({
    space: 'patient',
    kind: 'point',
    value: Object.freeze({
      x: point.value.x,
      y: point.value.y,
      z: point.value.z,
    }),
  });
}

function copyUnitQuaternion(
  orientation: InstrumentPoseOrientation,
): InstrumentPoseOrientation {
  const values = [
    orientation?.x,
    orientation?.y,
    orientation?.z,
    orientation?.w,
  ];
  if (!values.every(Number.isFinite)) {
    throw new TypeError('Instrument pose orientation must be finite.');
  }
  const norm = Math.hypot(
    orientation.x,
    orientation.y,
    orientation.z,
    orientation.w,
  );
  if (!Number.isFinite(norm) || Math.abs(norm - 1) > 1e-9) {
    throw new RangeError(
      'Instrument pose orientation must be a unit quaternion.',
    );
  }
  return Object.freeze({
    x: orientation.x / norm,
    y: orientation.y / norm,
    z: orientation.z / norm,
    w: orientation.w / norm,
  });
}

export const instrumentDefinitionId = (
  value: string,
): InstrumentDefinitionId =>
  nonEmptyIdentifier<'InstrumentDefinitionId'>(value, 'Instrument definition ID');

export const instrumentInstanceId = (value: string): InstrumentInstanceId =>
  nonEmptyIdentifier<'InstrumentInstanceId'>(value, 'Instrument instance ID');

export const instrumentPartId = (value: string): InstrumentPartId =>
  nonEmptyIdentifier<'InstrumentPartId'>(value, 'Instrument part ID');

export function createInstrumentPart(input: {
  readonly id: InstrumentPartId;
  readonly name: string;
  readonly parentPartId?: InstrumentPartId | null;
}): InstrumentPart {
  const id = instrumentPartId(input.id);
  const parentPartId =
    input.parentPartId == null ? null : instrumentPartId(input.parentPartId);
  if (parentPartId === id) {
    throw new RangeError('Instrument part cannot be its own parent.');
  }
  return Object.freeze({
    id,
    name: nonEmptyName(input.name, 'Instrument part name'),
    parentPartId,
  });
}

export function createInstrumentDefinition(input: {
  readonly id: InstrumentDefinitionId;
  readonly name: string;
  readonly parts: readonly InstrumentPart[];
}): InstrumentDefinition {
  const parts = input.parts.map((part) => createInstrumentPart(part));
  const ids = new Set<string>();
  for (const part of parts) {
    if (ids.has(part.id)) {
      throw new RangeError(`Duplicate instrument part ID: ${part.id}`);
    }
    ids.add(part.id);
  }
  for (const part of parts) {
    if (part.parentPartId !== null && !ids.has(part.parentPartId)) {
      throw new RangeError(
        `Instrument part ${part.id} references an unknown parent ${part.parentPartId}.`,
      );
    }
  }
  return Object.freeze({
    id: instrumentDefinitionId(input.id),
    name: nonEmptyName(input.name, 'Instrument definition name'),
    parts: Object.freeze(parts),
  });
}

export function createInstrumentPose(input: {
  readonly position: InstrumentPosePosition;
  readonly orientation: InstrumentPoseOrientation;
}): InstrumentPose {
  return Object.freeze({
    position: copyPatientSpacePoint(input.position),
    orientation: copyUnitQuaternion(input.orientation),
  });
}

export function createInstrumentInstance(input: {
  readonly id: InstrumentInstanceId;
  readonly definitionId: InstrumentDefinitionId;
  readonly pose: InstrumentPose;
}): InstrumentInstance {
  return Object.freeze({
    id: instrumentInstanceId(input.id),
    definitionId: instrumentDefinitionId(input.definitionId),
    pose: createInstrumentPose(input.pose),
  });
}
