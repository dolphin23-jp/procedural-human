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
