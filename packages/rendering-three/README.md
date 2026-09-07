# Three.js renderer adapter

This package owns the concrete Three.js browser renderer while keeping medical and
renderer-neutral contracts outside Three.js.

TASK-046 introduced the explicitly non-medical synthetic anatomy fixture. The
fixture renders skin, soft tissue, vein, and artery. TASK-047 added explicit,
reversible Patient Space ↔ Render Space ↔ Three world conversion. The web fixture
uses the named `createFixtureCoordinateTransform()` configuration: patient origin
(0,0,12) mm, identity rotation, and 100 mm per render unit. It is a fixture-only
configuration, never a fallback registration for medical data.

The package pins Three.js 0.185.1 (MIT) and keeps Three imports inside this adapter
through the package-boundary rules. The adapter-local `three.d.ts` contains only
the narrow API surface this repository uses; runtime behavior comes from the
pinned Three.js package and integration tests exercise real Three objects.

## TASK-048 — GLB runtime loading and semantic binding

GLB is a derived render representation. Runtime identity is never inferred from a
node or mesh name. `ThreeGlbRuntimeLoader` requires an explicit
`GlbRuntimeAssetDescriptor` whose non-medical `renderBindingKey` values map to
`StructureId` values in a `ThreeSemanticContext`. The context resolves those IDs
to the actual `PatientStructureInstance` and canonical `AnatomicalEntity`.

The GLB declares `extras.renderBindingKey` on the object carrying a bound
representation. Every declared key must be present in the descriptor, every
descriptor key must exist in the GLB, and unknown structures or canonical
entities fail loading. The test GLB deliberately gives nodes misleading anatomy
names; explicit bindings still determine identity.

The descriptor requires `coordinateSpace: "patient-mm"`. Loaded patient-mm
geometry is wrapped once by the explicit Patient→Render transform. Missing or
implied registration is not accepted.

## TASK-049 / TASK-050 — Semantic presentation state

`ThreeStructurePresentation` resolves `StructureId` through the shared semantic
registry. Visibility updates only Three `visible` state. Opacity updates only
presentation materials and clones materials before mutation so one structure
cannot accidentally change another structure that shared a GLB material.

Visibility, opacity and selection do not mutate patient medical state or Spatial
Query. Unknown or unbound structures fail explicitly.

## TASK-051 — Picking and semantic resolution

`ThreeSemanticPicker` raycasts registered render meshes but never exposes a Three
mesh as the semantic result. A hit is resolved through the registry to the actual
`PatientStructureInstance` and canonical `AnatomicalEntity`, together with the
hit point converted back into Patient Space. Renaming a mesh has no effect on
semantic picking.

## TASK-052 — Camera input abstraction

Browser input is normalized to renderer-neutral `CameraIntent` values before the
Three camera changes. The fixture supports one-pointer orbit, Shift-drag pan,
mouse-wheel dolly, two-pointer pan, pinch dolly, and tap selection.

TASK-052 also separates physical displacement from dimensionless direction:
`PatientSpaceVector` represents millimetre displacement, while
`PatientSpaceDirection` represents a finite unit direction. Orbit axes and future
clipping normals use directions; pan remains a physical vector. Patient↔render
direction conversion applies rotation only, not scale.

## TASK-053 — Real iPad checkpoint

The implementation required for the manual checkpoint is present, but CI cannot
close TASK-053. See [REAL_IPAD_CHECKPOINT.md](REAL_IPAD_CHECKPOINT.md) for the
physical-iPad Safari acceptance record covering rotate, zoom, pan and semantic
selection. Gate E remains open until that record passes on a real device.
