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
  type SpatialContactQueryApi,
  type SpatialContactInterval,
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

function movementSegment(request: NeedleMovementRequest): PatientSpaceSegment {
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
    return patientSpaceSegment(start, end);
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
  return patientSpaceSegment(start, end);
}

/** Transient physical contact candidate; persistence/time belong to later tasks. */
export interface InstrumentContact {
  readonly kind: 'contact';
  readonly instrumentId: InstrumentInstanceId;
  readonly structureId: SpatialContactInterval['structureId'];
  readonly canonicalEntityId: SpatialContactInterval['canonicalEntityId'];
  readonly at: SpatialContactInterval['start'];
}

/** Patient-scoped, stateless tip movement and contact observation. */
export class InteractionEngine {
  readonly #spatial: SpatialQueryApi & Partial<SpatialContactQueryApi>;

  constructor(spatial: SpatialQueryApi & Partial<SpatialContactQueryApi>) {
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
    const segment = movementSegment(request);
    if (samePosition(segment.start, segment.end)) {
      return Object.freeze({
        kind: 'stationary',
        instrumentId: request.current.id,
        position: segment.end,
      });
    }
    const spatialResult = this.#spatial.querySegment(segment);
    return Object.freeze({
      kind: 'queried',
      instrumentId: request.current.id,
      segment,
      spatialResult,
    });
  }

  detectNeedleContacts(
    request: NeedleMovementRequest,
  ): readonly InstrumentContact[] {
    const segment = movementSegment(request);
    if (typeof this.#spatial.queryContacts !== 'function') {
      throw new TypeError('Spatial contact query capability is unavailable.');
    }
    if (samePosition(segment.start, segment.end)) return Object.freeze([]);
    // A component starting at zero is pre-existing contact, not a new onset.
    // Endpoint contact was reported by the preceding consecutive displacement.
    return Object.freeze(
      this.#spatial
        .queryContacts(segment)
        .filter((interval) => interval.start.t > 0)
        .map((interval) =>
          Object.freeze({
            kind: 'contact' as const,
            instrumentId: request.current.id,
            structureId: interval.structureId,
            canonicalEntityId: interval.canonicalEntityId,
            at: interval.start,
          }),
        ),
    );
  }
}
