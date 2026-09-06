# Spatial Query public API — TASK-043

## Purpose

Downstream packages should depend on the small `SpatialQueryApi` contract instead of
constructing `BasicSpatialIndex`, `PointQuery`, `BoundaryQuery`,
`DistanceQuery`, or `OrderedPenetrationPathQuery` themselves.

The public consumer surface is deliberately limited to:

- `queryPoint(PatientSpacePoint)`
- `querySegment(PatientSpaceSegment)`
- `distanceTo(PatientSpacePoint, StructureId)`

`SpatialQueryService` is the default implementation.

## Semantics

`queryPoint` returns the existing deterministic structure, tissue, and lumen
membership snapshot. Venous/arterial classification is copied only from explicit
binding metadata and is never inferred from names or geometry.

`querySegment` returns TASK-042's ordered penetration path. That result already
contains open-interval memberships, coincident occupancy transitions, medically
meaningful boundary crossings when authored, patient-space positions, and physical
distance from the supplied segment start. Raw representation contacts from
TASK-038 remain a lower-level capability and are not promoted into the consumer
facade.

`distanceTo` remains an explicitly targeted unsigned distance query. A
`StructureId` is required; the service does not choose a nearest structure.

All positions remain Patient Space and all physical distances remain `Length`.

## Construction boundary

`SpatialQueryServiceConfig.regions` provides patient-scoped occupancy bindings.
The service snapshots semantic metadata and membership-role arrays, while geometry
adapters remain caller-owned fixed-state dependencies for the duration of a query.

By default the same region bindings are used for distance queries. If a
`StructureId` has multiple regions, or distance must use a different
representation, composition must provide explicit `distanceEntries`. Existing
`DistanceQuery` duplicate-target validation then prevents an ambiguous
representation from being selected silently.

Boundary bindings are optional. A region transition can exist without an authored
medically significant boundary; the service does not fabricate one.

## Architectural boundary

The facade is spatial only. It does not:

- emit Interaction events
- judge venous access success or arterial safety
- mutate patient medical state
- inspect renderer meshes
- own procedure logic
- add cross-call trajectory history

Low-level Spatial classes remain exported for current in-package tests and
specialized Spatial development, but other packages should type their dependency
as `SpatialQueryApi`. Later Session composition can supply the concrete
`SpatialQueryService` without exposing those implementation classes.
