# M8V — Vessel Identification Evidence Lane

## Purpose

M8V exists to resolve the current MVP 0 vascular identity blocker without turning image-processing confidence, anatomical plausibility, atlas registration, or procedure role into medical truth.

The lane answers a narrower question than segmentation:

> What evidence is sufficient to assign a medically meaningful vessel identity or procedure role to an observed same-subject structure, and what remains unresolved?

M8V is an authoring-support lane between the completed M8S same-subject continuity work and M8A Medical Master promotion. It does not weaken the requirements of `DATA_POLICY.md`, `MVP0.md`, or TASK-A10.

Current blocker at lane creation (2026-09-10):

- the bounded ulnar-artery work remains source-supported and is preserved;
- `structure.radial_artery.left` remains unresolved;
- the distal superficial venous target remains unresolved as a defensible same-subject structure/track;
- cephalic/basilic naming must not be inferred from local position alone;
- TASK-A10 therefore remains fail-closed blocked.

## Governing rules

Authority remains:

1. `MASTER_SPEC.md`
2. `ARCHITECTURE.md`
3. `DATA_POLICY.md`
4. `MVP0.md`
5. `DEVELOPMENT_RULES.md`
6. `TASKS.md`
7. this document

The evidence hierarchy follows `DATA_POLICY.md`. For this lane, practical priority is:

1. direct observation in the same Visible Human Female subject;
2. same-subject continuity/branch topology;
3. same-subject CT/MRI evidence with explicit registration status;
4. same-subject anatomical landmark relationships;
5. validated atlas/literature used as inspection guidance or constraints;
6. expert/AI inference, explicitly unvalidated.

Lower-authority evidence may guide where to inspect. It may not silently replace missing same-subject geometry or identity.

## Separate claims; never collapse them into one confidence score

Each candidate may carry independently supported or unresolved claims for:

- observed structure existence;
- vessel class (artery/vein/unknown);
- named anatomical identity;
- same-subject geometry;
- longitudinal continuity;
- branch/merge topology;
- superficial/deep compartment relationship;
- landmark relationships;
- cross-modality registration;
- procedure role suitability;
- review/validation state.

A candidate can therefore be a source-supported superficial vein without being defensibly nameable as the cephalic or basilic vein.

## Observed structure identity versus named anatomy versus procedure role

These are different layers.

A same-subject observed structure may receive a subject-scoped identifier such as:

`vhf.left.distal_forearm.superficial_vein.01`

without receiving a canonical named identity.

That observed structure may later be bound to the procedure role `venous_access_target` if procedure-specific review supports that use. Procedure role never proves that the structure is the cephalic vein, basilic vein, or another named vessel.

For the radial artery, the named identity gate is intentionally stricter because arterial boundary recognition is a safety-relevant MVP behavior and the same anatomy is expected to support later radiocephalic AVF work.

## Registration policy

CT/MRI availability does not establish registration.

Registration work must:

- remain explicit about source coordinate systems;
- use stable non-vascular landmarks first, especially bone;
- record transforms, residuals, supported extent, and failure regions;
- distinguish nominal source-index correspondence from established spatial registration;
- never use a vessel candidate as the landmark that proves its own identity;
- never claim Patient Space until the applicable imaging/coordinate requirements are actually met.

The existing A06 same-cadaver CT/bone candidate work is reusable evidence. It is not upgraded automatically by being referenced from M8V.

## Landmark evidence

Upper-extremity landmark evidence may include source-supported relationships to:

- radius and ulna;
- radial/ulnar styloid regions where observed;
- brachioradialis;
- flexor carpi radialis;
- pronator quadratus;
- major flexor/extensor compartments and tendons;
- deep fascia and subcutaneous plane;
- other stable observed structures useful for localizing a vessel track.

Landmarks are evidence constraints, not a license to draw textbook anatomy into the subject.

## Vessel track graph

M8V treats vascular identification as a graph/evidence problem rather than independent per-slice classification.

A track representation should be able to record:

- observed nodes/segments;
- continuation edges;
- branch/merge candidates;
- explicit gaps;
- competing tracks;
- source frames and coordinates;
- derivation method;
- cross-modality/landmark evidence references;
- review status.

Gaps must remain gaps. Interpolation may be produced as an explicit derived hypothesis but cannot be counted as direct observation.

