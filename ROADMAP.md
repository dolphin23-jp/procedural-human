# Procedural Human — Project Direction and Roadmap

Status: project-direction record  
Decision date: 2026-09-10  
Implementation snapshot: `main@71812a0a5779d358a748f9c41bc0a02a9bc99145`

This document records the current project direction, the immediate authoring strategy, and the intended path from MVP 0 to the long-term Procedural Human platform.

It does not override higher-authority specifications. Authority remains:

1. `MASTER_SPEC.md`
2. `ARCHITECTURE.md`
3. `DATA_POLICY.md`
4. `MVP0.md`
5. `DEVELOPMENT_RULES.md`
6. `TASKS.md`

If this roadmap conflicts with those documents, the higher-authority document wins and the conflict must be resolved explicitly before implementation.

## 1. Long-term product direction

Procedural Human is intended to become one coherent digital human in which anatomy, physiology, physics, imaging, instruments, interaction, events, and procedure evaluation refer to the same patient and the same spatial/temporal world.

The long-term target is broader than a single procedure or body region:

- medically grounded whole-body normal anatomy;
- cross-sectional and 3D anatomical exploration;
- CT/reference imaging and later additional modalities;
- dynamic musculoskeletal anatomy;
- cardiac and respiratory motion;
- progressively refinable physiology and hemodynamics;
- ultrasound and Doppler as observations of the same patient;
- reusable generic instruments and interaction mechanics;
- multiple procedural simulators built on the shared patient rather than separate bespoke simulators;
- later pathology, anatomical variation, and patient/case diversity.

The target is not a monolithic maximum-fidelity whole body at all times. Fidelity is regional and purpose-dependent: whole-body context may be lower detail while a procedure field is high fidelity and explicitly validated.

## 2. Current implementation snapshot

As of `main@71812a0a5779d358a748f9c41bc0a02a9bc99145`:

### Core/runtime

- M0 repository foundation: complete.
- M1 contracts/schemas: complete.
- M2 anatomy/patient domain: complete.
- M3 Spatial Query Core: complete through TASK-044.
- M4 3D Runtime: complete through TASK-055.
- M5 Medical Imaging Bridge: complete through TASK-064.
- M6 Instrument and Interaction:
  - TASK-065 through TASK-072 are implemented.
  - generic instrument/needle state, normalized input, mouse control, touch/Apple Pencil control, Interaction Engine, and first-contact detection exist.
  - TASK-073 is the next numbered mainline interaction task.
- M7 Events, Procedure, Replay has not yet begun.

The existing runtime therefore already has the core architectural path needed to connect patient-space anatomy, rendering, imaging, generic needle movement, Spatial Query, and contact observation without embedding procedure knowledge into those layers.

### Medical-asset authoring lane

The current real-data authoring work uses the NLM Visible Human Female dataset.

Completed or established:

- TASK-A01 through TASK-A05: selected source, source records/tooling, bounded distal forearm/wrist ROI, and real V0 candidate segmentation pipeline.
- TASK-A06: human source-mask review recorded through the iPad review workflow.
- TASK-A07: semantic mapping exists for supported structures.
- TASK-A08/A09: a bounded 106-frame ulnar-artery candidate has progressed to source-stack centerline and lumen/boundary representations.

Current fail-closed state:

- left radial artery: semantic identity is reserved, but no accepted same-subject representation is established.
- superficial target vein: named anatomical identity and accepted representation remain unresolved.
- TASK-A10 Medical Master v0 therefore remains blocked.

The project also tested a direct cross-subject Z-Anatomy/BodyParts3D vessel-registration fallback and rejected it after the predeclared holdout gate failed. That negative result is retained as evidence. Cross-subject atlas geometry must not be silently promoted as Visible Human Female patient-specific geometry.

## 3. 2026-09-10 source strategy decision

The project will no longer treat the distal forearm ROI as the maximum source-evidence extent.

Instead:

> Ingest and preserve the usable whole-body source dataset first; author, validate, and ship Medical Masters region by region.

This is a source-foundation expansion, not an MVP 0 product-scope expansion.

### 3.1 What expands now

The authoring source foundation may include the entire usable Visible Human Female anatomical source stack and supporting same-subject modalities where licensing, availability, and metadata permit.

The source foundation should provide:

- immutable source retention outside Git;
- chunked/content-addressed storage;
- dataset/version/retrieval/license records;
- per-file or per-chunk hashes sufficient for reproducibility;
- a global frame/source index;
- reproducible region extraction;
- source-space navigation across anatomical regions;
- preservation of original source ordering and documented spatial metadata;
- explicit separation between source coordinates and Patient Space until a valid mapping is established.

### 3.2 What does not expand now

This decision does **not** authorize:

- whole-body segmentation for MVP 0;
- whole-body Medical Master creation for MVP 0;
- whole-body medical validation for MVP 0;
- whole-body runtime packaging for MVP 0;
- implementation of post-MVP physiology/physics merely because the source data is available.

MVP 0 acceptance remains limited to the medically grounded left distal forearm/wrist region defined in `MVP0.md`.

