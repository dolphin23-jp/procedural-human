# TASK-053 — Real iPad navigation checkpoint

This checkpoint is intentionally manual. CI, desktop browsers, simulators, and automated WebKit are not substitutes for a physical iPad running Safari.

## iPad-only access

The checkpoint viewer is deployed with GitHub Pages so the physical-device check can be completed without a development PC.

Expected URL after the Pages workflow succeeds:

- https://dolphin23-jp.github.io/procedural-human/

### One-time Pages enablement

GitHub requires the repository owner to enable Pages once before the deployment workflow can create the site. This can be done entirely on the iPad:

1. Open the repository in Safari while signed in to GitHub.
2. Open `Settings` → `Pages`.
3. Under `Build and deployment`, set `Source` to `GitHub Actions`.
4. Re-run the `Deploy iPad Preview` workflow, or make another commit to the checkpoint branch.

After this one-time repository setting, later pushes to `main` or `task-048-053-runtime-interaction` deploy automatically.

The Pages workflow builds the web app with the repository base path and deploys `apps/web/dist`. During TASK-053 it deploys from both `task-048-053-runtime-interaction` and `main`; after the task branch is merged, `main` remains the durable source.

On the iPad:

1. Open the Pages URL above in Safari.
2. Confirm the page says `Synthetic anatomy fixture` and `Development fixture · not medical anatomy`.
3. Run the interaction checks below in both portrait and landscape.
4. Report PASS/FAIL and any gesture or selection defect. Do not substitute a desktop or simulator result.

## Implementation ready for the checkpoint

The M4 fixture viewer now exposes the interaction path required by TASK-053:

- one-finger drag: orbit around the semantic Patient Space focus point;
- two-finger translation: pan;
- pinch: dolly/zoom;
- tap: Three raycast followed by semantic resolution to `PatientStructureInstance` and canonical `AnatomicalEntity`;
- desktop equivalents: drag to orbit, Shift-drag to pan, wheel to zoom, click to select.

Input is normalized into renderer-neutral `CameraIntent` values before camera mutation. Orbit axes and clipping normals use dimensionless `PatientSpaceDirection`; physical pan remains `PatientSpaceVector` in millimetres.

## Required physical-device record

Do not mark TASK-053 complete until a physical device has been checked and the following record has been filled in.

- Date:
- iPad model:
- iPadOS version:
- Safari version/build if observable:
- App commit:
- Orientation(s) checked: portrait / landscape
- Rotate/orbit: PASS / FAIL
- Pinch zoom: PASS / FAIL
- Two-finger pan: PASS / FAIL
- Tap selection: PASS / FAIL
- Resize/orientation-change rendering: PASS / FAIL
- Any accidental page scrolling/zooming during canvas gesture:
- Any obvious frame stalls, gesture loss, or selection offset:
- Notes:

## Acceptance rule

PASS requires all four TASK-053 actions—rotate, zoom, pan, select—to work on real iPad Safari without a coordinate-space error, semantic-name fallback, or gesture behavior that makes the fixture unusable. Record defects instead of weakening the semantic or coordinate contracts to accommodate the device.