## Promotion gates

### Radial artery named identity

Promotion to `structure.radial_artery.left` requires all of the following at the scope being promoted:

1. a defensible same-subject proximal or otherwise unique arterial anchor;
2. continuous or explicitly bounded-gap same-subject tracking to the target region;
3. compatible branch topology, including the relevant brachial/radial/ulnar relationship where used as evidence;
4. compatible source-supported landmark relationships;
5. no competing candidate with equal or better evidence left unresolved;
6. explicit human anatomical review of the identity claim.

CT/MRI or atlas position alone is insufficient.

### Superficial target vein structure

Promotion of a subject-scoped observed superficial vein does not require cephalic/basilic naming. It requires:

1. direct same-subject vessel observations over a procedure-relevant extent;
2. continuity sufficient to establish one observed structure rather than isolated blobs;
3. source-supported superficial/subcutaneous relationship;
4. defensible vessel-class evidence as a vein;
5. competing-track/conflict review;
6. explicit human anatomical review of the structure/class/relationship claims.

Procedure-role binding to `venous_access_target` is a later, separate procedure-suitability decision.

### Named superficial vein identity

Cephalic/basilic or other named identity requires additional topology/course evidence appropriate to that name and must not be inferred merely because a vessel is superficial or radial/ulnar in a local field.

## Machine-readable evidence

M8V records should reference immutable or content-addressed evidence wherever available. Evidence records must expose unsupported claims explicitly and must remain valid when the correct answer is `unresolved`.

A record marked `complete` means the assigned evidence task completed its bounded work. It does not mean that vessel identity, registration, medical validation, or Medical Master promotion succeeded unless those claims are separately true.

## Ordered tasks

### TASK-V01 — Same-subject radiological source inventory

Inventory the Visible Human Female CT/MRI source material relevant to M8V, its metadata/header distributions, existing bounded acquisition/probe tooling, persistence status, and registration status.

Done when available source collections and current limitations are machine-readable and reproducible. No registration or vessel identity is claimed.

### TASK-V02 — Cryosection ↔ CT registration scaffold

Establish a bounded same-subject CT-to-cryosection registration workflow using non-vascular landmarks first. Record transforms, residuals, supported extent, and failure state. Do not claim Patient Space merely from this authoring registration.

### TASK-V03 — Upper-extremity landmark graph

Create source-supported upper-extremity landmark observations and relationships needed to constrain candidate vessel identity. Keep unobserved landmarks unknown.

### TASK-V04 — Candidate vessel 3D track graph

Represent observed vascular candidates across frames as tracks with continuation, branch/merge candidates, explicit gaps, competitors, and provenance.

### TASK-V05 — Radial arterial identity evidence

Re-evaluate the arterial path using direct cryosection evidence, the preserved ulnar anchor, broader continuity, registered same-subject CT where informative, branch topology, and landmarks. Apply the radial promotion gate without relaxing criteria after seeing the result.

### TASK-V06 — Superficial venous network evidence

Trace the same-subject superficial venous network over a useful extent. First establish observed superficial vein structures; do not force cephalic/basilic identity.

### TASK-V07 — Multimodal review surface

Provide synchronized review of cryosection, CT (and MRI only where useful), candidate tracks/overlays, landmarks, and evidence/provenance. Review UI does not itself confer validation.

### TASK-V08 — Evidence ledger

Create the durable machine-readable evidence ledger linking each medically meaningful claim to supporting, conflicting, missing, algorithm-derived, and human-review evidence.

### TASK-V09 — Identity promotion evaluator

Implement fail-closed promotion rules for radial-artery identity, subject-scoped superficial-vein structure, and named superficial-vein identity. No single scalar confidence may substitute for required criteria.

### TASK-V10 — Feed M8V evidence into M8A

Feed only passed claims/representations back into A06/A07/A08/A09 and reevaluate A10. Preserve historical evidence and valid ulnar work. If required gates still fail, A10 remains blocked.

## Current task state

- TASK-V01: complete — see `authoring/outputs/m8v-v01-radiological-source-inventory-20260910.json`.
- TASK-V02: next.
- TASK-V03 through TASK-V10: not started by this lane definition.

No M8V task currently claims radial-artery identity, named superficial-vein identity, medical validation, Patient Space, or Medical Master promotion.
