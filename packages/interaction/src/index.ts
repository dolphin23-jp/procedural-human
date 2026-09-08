import {
  instrumentDefinitionId,
  instrumentInstanceId,
  type InstrumentInstanceId,
  type NeedleInstance,
} from '@procedural-human/instruments';
import type { PatientSpacePoint } from '@procedural-human/math';
import {
  patientSpaceSegment,
  type PatientSpaceSegment,
  type SpatialQueryApi,
} from '@procedural-human/spatial';

export interface NeedleMovementRequest {
  readonly previous: NeedleInstance;
  readonly current: NeedleInstance;
}

/** A query observation, not an interaction event or accumulated path. */
export type NeedleMovementObservation =
  | {
      readonly kind: 'stationary';
      readonly instrumentId: InstrumentInstanceId;
      readonly position: PatientSpacePoint;
    }
  | {
      readonly kind: 'queried';
      readonly instrumentId: InstrumentInstanceId;
      readonly segment: PatientSpaceSegment;
      readonly spatialResult: ReturnType<SpatialQueryApi['querySegment']>;
    };

function copyPoint(point: PatientSpacePoint): PatientSpacePoint {
  if (
    point?.space !== 'patient' ||
    point.kind !== 'point' ||
    ![point.value?.x, point.value?.y, point.value?.z].every(Number.isFinite)
  ) {
    throw new TypeError(
      'Needle movement requires finite Patient Space points.',
    );
  }
  return Object.freeze({
    space: 'patient',
    kind: 'point',
    value: Object.freeze({ ...point.value }),
  });
}

function samePosition(a: PatientSpacePoint, b: PatientSpacePoint): boolean {
  return (
    a.value.x === b.value.x &&
    a.value.y === b.value.y &&
    a.value.z === b.value.z
  );
}

function tipFor(instance: NeedleInstance): PatientSpacePoint {
  if (instance?.kind !== 'needle') {
    throw new TypeError('Needle movement requires two NeedleInstance states.');
  }
  instrumentInstanceId(instance.id);
  instrumentDefinitionId(instance.definitionId);
  const tip = copyPoint(instance.tipPosition);
  const origin = copyPoint(instance.pose?.position);
  if (!samePosition(tip, origin)) {
    throw new RangeError(
      'Needle tip must equal its Patient Space pose origin.',
    );
  }
  return tip;
}

/** Stateless observation of one caller-supplied straight tip displacement. */
export class InteractionEngine {
  readonly #spatial: SpatialQueryApi;

  constructor(spatial: SpatialQueryApi) {
    if (typeof spatial?.querySegment !== 'function') {
      throw new TypeError(
        'InteractionEngine requires Spatial Query querySegment.',
      );
    }
    this.#spatial = spatial;
  }

  observeNeedleMovement(
    request: NeedleMovementRequest,
  ): NeedleMovementObservation {
    const start = tipFor(request?.previous);
    const end = tipFor(request?.current);
    const { previous, current } = request;
    if (
      previous.id !== current.id ||
      previous.definitionId !== current.definitionId
    ) {
      throw new RangeError(
        'Needle movement states must identify the same needle.',
      );
    }
    if (samePosition(start, end)) {
      return Object.freeze({
        kind: 'stationary',
        instrumentId: current.id,
        position: end,
      });
    }
    if (
      !Number.isFinite(
        Math.hypot(
          end.value.x - start.value.x,
          end.value.y - start.value.y,
          end.value.z - start.value.z,
        ),
      )
    ) {
      throw new RangeError('Needle movement displacement overflow.');
    }
    const segment = patientSpaceSegment(start, end);
    const spatialResult = this.#spatial.querySegment(segment);
    return Object.freeze({
      kind: 'queried',
      instrumentId: current.id,
      segment,
      spatialResult,
    });
  }
}
