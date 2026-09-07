# Patient/render coordinate conversion — TASK-047

`PatientRenderTransform` is a renderer-neutral, immutable similarity transform.
Construction requires all three fields; missing registration never becomes an
identity transform:

| Configuration | Meaning |
| --- | --- |
| `patientOrigin: PatientSpacePoint` | Patient location in mm corresponding to render (0, 0, 0). |
| `patientToRenderRotation: Quaternion` | Unit quaternion mapping patient axes into render axes. |
| `millimetresPerRenderUnit: Length` | Positive physical length of one render unit. |

For rotation R, origin o, and scale s in mm per render unit:

- Point forward: `r = R (p - o) / s`; inverse: `p = o + s R⁻¹ r`.
- Displacement forward: `vr = R vp / s`; inverse: `vp = s R⁻¹ vr`.

Point methods require `PatientSpacePoint` / `RenderSpacePoint`; displacement
methods require `PatientSpaceVector` / `RenderSpaceVector`. Displacements carry
mm on the patient side and configured render units on the render side. They are
not unit normals or directions. Plane/normal conversion is not part of this task.

The transform permits translations, right-handed rotations (including axis
permutations expressible as rotations), and a uniform positive scale. Shear,
reflection, non-uniform scaling, projective matrices, image-voxel registration,
and anatomical deformation are outside this contract. This avoids changing
physical shape or silently guessing patient axis conventions. No DICOM LPS/RAS
convention is inferred for the non-medical fixture.

All inputs must be finite and correctly tagged. Scale must be positive with a
finite reciprocal. Quaternion length must be within 1e-12 of one; accepted
quaternions are normalized to remove only rounding error. Invalid configuration,
wrong coordinate tags and nonfinite arithmetic results throw actionable errors.
Input configuration is defensively copied and frozen. Conversion results are
fresh values and never alias caller data or mutable Three objects.

Tests use known expected coordinates, translations, quarter turns, an oblique
rotation, several scales, both directions, vectors, distance preservation,
invalid inputs and configuration immutability. Patient-space round-trip error
must be <= 1e-9 mm for the tested fixture-scale ranges. This is a numerical test
tolerance, not a statement of medical accuracy or GPU float32 accuracy. Extreme
origins/scales can lose floating-point precision; this contract does not promise
arbitrary-magnitude exact arithmetic.

## Three boundary and integration

`rendering-three/src/three-coordinates.ts` privately converts tagged render points
and displacements to/from fresh Three `Vector3` values. Three world coordinates
use the configured render axes and units exactly. Callers must convert any
mesh-local point to world coordinates before crossing that boundary; screen/NDC
coordinates are not world coordinates. Three types are not exported from the
package's public barrel or introduced into domain packages.

The Three matrix is built from the same transform's basis vectors and origin.
Matrix4.set takes row-major arguments; the Three storage is column-major. Fixture
meshes retain their patient-mm local geometry and X-aligned vessel axes. The
patient-to-render matrix is applied once at their parent group, with matrix
auto-update disabled. Camera position, target, up, clipping distances and light
positions/targets use the same transform. Tests inspect real Three mesh world
matrices and compare camera projections, without requiring a GPU.

The web composition explicitly calls `createFixtureCoordinateTransform()`:
origin `(0,0,12)` mm, identity rotation, and 100 mm per render unit. Both renderer
and scene constructors require a transform. The named fixture helper is solely
an explicit fixture configuration, never a fallback for missing medical data.

Geometry descriptors were moved into an internal fixture-scene module so tests
can inspect the actual rendered primitives. No fixture data, semantic IDs,
Spatial Query behavior, medical state, persistent schema, or external dependency
was changed. GLB loading and image registration remain separate tasks.