### 3.3 Why whole-body source is needed

The current distal-only crop is insufficient for reliable identity assignment of some small vessels.

For structures with branch/continuity anatomy, identity should preferentially be established by tracing the same subject from a more defensible anchor rather than by local appearance alone.

For example:

```text
brachial artery
  -> observed bifurcation
      -> radial artery branch
      -> ulnar artery branch
          -> distal forearm ROI
```

The evidence chain should record actual same-subject continuity wherever observable.

For superficial veins, the project should likewise use same-subject continuity and characteristic course/connection evidence. Anatomical position alone is not sufficient to force a cephalic/basilic identity where the source does not support it.

This changes the authoring strategy from:

`local appearance inference`

toward:

`same-subject continuity + topology + local appearance + review`.

## 4. Evidence hierarchy for anatomical identity

For patient/cadaver-specific geometry, use the following priority:

1. direct same-subject source evidence;
2. same-subject continuity/topology from a defensible anatomical anchor;
3. same-subject supporting modality with explicitly verified registration;
4. atlas/literature/anatomical prior as hypothesis generation or independent plausibility evidence;
5. unresolved/unknown.

An atlas may guide where to inspect, help define expected topology, or support review. It does not become acquired same-subject geometry merely through registration.

If source evidence and prior expectations disagree, preserve the disagreement and lower the claim rather than deforming the observed anatomy to match the atlas.

## 5. Immediate execution plan

A new supporting source-foundation lane is defined in `TASKS.md`.

Its purpose is to unblock the missing vascular identities without discarding the existing A01-A09 work.

The immediate sequence is:

```text
whole-body source inventory
  -> full source acquisition / immutable external archive
  -> global source manifest and index
  -> reproducible region extraction / navigation
  -> same-subject upper-extremity vascular tracing
  -> update radial-artery and superficial-vein evidence
  -> rerun A06/A07 evidence state where necessary
  -> complete A08/A09
  -> unblock A10 Medical Master v0
```

Existing accepted distal-forearm outputs remain valid within their stated provenance and support ranges. They are not thrown away because the source scope expands.

## 6. A10 unblock rule

TASK-A10 must remain blocked until the mandatory MVP vascular structures have defensible representations.

At minimum:

### Radial artery

A representation must be grounded in same-subject evidence with sufficient identity support. The preferred route is continuity from a clearly identified proximal arterial tree/bifurcation into the distal region.

A local candidate that merely lies near the radius is insufficient.

### Superficial target vein

The project must establish either:

- a defensible named superficial vein identity, such as cephalic vein, or
- an explicitly validated equivalent superficial target vein acceptable under `MVP0.md`.

A procedure role such as `venous_access_target` must not be used as a substitute anatomical identity.

### For both

Before A10 promotion, required downstream representations must exist as appropriate:

- segmentation/lumen representation;
- semantic identity;
- centerline where needed for interaction/runtime;
- robust boundary/lumen representation;
- provenance;
- human review appropriate to the claim.

Patient Space or medical-validation claims remain prohibited until their own requirements are actually met.

## 7. Roadmap to MVP 0 completion

### Stage 0 — Full-body source foundation

Current priority.

Goal: create a reusable whole-body immutable source foundation while keeping MVP 0 Medical Master authoring regional.

Primary output: trustworthy source archive/index plus same-subject continuity evidence needed for the left distal forearm.

### Stage 1 — Complete M6 and M7 on fixture anatomy

Continue TASK-073 through TASK-094.

Goal:

- boundary-crossing and lumen interaction events;
- penetration-path tracking;
- controlled patient-state transitions;
- simulation clock;
- event bus/log;
- minimal Venous Access Sandbox;
- arterial safety rule;
- session result;
- deterministic replay and replay UI.

Gate H remains the fixture end-to-end proof.

### Stage 2 — Complete M8A Medical Master

Resolve the missing vessels, then complete TASK-A10 through TASK-A18:

- Medical Master v0;
- technical geometry validation;
- anatomical review;
- AVF-region-specific review;
- render surfaces;
- collision assets;
- LODs;
- runtime manifest;
- browser-loadable regional package.

Gate I: medically grounded runtime forearm asset exists.

### Stage 3 — Replace the fixture and complete MVP 0

Complete TASK-095 through TASK-112.

The required end-to-end demonstration remains:

- medically grounded left distal forearm/wrist;
- 3D structure inspection and provenance;
- CT/reference-image synchronization;
- generic needle manipulation on desktop and iPad;
- tissue/boundary/lumen traversal;
- target venous-entry success;
- arterial puncture safety violation;
- event timeline;
- deterministic replay;
- real-iPad acceptance.

Gate J: formal MVP 0 completion.

## 8. Post-MVP roadmap toward the final system

The following stages describe intended direction. They do not authorize implementation before explicit tasks/specification updates.

### Stage 4 — Whole-body anatomical scaffold

Extend from one validated regional Medical Master toward a coherent whole-body canonical/patient anatomy framework.

Priorities:

