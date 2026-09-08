# Image / 3D plane synchronization — TASK-060/061/063

`ImagingPlaneSynchronizer` composes neutral `AxialImagingViewport` and
`PatientPlaneImagingViewport` ports with a rendering `setClippingPlane` port. Session owns the shared immutable state and
command ordering. Neither imaging nor rendering imports the other adapter.
This does not implement TASK-082 SimulationSession lifecycle or an Event Bus.
There are no persistent schema changes or new third-party dependencies.

The caller must explicitly bind the volume frame and both ports to the same
Patient Space. The calibration volume and synthetic anatomy use their declared
fixture coordinates; they are independent **development-fixture / V0** data,
not a registered medical image/anatomy pair. No registration is inferred and no
medical landmark correspondence is claimed.

## Commands and acknowledgement

- Image slider/wheel → `setImageSlice` / `scrollImage` → image readback → shared
  `PatientImagingPlane` → Three clipping plane and visual guide.
- 3D source-plane slider → `setPlaneAtVoxelK` → ImagePatientTransform →
  `setPatientPlane` → Cornerstone camera translation → readback → both controls.
- A caller with a Patient Space plane can use `setPatientPlane` directly.
  Source axial planes retain `AxialSliceState`; arbitrary oblique MPR commits the
  shared `PatientImagingPlane` with `slice = null` rather than inventing source-k metadata.

For declared axial source-plane commands, Cornerstone translates the current
focal point only along the target plane normal, preserving in-plane pan. Camera
distance and presentation zoom are retained while orientation is aligned to the
source plane. Source k is recovered from actual focal-point coordinates and
display index is read independently. The adapter never assumes
`displayIndex === k` or `displayIndex === count - 1 - k`.

For arbitrary TASK-063 oblique commands, the explicitly requested
`PatientImagingPlane` supplies the focal-plane origin and orientation. Camera
distance is preserved, and the actual camera plane is read back before Session
commits the shared Patient Space plane.

TASK-061 source-k navigation remains restricted to declared axial sample planes.
TASK-063 adds arbitrary oblique MPR through the generic Patient Space plane port.
The Cornerstone camera basis is read back and checked before the shared plane is
committed. Oblique state intentionally has no source `displayIndex`/`voxelK`.
Returning to an explicit source-k command restores axial source-plane semantics.
The existing `1e-4` voxel-k readback tolerance covers Cornerstone numerical
error, not medical
registration accuracy or arbitrary snapping. An accepted request moves to the
canonical sample plane, then validates readback. Wheel input explicitly stops
at volume ends; the public plane command never silently clamps.

All image mutations run in input order with at most one command in flight.
Readback alone commits state. Rendering is a command sink, so readback does not
cause image → rendering → image feedback. Failures propagate to callers, clear
the stale 3D plane and expose an error; later valid commands can recover.
Disposal suppresses late results and queued mutations. Viewport resources stay
owned by the caller, which disposes the synchronizer before its adapters.

The clipping toggle controls presentation only. While it is off, image/plane
state still follows navigation; re-enabling shows the latest plane. The 3D
plane slider has discrete source-k positions, usable with touch or keyboard.
The guide does not alter anatomy, source scalar data or spatial queries.

## Verification

`tests/imaging-sync.test.mjs` covers both directions, reversed display order,
nonidentity render origin/rotation/scale, descending k, anisotropic spacing,
unsupported geometry, queued mixed input, error recovery, volume ends, clipping
toggle and disposal. Existing imaging/rendering/schema/boundary tests remain.

Browser checks: move each slider to both ends, wheel the image, toggle clipping,
rotate/zoom the 3D camera, and resize/reorient the page away from the center
slice. Source k and Patient plane Z must agree across both panels. Real iPad
acceptance must still be performed on the device; desktop checks do not certify
it. Side-by-side layout and comprehensive round trips remain TASK-064 / TASK-062.
