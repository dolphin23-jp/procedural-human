# TASK-A06 — Manual anatomical correction workflow

This workflow consumes the verified TASK-A05 source handoff and V0 candidate output.

It does **not** convert V0 automation into medical validation. A completed TASK-A06 record proves that a human editor reviewed/corrected the authoring representation and records what was changed. TASK-A12/A13 medical review remains separate.

## Current repository state

The current record is:

`authoring/manual-inputs/a06-manual-correction-status-20260909.json`

Its state is intentionally `pending-human-edit`.

No human editor, anatomical review, or medical validation is currently claimed.

The A05 source and candidate output remain source-image-stack only:

- 451 frames
- `avf1567a.png` through `avf1717a.png`
- crop dimensions 550 × 750 px
- no DICOM Patient Space claim
- no CT registration claim

## Required persistent inputs

Source handoff:

`/Procedural Human/A05 Visible Human Female Source/`

The directory must contain exactly:

`chunk-0.zip` through `chunk-9.zip`

Use the byte sizes and SHA-256 values recorded in:

`authoring/source-archives/a05-real-source-verification-20260909.json`

Candidate output:

`/Procedural Human/A05 Real V0 Output/a05-real-v0-output-from-verified-handoff.zip`

Expected SHA-256:

`6a9f302ab5a1efd5d5d9c60e3c29aeee6b2082f3e04df2bcbe880e886b8b3ef4`

## 1. Reconstruct and verify the source stack

Download all ten source chunks into one local directory and run:

```bash
python authoring/source-acquisition/vhp_female_handoff.py \
  --handoff-dir <downloaded-chunk-directory> \
  --source-archive-record authoring/source-archives/visible-human-female.json \
  --output <verified-source-output>
```

Do not continue if archive size/hash, per-crop SHA-256, frame count, ordering, or crop dimensions fail verification.

The reconstructed result remains in source-image-stack coordinates only.

## 2. Load source and V0 candidates into the authoring environment

Use an explicit authoring workspace such as 3D Slicer or another review tool that preserves the slice order and pixel dimensions.

The editor must be able to compare the original cropped photograph and candidate mask on the same source frame.

Do not assign physical spacing, Patient Space coordinates, or CT registration merely to make a viewer convenient.

## 3. Review the available V0 candidates

The original A05 generated structures are:

- skin
- subcutaneous soft tissue
- major muscle/tendon region

Supplemental source-evidence work has also produced:

- radius — partial-support V0 candidate for `avf1567a.png` through `avf1685c.png`
- ulna — partial-support V0 candidate for `avf1567a.png` through `avf1685c.png`
- ulnar artery — bounded continuous V0 candidate for all 106 frames from `avf1646a.png` through `avf1681a.png`

These remain candidate authoring representations. They require human review/correction before TASK-A06 can be complete, and no complete-extent claim is implied outside their documented support interval.

The following remain blocked by source evidence and must not be represented by empty, atlas-substituted, or guessed masks:

- radial artery
- superficial target vein

The current fail-closed vessel diagnostics are recorded in:

`authoring/outputs/a06-vessel-source-diagnostic-provenance-20260909.json`

A human editor may add a previously blocked structure only when the source image itself supports the identity and extent well enough to document the correction. Expected anatomy, atlas position, or a procedure role alone is not evidence.

If the source still does not support a structure, leave it `blocked-source-evidence`.

## 4. Export corrected representations

Preserve:

- exactly the source frames reviewed
- filename/global-frame correspondence
- source-space orientation
- lossless/binary mask semantics
- a reproducible hash for each corrected structure output

Do not overwrite the A05 V0 candidate package.

A corrected output is a new derived authoring representation.

## 5. Record manual-edit provenance

For every structure marked `edited` or `reviewed-no-change`, TASK-A06 provenance requires:

- an editor reference
- authoring tool
- completion time
- corrected output URI/path
- SHA-256 of the corrected output

Use the contract:

`schemas/assets/manual-edit-provenance.v1.schema.json`

A completed human correction record must use:

`manualCorrection.status = "human-correction-recorded"`

The record must still state:

- `medicalValidation = false`
- `anatomicallyReviewed = false`
- `patientSpaceGeometry = false`
- `automaticPromotionAllowed = false`

TASK-A06 is manual authoring provenance, not TASK-A12 anatomical acceptance.

### Validate the completed record against materialized outputs

Before changing the repository status to completed, materialize one reproducible file per structure marked `edited` or `reviewed-no-change` (for example, a structure-specific lossless ZIP export) and run:

```bash
uv run --package ph_assets python -m ph_assets.manual_correction \
  --record <completed-a06-record.json> \
  --output skin=<skin-output.zip> \
  --output subcutaneous_soft_tissue=<subcutaneous-output.zip> \
  --output major_muscle_tendon_region=<muscle-tendon-output.zip>
```

Repeat `--output` for every structure whose status is `edited` or `reviewed-no-change`.

The validator fails closed when:

- any MVP0 A06 structure remains `pending-human-edit`
- a reviewed structure has no materialized output
- the materialized file SHA-256 differs from the provenance record
- a `blocked-source-evidence` structure carries an output
- source-space / non-validation claims are changed
- `claims.humanEdited` disagrees with the actual structure statuses

Passing this validator proves only provenance and file integrity. It does not establish TASK-A12 anatomical review, TASK-A13 procedure-specific review, Patient Space geometry, CT registration, or medical validation.

## 6. Downstream gates

TASK-A07 semantic identity may be assigned independently of whether a geometric representation exists.

TASK-A08 centerlines remain blocked unless the vessel evidence and corrected representation support a continuous vessel.

TASK-A09 boundary/lumen authoring remains blocked without adequate vessel geometry.

TASK-A10 Medical Master promotion is fail-closed until the required upstream authoring gates pass.