- regional Medical Masters rather than one uncontrolled full-body segmentation pass;
- skeleton and major joints;
- major muscles/tendons;
- arterial and venous trees with explicit topology;
- major peripheral nerves;
- thoracic, abdominal, pelvic, cranial, and other organ systems;
- continuity across regional asset boundaries;
- multi-resolution whole-body navigation;
- region-specific validation.

The whole-body source archive created earlier becomes reusable evidence for this stage.

### Stage 5 — Dynamic musculoskeletal and respiratory anatomy

Add controlled deformation and kinematics without rewriting canonical anatomy.

Examples:

- joint motion;
- muscle/tendon state and movement;
- posture-dependent anatomy;
- respiratory chest-wall and diaphragmatic motion;
- lung and organ displacement.

Dynamic anatomy remains a time-varying state/deformation of referenced anatomy.

### Stage 6 — Cardiac motion and progressively refinable physiology

Build the normal-physiology layer using replaceable fidelity.

Progression:

```text
static physiology
  -> 0D lumped circulation
  -> 1D vascular hemodynamics
  -> local 3D CFD / FSI where clinically justified
```

Target capabilities include:

- heart rate/cardiac phase;
- chamber pressure and volume;
- valve opening/closure;
- regurgitant flow where modeled;
- systemic arterial pressure;
- regional arterial pulsation;
- vascular compliance;
- venous pressure;
- central venous pressure;
- respiratory-pressure effects on circulation;
- regional flow and velocity.

High-fidelity local flow should be used only where it adds procedural or educational value; it should not force the entire body into the same solver fidelity.

### Stage 7 — Imaging as observations of the same dynamic patient

Expand the imaging layer while preserving Patient Truth -> Observation -> Presentation.

Targets include:

- CT and MRI integration;
- interactive ultrasound;
- Doppler based on the same vascular/physiological state;
- later X-ray/fluoroscopy and endoscopic views where useful;
- needle/instrument appearance derived from their actual patient-space state;
- validation of reduced-fidelity iPad rendering against higher-fidelity references where appropriate.

### Stage 8 — Procedure expansion

Build procedures on the shared anatomy/physiology/interaction platform rather than standalone simulators.

Likely progression includes:

- AVF-region training and later AVF creation;
- central venous catheter and dialysis catheter workflows;
- arterial line and PICC;
- lumbar puncture;
- thoracentesis/chest tube;
- pericardiocentesis;
- tracheostomy;
- paracentesis;
- joint aspiration;
- biopsy/bone marrow/regional anesthesia;
- later endovascular and surgical workflows.

Generic instruments, anatomy, events, and physics should remain reusable across procedures.

### Stage 9 — Variation, pathology, and advanced patient simulation

After a reliable normal-human platform exists:

- anatomical variants;
- age/body-habitus diversity where data permits;
- pathology layered onto baseline anatomy;
- disease-specific physiology;
- case generation under validated constraints;
- longitudinal/session-specific patient state.

Synthetic variation must remain constrained, versioned, seeded where applicable, and distinguishable from acquired/cadaver-derived evidence.

### Stage 10 — Integrated Procedural Human

The intended final platform is a coherent digital human in which a learner can:

- inspect anatomy from whole body to procedure-level detail;
- move the body and observe dynamic anatomical relationships;
- inspect synchronized medical imaging;
- observe cardiovascular and respiratory physiology;
- use ultrasound/Doppler on the same patient;
- manipulate generic medical instruments;
- perform multiple procedures;
- cause physically/physiologically meaningful state changes;
- have those changes interpreted clinically through structured procedure logic;
- review events, complications, outcomes, and deterministic/reproducible sessions.

The key architectural success condition is unchanged:

> Adding a new body region, physiology model, imaging modality, or procedure should usually add validated representations/adapters/definitions—not require rebuilding the core digital-human architecture.

## 9. Guardrails

The following remain non-negotiable:

- no fabricated anatomy to satisfy a task checklist;
- no automatic promotion from segmentation to medical validation;
- no silent atlas-to-patient substitution;
- no false Patient Space claims;
- no medical truth inferred from render geometry or filenames;
- no large medical source binaries committed to Git;
- no loss of source/provenance/hash lineage;
- no expansion of MVP 0 acceptance merely because more source data has been acquired;
- no alteration of validated Medical Master geometry solely for runtime performance;
- no implementation of advanced physiology/physics before its specification boundary is intentionally opened.

## 10. Decision summary

The project now follows a two-scale strategy:

```text
WHOLE-BODY SOURCE FOUNDATION
  immutable, indexed, reusable, same-subject evidence
                    |
                    v
REGIONAL MEDICAL MASTERS
  validated only where needed
                    |
                    v
WHOLE-BODY COHERENT DIGITAL HUMAN
  assembled progressively with regional fidelity
                    |
                    v
DYNAMIC PHYSIOLOGY + IMAGING + PROCEDURES
```

For the current MVP, the whole-body source foundation exists to improve anatomical identity and future reuse. The deliverable remains the validated left distal forearm/wrist end-to-end simulation.
