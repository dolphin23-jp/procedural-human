# Imaging contracts and coordinate bridge — TASK-056/057

## Ownership

Patient Truth → Imaging Observation → Imaging Presentation. These runtime
contracts observe the same Patient Space as anatomy and spatial queries. They
neither mutate anatomy nor own acquired pixel data. Source classes remain
`acquired`, `synthetic`, and `hybrid`; technical geometry checks imply no medical
validation. Observation `assetId` resolves provenance/validation through the
asset manifest, not through render names or a new medical metadata model.

- `imaging-core`: Image ↔ Patient geometry; depends only on core/units/math.
- `rendering-core`: existing `PatientRenderTransform`, Patient ↔ Render.
- `session`: `ImageRenderCoordinateBridge` composes those two concrete neutral
  transforms. Neither core subsystem imports the other. This is a small pure
  composition utility, not TASK-082 session lifecycle or live synchronization.

Both new packages compile with ES2022 alone, without DOM, Three, React, or
Cornerstone. The composition root must bind transforms to the same patient and
coordinate reference: existing Patient/Render points and transforms do not carry
patient IDs or frame-of-reference IDs, so this bridge cannot itself verify that
binding. No registration lookup or identity fallback is provided.

## Observation/reference boundary

`ImagingObservation` carries the patient ID and the existing patient-manifest v1
imaging reference fields (id, assetId, sourceType, registrationStatus,
registrationId). `id` remains a nonempty string, matching that schema; asset and
patient IDs retain their existing brands. `registrationId: null` means the
upstream identifier is unavailable, not that geometry should be guessed.

Registered runtime observations require at least one explicit valid frame in
that patient's space. Unknown/unregistered observations have `frames: null` and
cannot be used as a source of patient geometry. These runtime contracts do not
change persistent schemas: a manifest reference alone is insufficient to build
a transform. A future adapter must resolve and validate its spatial metadata.
The frame array order does not assign any implied spatial interval.

## Indices and frames

`ImageVoxelCoordinate(i,j,k)` keeps its existing tagged shape. Indices are
continuous, zero based, dimensionless **sample-center** coordinates. `(0,0,0)`
is the first voxel center, exactly the supplied Patient Space origin in mm.
No implicit `+0.5`/`-0.5` is applied. Integer coordinates identify sample centers;
fractions, negative coordinates, and coordinates outside the buffer are valid
geometry. Buffer access, interpolation, and bounds/clamping are separate tasks.
For N samples along an axis, centers span 0…N−1 and ideal cell support spans
−0.5…N−0.5. This support interpretation does not specify slice thickness.

- i increases the column index within a row.
- j increases the row index within a column.
- k increases the slice index in a regular 3D lattice.
- Di/Dj/Dk are named, dimensionless unit PatientSpaceDirections.
- Si/Sj/Sk are positive center-to-center `Length` values in canonical mm.
- Dimensions are positive safe integers describing sample counts, not lengths.

`VolumeImagingFrame` explicitly declares `volume-3d`, spacing on all three axes,
and basis handedness. Both right- and left-handed index lattices are supported;
left-handed can represent descending slice order in a right-handed patient
reference. The determinant sign must match the supplied handedness. Axes are
not assigned anatomical labels and no LPS/RAS convention is inferred.

`PlanarImagingFrame` explicitly declares `plane-2d` and has no k spacing, k axis,
or fictional volume thickness. Multiple independent planar frames can preserve
unequal slice spacing or per-frame orientation/origin. They are **not** silently
promoted to a regular volume. No continuous k inverse or stack interpolation is
claimed for an irregular collection. Trusted authoring/adapters must either
retain per-frame geometry or explicitly derive a registered regular volume.

## Transform and inverse

For a volume let `B = [Di Dj Dk]`, `S = diag(Si,Sj,Sk)`, `v = (i,j,k)`, and
`O` be the first center in Patient Space:

`P = O + B S v = O + i Si Di + j Sj Dj + k Sk Dk`.

The inverse is `v = S⁻¹ B⁻¹ (P−O)`. With `d = Di · (Dj × Dk)`:

- `i = ((P−O) · (Dj × Dk)) / d / Si`
- `j = ((P−O) · (Dk × Di)) / d / Sj`
- `k = ((P−O) · (Di × Dj)) / d / Sk`

Although metadata must be orthonormal within tolerance, the inverse uses the
actual supplied basis, not its approximate transpose. Accepted rounding
residuals are preserved, not silently normalized or orthogonalized.

