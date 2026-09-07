# Three.js renderer adapter

TASK-046 adds the first static browser renderer for the explicitly non-medical
synthetic anatomy fixture. `ThreeFixtureScene` creates four semantic meshes:
skin, soft tissue, vein, and artery. Mesh metadata stores branded patient
`StructureId` values so later picking work does not need to infer identity from
mesh names.

`ThreeFixtureRenderer` owns the Three.js renderer, camera, lights, resize/render
entry points, and deterministic disposal of geometries, materials, and the WebGL
renderer. It caps device pixel ratio at 2 by default to avoid unnecessary iPad
fill-rate cost. The web shell displays a clear development-fixture label.

The package pins Three.js 0.185.1 (MIT), the current release when this task was
implemented. It is isolated to this adapter by the existing dependency-boundary
check. The package includes only the narrow ambient declarations used by this
adapter because Three.js does not publish TypeScript declarations. Runtime
behavior is still provided by the unmodified pinned package.

TASK-047 adds explicit reversible Patient Space ↔ Render Space ↔ Three world
conversion. The renderer and scene now require a `PatientRenderTransform`.
The web composition supplies `createFixtureCoordinateTransform()` explicitly:
origin (0,0,12) mm, identity rotation, and 100 mm per render unit. The parent
geometry matrix, camera and lights share this mapping. See
[coordinate contracts](../rendering-core/COORDINATES.md) for equations, units,
validation and numerical tolerances. Camera input, GLB loading,
visibility/opacity controls, picking and clipping remain later tasks.


## TASK-048 — GLB runtime loading and semantic binding

GLB is treated only as a derived render representation. Runtime identity is never
inferred from a node or mesh name. `ThreeGlbRuntimeLoader` requires an explicit
`GlbRuntimeAssetDescriptor` whose non-medical runtime binding keys map to
`StructureId` values in a `ThreeSemanticContext`. The context resolves those IDs
to the actual `PatientStructureInstance` and canonical `AnatomicalEntity`.

The GLB must declare `extras.renderBindingKey` on the node/mesh carrying a bound
representation. Every declared key must be explicitly present in the descriptor,
every descriptor key must exist in the GLB, and unknown patient structures or
canonical entities fail loading. GLB names remain presentation/debug metadata only.

The descriptor also requires `coordinateSpace: "patient-mm"`. Loaded geometry is
wrapped once by the explicit TASK-047 Patient→Render transform. Missing or implied
registration is not accepted.

## TASK-049 — Structure visibility

`ThreeStructurePresentation.setVisibility()` resolves a semantic `StructureId`
through the shared semantic registry and updates only the Three.js `visible`
property on every render mesh bound to that structure. Unknown or unbound
structures fail explicitly. Visibility does not clear selection, alter opacity,
mutate `PatientInstance` medical state, or call Spatial Query.
