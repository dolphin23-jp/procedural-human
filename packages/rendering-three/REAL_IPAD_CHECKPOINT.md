# TASK-053 — Real iPad navigation checkpoint

This checkpoint is intentionally manual. CI, desktop browsers, simulators, and automated WebKit are not substitutes for a physical iPad running Safari.

## Result

**PASS — 2026-09-07**

A physical iPad Safari check was completed against the GitHub Pages deployment from commit `2c8b1761299b3a8291d6b1acae5a81f9d2375ceb`. All required TASK-053 interactions and orientation behavior were reported working without observed gesture, scrolling, selection-offset, or usability defects.

Device model and browser/OS version were not recorded and are not inferred here.

## iPad-only access

The checkpoint viewer is deployed with GitHub Pages so the physical-device check can be completed without a development PC.

- https://dolphin23-jp.github.io/procedural-human/

### One-time Pages enablement

GitHub requires the repository owner to enable Pages once before the deployment workflow can create the site. This has been completed for this repository.

Later pushes to `main` or `task-048-053-runtime-interaction` deploy automatically.

The Pages workflow builds the web app with the repository base path and deploys `apps/web/dist`. During TASK-053 it deploys from both `task-048-053-runtime-interaction` and `main`; after the task branch is merged, `main` remains the durable source.

## Implementation exercised by the checkpoint

The M4 fixture viewer exposes:

- one-finger drag: orbit around the semantic Patient Space focus point;
- two-finger translation: pan;
- pinch: dolly/zoom;
- tap: Three raycast followed by semantic resolution to `PatientStructureInstance` and canonical `AnatomicalEntity`;
- desktop equivalents: drag to orbit, Shift-drag to pan, wheel to zoom, click to select.

Input is normalized into renderer-neutral `CameraIntent` values before camera mutation. Orbit axes and clipping normals use dimensionless `PatientSpaceDirection`; physical pan remains `PatientSpaceVector` in millimetres.

## Physical-device record

- Date: 2026-09-07
- iPad model: not recorded
- iPadOS version: not recorded
- Safari version/build if observable: not recorded
- App commit: `2c8b1761299b3a8291d6b1acae5a81f9d2375ceb`
- Orientation(s) checked: portrait / landscape — PASS
- Rotate/orbit: PASS
- Pinch zoom: PASS
- Two-finger pan: PASS
- Tap selection: PASS
- Resize/orientation-change rendering: PASS
- Any accidental page scrolling/zooming during canvas gesture: none observed
- Any obvious frame stalls, gesture loss, or selection offset: none observed
- Notes: User completed the physical iPad Safari checkpoint and reported all requested checks working normally.

## Acceptance rule

PASS requires all four TASK-053 actions—rotate, zoom, pan, select—to work on real iPad Safari without a coordinate-space error, semantic-name fallback, or gesture behavior that makes the fixture unusable. The recorded result satisfies this acceptance rule.

**Gate E: PASS.**
