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

## Authoritative documents

The project specifications are, in order of authority:

1. MASTER_SPEC.md
2. ARCHITECTURE.md
3. DATA_POLICY.md
4. MVP0.md
5. DEVELOPMENT_RULES.md
6. TASKS.md

Implementation tasks must not silently violate higher-level specifications.

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

Architecture and MVP 0 planning are established. Implementation starts with the repository foundation and contracts defined in TASKS.md.
