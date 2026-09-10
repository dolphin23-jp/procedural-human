# Procedural Human

Procedural Human is a medically grounded, extensible digital-human platform for anatomy learning, medical imaging, and procedural simulation.

The long-term goal is to let a learner observe, image, manipulate, puncture, dissect, and operate on one coherent digital patient while preserving consistent anatomy, physiology, imaging, physics, instrument state, and procedure state.

## Design priorities

1. Medical correctness and traceability
2. Extensibility across body regions and procedures
3. Reproducibility
4. Separation of concerns
5. Desktop authoring with iPad as a first-class runtime target
6. Progressive fidelity: high precision only where medically needed

## MVP 0

MVP 0 is deliberately small. It targets the left distal forearm/wrist and proves the shared foundation:

- medically grounded anatomy with provenance
- shared patient coordinate system
- 3D anatomy on desktop and iPad Safari
- CT/reference image synchronization
- generic needle interaction
- vessel wall/lumen recognition
- structured simulation events
- minimal venous-access evaluation
- deterministic replay

MVP 0 is not yet a complete AVF or CVC simulator.

The current authoring strategy may ingest and index same-subject source data beyond the distal forearm, including the usable whole-body source dataset, when broader source context is needed to establish anatomical identity or continuity. This does **not** expand the MVP 0 runtime or acceptance region beyond the left distal forearm/wrist.

## Authoritative documents

The project specifications are, in order of authority:

1. MASTER_SPEC.md
2. ARCHITECTURE.md
3. DATA_POLICY.md
4. MVP0.md
5. DEVELOPMENT_RULES.md
6. TASKS.md

Implementation tasks must not silently violate higher-level specifications.

## Project direction

`ROADMAP.md` records the current implementation snapshot, the 2026-09-10 whole-body source-foundation decision, the immediate authoring plan, and the staged path from MVP 0 toward the long-term whole-body anatomy/physiology/procedure platform.

`ROADMAP.md` is directional and does not override the authoritative documents above.

## Planned runtime / authoring split

Runtime:
- TypeScript
- browser-first
- desktop browsers
- iPad Safari
- WebGPU where available, with compatible fallbacks

Authoring and preprocessing:
- Python
- 3D Slicer
- medical-image processing
- segmentation
- registration
- mesh and asset generation
- medical validation tooling

## Status

Snapshot: 2026-09-10, `main@71812a0a5779d358a748f9c41bc0a02a9bc99145`.

- M0-M5 are implemented through TASK-064.
- M6 is implemented through TASK-072; TASK-073 is the next numbered mainline interaction task.
- M7 Events/Procedure/Replay has not yet begun.
- M8A real-data authoring has progressed through A06 human review and A07 semantic mapping.
- A08/A09 have a bounded ulnar-artery centerline/lumen-boundary candidate.
- Radial-artery and superficial-target-vein evidence remain fail-closed, so A10 Medical Master v0 remains blocked.
- The next authoring strategy is to establish a reusable whole-body same-subject source foundation and trace missing vascular identity by continuity before resuming A10 promotion.
