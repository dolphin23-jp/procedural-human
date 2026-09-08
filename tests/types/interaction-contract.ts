import type {
  InstrumentInstanceId,
  NeedleInstance,
} from '../../packages/instruments/src/index';
import {
  InteractionEngine,
  type NeedleMovementRequest,
} from '../../packages/interaction/src/index';
import {
  renderSpacePoint,
  type PatientSpacePoint,
} from '../../packages/math/src/index';
import type {
  PenetrationPathElement,
  SpatialQueryApi,
} from '../../packages/spatial/src/index';

declare const spatial: SpatialQueryApi;
declare const previous: NeedleInstance;
declare const current: NeedleInstance;
const request: NeedleMovementRequest = { previous, current };
const engine = new InteractionEngine(spatial);
const result = engine.observeNeedleMovement(request);
const id: InstrumentInstanceId = result.instrumentId;
void id;
if (result.kind === 'queried') {
  const start: PatientSpacePoint = result.segment.start;
  const raw: readonly PenetrationPathElement[] = result.spatialResult;
  void [start, raw];
  // @ts-expect-error Observations have no event payload.
  void result.events;
} else {
  const point: PatientSpacePoint = result.position;
  void point;
  // @ts-expect-error Stationary observation has no query result.
  void result.spatialResult;
}
// @ts-expect-error Both domain states are required.
engine.observeNeedleMovement({ current });
// @ts-expect-error Points alone are not needle states.
engine.observeNeedleMovement({ previous: renderSpacePoint(0, 0, 0), current });
const invalid: NeedleInstance = {
  ...current,
  // @ts-expect-error Render Space cannot replace Patient Space.
  tipPosition: renderSpacePoint(0, 0, 0),
};
void invalid;
// @ts-expect-error An explicit public Spatial Query dependency is required.
new InteractionEngine();

declare const contactApi: import('../../packages/spatial/src/index').SpatialContactQueryApi;
declare const contact: import('../../packages/interaction/src/index').InstrumentContact;
const contactPoint: PatientSpacePoint = contact.at.position;
const contactDistance: import('../../packages/units/src/index').Length =
  contact.at.distanceFromStart;
const contactStructure: import('../../packages/core/src/index').StructureId =
  contact.structureId;
void [contactPoint, contactDistance, contactStructure];
// @ts-expect-error Contact position cannot be Render Space.
const wrongContactPoint: typeof contact.at.position = renderSpacePoint(0, 0, 0);
// @ts-expect-error Contact distance requires physical Length.
const wrongContactDistance: typeof contact.at.distanceFromStart = 1;
// @ts-expect-error Structure identity remains branded.
const wrongContactStructure: typeof contact.structureId = 'structure';
void [wrongContactPoint, wrongContactDistance, wrongContactStructure];
contactApi.queryContacts({
  // @ts-expect-error Contact query requires explicit Patient Space.
  start: renderSpacePoint(0, 0, 0),
  end: current.tipPosition,
});
engine.detectNeedleContacts(request);
// @ts-expect-error Contact detection requires both needle states.
engine.detectNeedleContacts({ current });
