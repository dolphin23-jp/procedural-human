# TASK-071 — Interaction Engine skeleton

`new InteractionEngine(spatial: SpatialQueryApi)` injects a patient-scoped
public Spatial Query dependency. `observeNeedleMovement({ previous, current })`
takes two existing `NeedleInstance` states for the same instance and definition.
Both states must be valid domain states from Instruments, in the same Patient
Space as the injected service. The composition caller owns that association:
neither NeedleInstance nor SpatialQueryApi currently carries a patient/frame ID.

The engine copies the previous and current physical tip positions into the
existing `PatientSpaceSegment` and calls public `querySegment` exactly once
for nonzero displacement. Coordinates are canonical millimetres. No conversion
or offset is applied. Local +Z orientation, tip direction and the instrument's
trajectory remain owned by Instruments.

## Observation contract

- `stationary`: instrument ID and Patient Space position; no query is called.
  Exact component equality defines zero movement, including rotation about a
  stationary tip. This is not a claim that the shaft has not moved.
- `queried`: instrument ID, immutable copied segment, and `spatialResult`,
  the unchanged return value of public `SpatialQueryApi.querySegment`.

The narrow wrapper distinguishes no query from a query result and associates the
query with its needle and segment. It deliberately reuses the public Spatial
result contract rather than cloning Spatial's vocabulary or exposing private
query/index/adapter classes. Query results are raw **with respect to Interaction**:
Spatial already supplies ordered spans, occupancy transitions and authored
boundary crossings. They are not Interaction events.

## Caller and failure contract

Supply each intended consecutive displacement explicitly. This method describes
one straight segment between the two tips; it does not inspect, consume, replay
or concatenate the trajectory history. Skipping intermediate motion samples
would describe a chord, not the omitted motion. Repeating a request repeats the
query; the engine has no history, deduplication, or global singleton.

Missing/non-needle states, invalid IDs, mismatched instance/definition identity,
missing/nonfinite/non-Patient-Space points, disagreement between tip and pose
origin, and overflowing displacement fail before querying. This is a movement
boundary check, not a replacement for Instruments' full state constructors.
Unused orientation/direction/history are not independently revalidated here.
No epsilon discards small but nonzero displacements. Missing query dependency
fails explicitly. Spatial errors propagate unchanged, without catch/fallback.
Anatomy bindings and availability belong to the supplied Spatial service;
Interaction creates no substitute anatomy. An explicitly empty Spatial region
set retains the public query's outside-span semantics.

## Ownership and limits

Direct dependencies: Instruments, Math (PatientSpacePoint), and Spatial.
No Patient service, Physics API, Physiology, Procedure, rendering, UI, browser,
Session or Event Bus dependency is introduced. The package compiles without DOM
libraries. Inputs, patient state and existing instrument controls are unchanged.

TASK-071 implements no contact semantics, boundary/lumen interaction events,
Interaction-owned penetration path state, medical-state mutation, procedure
evaluation, Event Bus/Event Log, replay, or demo/UI integration. It observes tip
translation only; no shaft collision, swept volume, bending or mechanics.

Before TASK-072, define which contacts must be observable. The current public
segment query omits isolated tangency and endpoint-only crossings, and rejects
finite boundary overlaps. It cannot establish every first-contact case merely
by interpreting its transitions. If contact detection needs additional spatial
evidence, extend the public Spatial contract explicitly; do not import internal
query implementations or infer missing contacts. Cross-call boundary continuity
also remains later Interaction work. TASK-071 preserves these semantics.

Tests use unchanged development-fixture geometry. Software validation makes no
medical-validation claim.
