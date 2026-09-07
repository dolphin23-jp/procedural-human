# imaging-cornerstone

Cornerstone-specific browser adapter for Procedural Human medical imaging.

TASK-058/059 intentionally keep all `@cornerstonejs/*` imports in this package.
`imaging-core` remains technology-neutral and continues to own Image ↔ Patient
geometry.

## Dependency decision

- `@cornerstonejs/core` 5.8.2 (MIT) provides volume caching, local volume
  creation, and GPU-backed orthographic volume viewports.
- `@cornerstonejs/metadata` 5.8.2 is installed explicitly to satisfy the
  current Cornerstone core peer contract.
- No Cornerstone tools or DICOM loader are added yet. TASK-058 loads a
  deterministic in-memory development fixture only.
- The dependency is browser/iPad-oriented but materially increases the web
  bundle. It is isolated here so later loading/splitting can be optimized
  without coupling domain geometry to Cornerstone.

The bundled calibration volume is a software fixture only. It is not anatomy,
not CT, and has validation level V0.

## TASK-060/061 synchronization port

The adapter implements the neutral `AxialImagingViewport` port in imaging-core.
`setPatientPlane` translates the axial camera, validates source-plane alignment,
and returns readback with separate display index/source k. Session composes it
with rendering; see [synchronization contract](../session/IMAGING_SYNC.md).

### Browser entry prerequisite

vtk.js 36.4.1 imports xmlbuilder2 4.0.3's Node entry, which evaluates an
`EventEmitter` subclass during module loading. Vite externalizes Node `events`
and `url`, so a successful build can still produce a blank browser page.
`apps/web/vite.config.ts` resolves xmlbuilder2 to the same installed version's
published browser bundle, including its upstream polyfills. No API is stubbed
and no dependency version changes. A VM regression test initializes that bundle
without Node globals and exercises XML creation.