For a plane, `P = O + i Si Di + j Sj Dj`. `ImagePlaneTransform` inverts the
2×2 Gram matrix of Di/Dj and rejects points outside the plane tolerance. It is
not a bijection from all 3D Patient Space and does not silently project distant
points onto an image. A residual within numerical tolerance is treated as
rounding on the plane.

`PatientImagingPlane` retains origin, Di, Dj and the derived unit normal
`normalize(Di × Dj)`. Deriving a unit normal does not modify supplied axes.
Normal alone would discard image rotation about that normal. This plane carries
no clipping half-space, sample spacing, or thickness. `planeAtK(k)` locates its
origin at `voxelToPatient(0,0,k)` and keeps Di/Dj; with left-handed indexing the
normal points opposite Dk. Fractional k is allowed; no resampling is performed.

For the existing render rotation R, patient origin A and scale s (mm/unit):

- `r = R(P−A)/s`
- `P = A + s R⁻¹ r`
- Image → Render is `PatientRenderTransform.patientPointToRender(voxelToPatient(v))`.
- Render → Image is `patientToVoxel(PatientRenderTransform.renderPointToPatient(r))`.

The session bridge calls these methods directly; it duplicates no matrix math.

## Validation and tolerances

Factories and transform constructors validate tags, finite components, positive
finite spacing with finite reciprocals, positive safe-integer dimensions, and
explicit kind/index convention/handedness. Invalid geometry throws TypeError or
RangeError; unknown transforms never become identity. Inputs are defensively
copied and deeply frozen; output coordinates do not alias input metadata.

`IMAGE_BASIS_TOLERANCE = 1e-9` is dimensionless: unit-norm error and pairwise
absolute dot products must be within it. A determinant magnitude below
`1 − 4*tolerance` is rejected (the factor covers accumulated norm roundoff).
Zero/parallel axes, shear outside that tolerance, and wrong determinant signs
fail. Accepted axes are not repaired. Constructors accept typed metadata; the
future ingest adapter still owns parsing and registration trust.

`IMAGE_PLANE_TOLERANCE_MM = 1e-9` is an absolute off-plane arithmetic residual.
All transforms check nonfinite inputs and arithmetic outputs, including overflow.
Double precision cannot promise reversibility for arbitrarily large origins,
extreme spacing ratios, or sub-resolution displacements; finite arithmetic alone
is not clinical registration validation. No broad medical accuracy is claimed.

The bounded synthetic fixture uses absolute assertions of `1e-10` patient mm,
`1e-10` voxel units, and `1e-11` render units. These cover double-precision
roundoff at fixture scales while decisively detecting axis, scale, sign, and
translation errors. Metadata tolerance and coordinate error tolerance are
separate quantities. TASK-062's comprehensive suite remains later work.

## Synthetic volume

`fixtures/imaging/synthetic-volume-v1.mjs` generates 4×3×3 scalar samples with
`value = i + 10*j + 100*k`, i fastest. It is synthetic imaging with explicit
**development-fixture / V0** provenance, no acquired data or medical validation.
Its source reference resolves to that in-repository fixture module; it is not a
released medical asset manifest. Scalars are not CT attenuation values.

- O = (13,−21,34) mm
- Di = (0.6,0.8,0), Dj = (−0.48,0.36,0.8), Dk = (0.64,−0.48,0.6)
- S = (0.7,1.3,2.5) mm
- Patient→Render uses A = (−7,9,11) mm, +90° about Z, s = 10 mm/unit.

For example `(2,1,2)` → `(16.416,−21.812,38.04)` mm →
`(3.0812,2.3416,2.704)` render units. Independently calculated axis landmarks and
fractional/negative coordinates establish the forward and inverse meaning.
Tests also feed valid but wrong axis/sign configurations to the landmark oracle,
exercise descending slices, immutable snapshots, invalid frames, 2D off-plane
rejection, irregular frame collections, and compile-time coordinate boundaries.

## Later adapters

Authoring/Cornerstone adapters may translate trusted source origins, in-plane
orientations, spacings and frame-of-reference relationships into these neutral
contracts. They must explicitly resolve source axes into the patient's reference
and preserve source identity/registration lineage. A mere match in patient ID is
not proof of spatial registration. Preserve per-frame origins for irregular
stacks; do not substitute slice thickness for center spacing. No DICOM field
names, parser, medical datasets, CT logic, viewer, or TASK-058+ UI/synchronization
are implemented here.
