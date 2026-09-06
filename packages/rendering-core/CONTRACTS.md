# Rendering-core contracts (TASK-045)

This package owns transient presentation contracts, independent of browser input,
Three.js, React, medical state, and Spatial Query. It compiles without DOM types.
It introduces no persistent schema or third-party dependency.

`RenderingPresentationApi` is bound to one explicit `PatientId` by the composition
root. Every `StructureId` identifies a patient structure in that scope, never a
mesh name or canonical `EntityId`. Adapters must reject unknown IDs and resolve
all relevant render representations; they must not infer identity from names.

| Contract | Meaning |
| --- | --- |
| `StructureVisibility` | Explicit show/hide state for a semantic structure. |
| `StructureOpacity` | Presentation alpha constructed with `opacity(value)`: finite 0–1, inclusive. Invalid values throw `RangeError`; no clamping. |
| `StructureSelection` | One semantic `StructureId`, or `null` to clear selection. |
| `PatientClippingPlane` | Point on the plane in patient mm and a dimensionless patient-space unit normal. Keep the nonnegative side of `dot(normal, point - origin)`, including the plane. `null` disables clipping. |
| `CameraIntent` | Orbit, pan, dolly, or focus expressed independently of input device and renderer. |

Visibility, opacity, and selection are independent. Hiding or making a structure
transparent does not implicitly clear selection. Selection does not force a
structure visible or opaque. Clipping affects presentation only. None of these
operations modifies anatomy, patient medical state, or Spatial Query results.

Camera orbit uses a patient-space pivot and unit axis with a right-hand-rule
`Angle` in radians, rotating camera position and orientation around that pivot.
Pan translates camera and target by a patient-space displacement in mm. Dolly
translates camera along its current viewing direction by signed `Length` in mm
(positive forward), without changing its target. Focus changes the target without
moving the camera. These are intents, not a camera controller or input mapping.

Adapters must validate finite spatial coordinates, unit normals/axes, finite
angles/distances, and a usable camera view before applying commands. Invalid
inputs must fail explicitly, without partial updates or inferred transforms.
The TypeScript shapes do not perform runtime spatial validation. The opacity
constructor performs its own scalar validation; type assertions can bypass it,
so adapters remain responsible for untrusted input.

The adapter must explicitly convert Patient Space to its Render Space. No
identity transform is implied. Coordinate conversion and tests belong to
TASK-047; renderer implementation to TASK-046; visibility/opacity/picking/input
and clipping behavior to TASK-049–055. No GLB loader, state store, renderer,
picking algorithm, input controller, or clipping algorithm is implemented here.
