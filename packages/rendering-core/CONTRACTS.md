# Rendering-core contracts (TASK-045, refined by TASK-052)

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
| `PatientClippingPlane` | Point on the plane in patient mm and a dimensionless `PatientSpaceDirection` unit normal. Keep the nonnegative side of `dot(normal, point - origin)`, including the plane. `null` disables clipping. |
| `CameraIntent` | Orbit, pan, dolly, or focus expressed independently of input device and renderer. |

Visibility, opacity, and selection are independent. Hiding or making a structure
transparent does not implicitly clear selection. Selection does not force a
structure visible or opaque. Clipping affects presentation only. None of these
operations modifies anatomy, patient medical state, or Spatial Query results.

Camera orbit uses a patient-space pivot and dimensionless `PatientSpaceDirection`
unit axis with a right-hand-rule `Angle` in radians. Pan translates camera and
target by a physical `PatientSpaceVector` displacement in mm. Dolly translates
camera along its current viewing direction by signed `Length` in mm (positive
forward), without changing its target. Focus changes the target without moving
the camera.

TASK-052 makes the axis/vector distinction part of the type system. Unit normals
and directions are not represented as physical displacement vectors. Adapters
must validate finite spatial coordinates, unit directions, finite angles and
distances, and a usable camera view before applying commands. Invalid inputs must
fail explicitly, without partial updates or inferred transforms. The opacity
constructor performs scalar validation; adapters still validate untrusted values
because type assertions can bypass constructors.

The adapter must explicitly convert Patient Space to its Render Space. No
identity transform is implied. TASK-047 implements the neutral
`PatientRenderTransform`; see [coordinate contracts](COORDINATES.md).

Renderer implementation belongs to `packages/rendering-three`. TASK-048 adds
explicit GLB semantic binding, TASK-049/050 semantic visibility and opacity,
TASK-051 semantic picking, and TASK-052 mouse/touch input normalization. Clipping
rendering remains TASK-055. Rendering-core itself contains none of those concrete
Three.js or browser implementations.
