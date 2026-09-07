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
