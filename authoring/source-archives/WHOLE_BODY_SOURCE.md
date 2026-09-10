# Visible Human Female whole-body source foundation

## TASK-AS01 checkpoint — 2026-09-10

The selected source is **5,186 unique provider PNG cryosections**, from
`avf1001a.png` to `avf2730b.png`, totaling **16,452,622,136 listed source bytes**
(16.45 GB / 15.32 GiB). This is one subject, `source.nlm.vhp-female`.

The immutable inventory is
`vhf-whole-body-inventory-20260910.json`. It binds observed listing snapshots,
source URLs, exact listed byte sizes, provider dates, ordering, overlapping
folder alternatives, and the deterministic 64-frame / 82-chunk plan.

### Scope and missing material

- Six provider partitions: head, thorax, abdomen, pelvis, thighs, legs.
- 7,106 listed regional PNG objects reduce to 5,186 distinct filenames. Folder
  overlap is retained as alternative-location metadata, not a claim of byte
  equivalence. Selection prioritizes abdomen to preserve all A05 source URLs.
- The NLM overview describes 5,189 sections. Both the current PNG lists and the
  historical `Fullcolor/fullbody` INDEX enumerate 5,186. The interior gaps are
  `avf2328c.png`, `avf2329a.png`, `avf2329b.png`. Nothing fills those gaps.
- The last observed frame is `avf2730b.png`; no `avf2730c.png` is invented.
- Provider filenames are an ordered source index, not Patient Space.
- 2048 × 1216 pixels and nominal 0.33 mm spacing are provider documentation;
  actual PNG headers are checked during acquisition. No calibrated origin,
  orientation, z positions, or CT registration are asserted.
- CT/MRI and their headers are inventoried in both legacy and PNG folders;
  they are not part of this bulk cryosection acquisition. The inventory records
  object counts and listed bytes, including READMEs where present; these are
  not automatically imaging frame counts.
- Legacy raw.Z is an alternative distribution, not a second bulk copy. Provider
  PNG is recommended by NLM; no local image conversion is labeled original.

### Terms checkpoint

Current NLM documentation describes VHP as public-domain data and states that
an access license is no longer required as of 2019. This supersedes the older
Fullcolor README's reference to a written access license. Modification,
derivatives, commercial applications and redistribution are within the stated
public-domain scope, subject to the published conditions. This is an
engineering terms checkpoint, not a new license or medical approval.

Courtesy of the U.S. National Library of Medicine

No NLM endorsement is implied. This snapshot may not reflect the most current
or accurate NLM data. NLM gives no accuracy or fitness warranty. See:

- https://www.nlm.nih.gov/databases/download/terms_and_conditions.html
- https://www.nlm.nih.gov/research/visible/visible_human.html
- https://www.nlm.nih.gov/research/visible/getting_data.html

The exact downloaded listing/README/terms/overview evidence is retained in
`vhf-source-evidence-20260910.zip`, Library file
`libfile_17a242c927c48191b4fb32fb6c9734da`, under
`/Procedural Human/AS Whole Body Visible Human Female Source/`.
Every required evidence member's SHA-256 is in the inventory. The old INDEX
contains historical timestamps; they are not mistaken for retrieval dates.

## TASK-AS02/AS03 archive protocol

The durable source store is the repository's **draft release** with tag
`source-vhf-png-20260910`. Large source bytes are release assets, never Git blobs.
Actions artifacts are only temporary transport for small verification receipts.

Each `vhf-source-NNNN.zip` contains unchanged provider PNG bytes at their source
paths and a schema-validated `manifest.json` with per-file SHA-256, size, PNG
geometry, URL and retrieval metadata. ZIP member order, timestamps and chunk
membership are fixed. Acquisition timestamps make a fresh retrieval a new
snapshot; byte-for-byte ZIP reproducibility is claimed only with identical
source bytes and identical manifests, not across fresh retrieval timestamps.

The workflow verifies local bytes, saves each chunk, downloads the saved asset
again, and verifies every PNG hash. Existing assets are verified and reused;
there is no `--clobber` or silent upstream replacement. A changed upstream
source requires a new reviewed inventory/tag, not editing this snapshot.

Finalization requires exactly all 82 chunk receipts from one inventory hash,
correct frame counts and matching release asset identities/sizes. It produces
`vhf-source-archive-index-20260910.json` and `vhf-source-storage-20260910.json`,
retains them as release assets, and commits metadata to the work branch.
**Until finalization succeeds, AS02 is incomplete**, even if some assets exist.
A draft release stays restricted to repository users who can access drafts;
it is not silently published as a public runtime dataset.

Storage requirement is about 16.46 GB for one archived copy plus temporary
chunk space. A local all-chunk run uses about 17 GB; a release shard processes
one chunk at a time and does not need full-body disk capacity. Each failed
chunk can be retried; completed chunks are re-hashed before reuse. Re-download
and image verification may be expensive but do not consume model agents.

## Reproducible commands

Standalone authoring dependencies: `jsonschema==4.25.1`, `pillow==11.3.0`.
They are confined to authoring; browser/runtime dependencies are unchanged.
Use a Python environment containing those dependencies, or:

```sh
uv run --no-project --with jsonschema==4.25.1 --with pillow==11.3.0 python authoring/source-acquisition/vhf_whole_body.py --help
```

Examples (replace local archive/output paths):

```sh
python authoring/source-acquisition/vhf_whole_body.py acquire --inventory authoring/source-archives/vhf-whole-body-inventory-20260910.json --output /external/vhf --first 0 --last 81
python authoring/source-acquisition/vhf_whole_body.py index --inventory authoring/source-archives/vhf-whole-body-inventory-20260910.json --archive /external/vhf --output /external/archive-index.json
python authoring/source-acquisition/vhf_whole_body.py extract --inventory authoring/source-archives/vhf-whole-body-inventory-20260910.json --index /external/archive-index.json --archive /external/vhf --first 1698 --last 2148 --crop 1450 250 2000 1000 --output /external/a05-derived
```

## TASK-AS04 contract

Select inclusive global frame indices explicitly. The A05 range is 1698–2148
(451 frames), with crop `[1450, 250, 2000, 1000]`. Index 0 is `avf1001a.png`.
Indices are not millimetres. Future proximal-forearm, antecubital, upper-arm
and other selections use this same mechanism; their anatomical boundaries
must be observed, not inferred from folder labels.

Extraction validates each required chunk and file before writing, refuses an
existing output directory, retains source identity, and records output hashes,
parent inventory/index/chunk/source hashes, and crop parameters. No-crop copies
are byte-identical. Crops are explicit derived PNGs, never a new source archive.
Existing A05/A06 records are unchanged. New evidence does not promote any
segmentation, vessel identity or Medical Master.

AS05 navigation and AS06/AS07 vascular tracing remain separate tasks. None of
this source work unblocks A10 by itself or closes Gate S.
