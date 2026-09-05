# Procedural Human — MVP 0 Implementation Tasks

## 1. Purpose

This file defines the ordered MVP 0 implementation plan.

Each task is bounded so Astra or a human developer can implement one concern without redesigning adjacent systems.

Authority order:
1. MASTER_SPEC.md
2. ARCHITECTURE.md
3. DATA_POLICY.md
4. MVP0.md
5. DEVELOPMENT_RULES.md
6. this file

## 2. Execution rule

Before each task:
1. read governing documents
2. inspect current code/tests
3. implement only the assigned task
4. do not implement later tasks
5. preserve passing tests
6. add appropriate tests
7. report any architecture conflict

Suggested commit: TASK-XXX: short description.

## 3. Milestones

M0 Repository Foundation  
M1 Contracts and Schemas  
M2 Anatomy and Patient Domain  
M3 Spatial Query Core  
M4 3D Runtime  
M5 Medical Imaging Bridge  
M6 Instrument and Interaction  
M7 Events, Procedure, Replay  
M8 Medical Asset Pipeline and MVP 0 Integration

The medical-asset lane may run in parallel once relevant schemas exist.

# M0 — Repository Foundation

## TASK-001 — Create repository skeleton
Create apps/web, packages, schemas, authoring/python, authoring/slicer, procedures, cases, asset-manifests, fixtures, tests, and tools according to ARCHITECTURE.md.
Out of scope: medical logic, rendering, imaging, physics.

## TASK-002 — Configure pnpm workspace
Create package.json, pnpm-workspace.yaml, lockfile, and @procedural-human/* naming convention.
Done: pnpm install succeeds.

## TASK-003 — Configure Python uv workspace
Create pyproject.toml, uv.lock, and initial authoring Python package structure.
Done: uv sync succeeds.
Out of scope: Slicer integration.

## TASK-004 — Configure strict TypeScript
Shared strict tsconfig before domain code is added.

## TASK-005 — Configure formatting and linting
Provide root lint, format/check, and typecheck commands without unnecessary framework complexity.

## TASK-006 — Create minimal web application
Vite/React shell boots with no simulation logic in UI.
Acceptance: desktop browser and real iPad Safari.

## TASK-007 — Establish CI baseline
CI runs install, lint, typecheck, tests, and build.

## TASK-008 — Enforce package dependency boundaries
Mechanically reject forbidden imports defined in ARCHITECTURE.md.
Acceptance: a deliberate fixture violation fails, then is removed.

# M1 — Contracts and Schemas

## TASK-009 — Core identifier types
Create EntityId, StructureId, PatientId, AssetId, ProcedureId, CaseId, SessionId.

## TASK-010 — Version and ContentHash types
Create Version, SchemaVersion, and ContentHash contracts.

## TASK-011 — Units foundation
Create Length, Time, Angle, Pressure, Velocity, FlowRate, Volume, and Force with conversion tests.

## TASK-012 — Technology-neutral math types
Create Vec3, Quaternion, Mat4, Transform, Plane, Ray, Segment, BoundingBox.

## TASK-013 — Explicit coordinate-space types
Create PatientSpacePoint/Vector, RenderSpacePoint, ImageVoxelCoordinate.

## TASK-014 — JSON Schema toolchain
Add schema validation command, fixtures, and versioning convention.

## TASK-015 — Anatomical Entity schema v1
Fields: id, name, type, laterality, region, relationships, representations, provenance, accuracy, validation.

## TASK-016 — Asset Manifest schema v1
Fields: assetId, version, contentHash, region, source, accuracy, validation, representations, dependencies, license.

## TASK-017 — Patient Manifest schema v1
Distinguish canonical anatomy reference, patient-specific structures, baseline state, and imaging references.

## TASK-018 — Simulation Event schema v1
Fields: id, type, simulationTime, actor, target, patientPosition, payload, schemaVersion.

## TASK-019 — Procedure Definition schema v1
Initial goals, dependencies, semantic bindings, safety rules, completion criteria.

## TASK-020 — Case Manifest schema v1
Support semantic role binding, e.g. venous_access_target → target structure.

## TASK-021 — Session Record schema v1
Include session ID, case/engine versions, asset versions/hashes, procedure version, schema versions, random seed.

## TASK-022 — TypeScript/Python shared validation
One fixture validates under both ecosystems.

Gate B: schemas are authoritative and cross-language compatible.

# M2 — Anatomy and Patient Domain

## TASK-023 — AnatomicalEntity domain model
Implement canonical identity in packages/anatomy without renderer or patient runtime state.

## TASK-024 — AnatomicalGraph
Initial relations: part_of, branch_of, adjacent_to, connected_to.

## TASK-025 — Provenance model
Support source class/dataset, derivation method, validation, and unknown values.

## TASK-026 — Accuracy profile
Initial dimensions: identity, topology, geometry, registration, relationship.

## TASK-027 — Representation Bundle
Describe renderSurface, collisionSurface, segmentationVolume, lumenVolume, centerline.

## TASK-028 — BoundaryEntity
Represent medically significant boundaries and the regions they separate.

## TASK-029 — PatientInstance
Static morphology is sufficient for MVP 0.

## TASK-030 — PatientStructureInstance
Link patient-specific geometry/state to canonical identity.

## TASK-031 — RuntimeMedicalState
Initial state can be intact/punctured. Out of scope: incision, clamp, bleeding.

## TASK-032 — PatientStateTransitionService
Only controlled public mutation path for clinically meaningful state.

## TASK-033 — Static physiology interface
Create future-compatible contracts; static/unavailable values are sufficient.

## TASK-034 — Synthetic anatomy fixture v1
Non-medical fixture: skin slab, soft tissue, vein cylinder, artery cylinder. Explicit development-fixture provenance.

Gate C: anatomy/patient models work without a renderer.

# M3 — Spatial Query Core

## TASK-035 — Spatial representation adapter interface
Define containsPoint, intersectSegment, distanceToPoint capability without renderer dependency.

## TASK-036 — Basic spatial index
Simple bounding-volume candidate narrowing; no premature optimization.

## TASK-037 — Point query
Determine tissue, named structures, and lumen membership for fixture points.

## TASK-038 — Segment query
Return relevant intersections along a patient-space segment.

## TASK-039 — Boundary crossing detection
Return boundary ID, entry/exit, intersection position, and distance along segment.

## TASK-040 — Lumen membership
Distinguish vein and artery lumen.

## TASK-041 — Distance query
Distance to relevant structure/representation.

## TASK-042 — Ordered penetration path
Produce stable ordered traversal, e.g. skin → soft tissue → vein wall → lumen → wall → soft tissue.

## TASK-043 — Small public Spatial Query API
Expose queryPoint, querySegment, distanceTo without leaking internals.

## TASK-044 — Spatial performance baseline
Measure query throughput, fixture complexity, and memory before optimization.

Gate D: deterministic fixture spatial queries.

# M4 — 3D Runtime

## TASK-045 — Rendering-core contracts
Visibility, opacity, selection, clipping plane, camera intent. No Three.js types.

## TASK-046 — Three.js renderer adapter
Render fixture anatomy with library-specific code isolated.

## TASK-047 — Domain/renderer coordinate adapter
Explicit PatientSpace ↔ RenderSpace ↔ Three conversion with tests.

## TASK-048 — GLB runtime loader
Load derived render representations and resolve semantic identities.

## TASK-049 — Structure visibility
Hide/show semantic structures.

## TASK-050 — Structure opacity
Support transparency.

## TASK-051 — Picking and semantic resolution
Tap/click geometry and resolve PatientStructureInstance/AnatomicalEntity, not only mesh name.

## TASK-052 — Camera input abstraction
Mouse/touch navigation.

## TASK-053 — Real iPad navigation checkpoint
Manual real-device check: rotate, zoom, pan, select.

Gate E: early real-iPad usability.

## TASK-054 — Structure metadata panel
Show name, source class, accuracy, validation.

## TASK-055 — Clipping plane rendering
Display arbitrary patient-space plane through 3D anatomy.

# M5 — Medical Imaging Bridge

## TASK-056 — Imaging-core contracts
ImagingObservation, ImagingSourceType, ImagingFrame, PatientImagingPlane.

## TASK-057 — Imaging coordinate bridge
Transforms among image voxel, patient coordinate, render coordinate; test with synthetic volume.

## TASK-058 — Cornerstone adapter bootstrap
Load one small trusted image fixture.

## TASK-059 — Axial volume viewer
Slice position has patient-space meaning.

## TASK-060 — Image-to-3D synchronization
Scrolling image moves the 3D plane.

## TASK-061 — 3D-to-image synchronization
Moving the 3D plane updates the image viewport.

## TASK-062 — Coordinate round-trip suite
voxel → patient → render → patient → voxel within explicit numerical tolerance.

## TASK-063 — Arbitrary oblique plane
Support oblique image section matching a patient-space plane. If blocked, document exact reason before scope revision.

## TASK-064 — Side-by-side 3D + image UI
Basic layout; polish not required.

Gate F: image/3D coordinate integrity.

# M6 — Instrument and Interaction

## TASK-065 — Instrument base domain
InstrumentDefinition, InstrumentInstance, InstrumentPart, InstrumentPose.

## TASK-066 — NeedleDefinition
Generic tip, bevel, shaft, lumen. No CVC/AVF semantics.

## TASK-067 — NeedleInstance
Pose, tip position/direction, trajectory.

## TASK-068 — Input intent model
Normalized translation, rotation, advance/retract intent.

## TASK-069 — Mouse needle controller
Desktop manipulation only; no clinical logic.

## TASK-070 — Touch/Pencil needle controller
Usable iPad manipulation; pressure sensitivity not required.

## TASK-071 — Interaction Engine skeleton
Connect needle movement and Spatial Query without Procedure knowledge.

## TASK-072 — Contact detection
Emit contact when needle first interacts with a structure.

## TASK-073 — Boundary crossing interaction
Convert spatial crossing into semantic interaction event candidate with patient-space location.

## TASK-074 — Lumen entered/exited
Distinguish transitions for vein and artery fixture.

## TASK-075 — Penetration path tracking
Maintain ordered tissue/structure traversal.

## TASK-076 — Patient state transition integration
Medical state updates only through PatientStateTransitionService.

## TASK-077 — Interactive fixture needle demo
PC and iPad: move needle → enter fixture vein → recognize lumen entry. No scoring yet.

Gate G: generic needle traverses fixture anatomy.

# M7 — Event, Procedure, Replay

## TASK-078 — SimulationClock
One authoritative simulation time source.

## TASK-079 — Event Bus
Publish structured events without producer/consumer coupling.

## TASK-080 — Event Log
Persist ordered event sequence.

## TASK-081 — Interaction event serialization
Versioned Contact, BoundaryCrossed, LumenEntered, LumenExited events.

## TASK-082 — SimulationSession skeleton
Own create, initialize, start, pause, finish, dispose and compose MVP systems.

## TASK-083 — Procedure Evaluator core
Consume events and evaluate declarative rules; never move instruments.

## TASK-084 — Venous Access Sandbox definition
Goal: target venous lumen entered. Target supplied by case.

## TASK-085 — Fixture case
Bind venous_access_target to fixture vein.

## TASK-086 — ProcedureGoalSatisfied event
Emit when target lumen entry satisfies the goal.

## TASK-087 — Arterial puncture safety rule
Physical action remains allowed; procedure records a safety violation.

## TASK-088 — Session result summary
At minimum: goal achieved, arterial puncture, event count, needle trajectory.

## TASK-089 — Input recording
Record sufficient control data for replay.

## TASK-090 — Session-scoped seeded random source
Establish deterministic randomness infrastructure.

## TASK-091 — Deterministic replay engine
Re-run input against initial state and reproduce clinically relevant events.

## TASK-092 — Replay comparison test
Original clinically relevant events equal replayed sequence.

## TASK-093 — Event timeline UI
Display chronological events after session.

## TASK-094 — Replay UI controls
Play, pause, restart.

Gate H: full fixture end-to-end flow.

# M8A — Medical Asset Authoring Lane

May begin after relevant schemas exist.

## TASK-A01 — Select MVP 0 source dataset
Document dataset, license, modalities, resolution, and known limitations for distal left forearm/wrist.

## TASK-A02 — Source archive record
Record source identifiers, retrieval date, hashes, license metadata.

## TASK-A03 — DICOM/source ingest tooling
ph_dicom preserves spatial metadata.

## TASK-A04 — Define reproducible ROI
Record patient-space extent for distal forearm/wrist.

## TASK-A05 — Draft segmentation
Create required structures; automated output remains draft.

## TASK-A06 — Manual anatomical correction
Record manual-edit provenance.

## TASK-A07 — Semantic structure mapping
Assign project anatomical IDs.

## TASK-A08 — Vessel centerlines
Create key vessel centerlines where source quality supports it.

## TASK-A09 — Boundary/lumen representation
Represent outside vessel, wall crossing, and lumen robustly enough for MVP interaction.

## TASK-A10 — Medical Master v0
Authoritative forearm package with source references, segmentation, semantic identity, and validation metadata.

## TASK-A11 — Technical geometry validation
Coordinate integrity, mesh integrity, required structures, representation links. Not medical validation.

## TASK-A12 — Anatomical review
Review principal vessels, bones, target region, and key spatial relationships.

## TASK-A13 — Procedure-specific AVF-region review
Even though full AVF is out of scope, review target superficial vein, radial artery, depth relationship, and nearby nerve if represented.

## TASK-A14 — Generate render surfaces
Derived from Medical Master with lineage.

## TASK-A15 — Generate collision assets
Suitable for MVP needle query.

## TASK-A16 — Generate LODs
Preserve clinically relevant vessel geometry within tolerance.

## TASK-A17 — Runtime Asset Manifest
Versioned manifest linking representations.

## TASK-A18 — Package runtime anatomy
Browser-loadable regional asset only.

Gate I: medically grounded runtime forearm asset exists.

# M8B — Replace Fixture With Medical Anatomy

## TASK-095 — Medical asset runtime loading
Load validated forearm through asset-runtime with no dataset-specific engine hack.

## TASK-096 — Medical structure picking
Resolve real structures such as left radial artery and target superficial vein to semantic IDs.

## TASK-097 — Medical provenance UI
Show source/validation metadata.

## TASK-098 — Register reference imaging
Explicitly connect source/reference volume to the same Patient Space.

## TASK-099 — Medical image/3D synchronization test
Known landmarks align within defined tolerance.

## TASK-100 — Medical spatial-query validation
Known trajectories correctly identify soft tissue, target vein wall/lumen, and arterial boundary/lumen.

## TASK-101 — Bind Venous Access procedure to medical target
Replace fixture semantic binding without Procedure Engine rewrite.

## TASK-102 — Medical venous-entry demo
Needle enters validated target vein and satisfies goal.

## TASK-103 — Medical arterial-puncture demo
Needle enters/crosses artery and produces safety violation.

## TASK-104 — Fixture-replacement architecture test
If replacing the fixture requires core Interaction or Procedure redesign, treat it as architecture failure before proceeding.

# M8C — MVP 0 Acceptance

## TASK-105 — Desktop acceptance suite
Launch, anatomy, picking, opacity, imaging, sync, needle, venous success, arterial violation, replay.

## TASK-106 — Automated WebKit acceptance
Useful but not a substitute for real iPad.

## TASK-107 — Real iPad Safari acceptance
Manual: launch, rotate, zoom, pan, select, opacity, image scroll, plane move, needle, procedure result, event timeline, replay. Record device/browser version.

## TASK-108 — MVP performance baseline
Measure median fps, frame spikes, initial asset load, and memory where observable. Target ~30 fps or better median. Do not alter Medical Master geometry.

## TASK-109 — Deterministic medical replay acceptance
Saved medical session reproduces clinically relevant event sequence.

## TASK-110 — MVP medical validation review
Ensure user-visible claims do not exceed asset validation.

## TASK-111 — MVP 0 release candidate
Mandatory tests and real-device checks pass; no unresolved medical-data integrity errors.

## TASK-112 — MVP 0 completion record
Record app/engine/schema versions, medical asset version/hash, procedure/case version, device/browser acceptance info, and known limitations.

Gate J: formal MVP 0 completion.

# 4. Explicit post-MVP areas — not authorized yet

Do not implement before explicit tasks:
- ultrasound engine
- probe compression
- needle visualization on ultrasound
- Doppler
- scalpel/cutting
- forceps/grasping
- vascular clamp
- guidewire
- flexible catheter mechanics
- dilator/CVC workflow
- 0D circulation
- 1D vascular flow
- arterial pulsation
- venous pressure
- respiration
- AVF anastomosis
- chest tube
- lumbar puncture
- pericardiocentesis
- tracheostomy
- FEM
- XPBD
- CFD/FSI
- bleeding
- haptics

# 5. Recommended Astra batches

Initial low-risk setup may be grouped:
- Batch 1: TASK-001 to TASK-003
- Batch 2: TASK-004 to TASK-008
- Batch 3: TASK-009 to TASK-013
- Batch 4: TASK-014 to TASK-018

After domain implementation starts, prefer smaller batches.

Spatial Query, imaging registration, Interaction, and Replay should generally be one task at a time.

# 6. Critical gates

Gate A after TASK-008: repository builds/tests and dependency rules work.  
Gate B after TASK-022: schema contracts are authoritative across TS/Python.  
Gate C after TASK-034: anatomy/patient domain works without renderer.  
Gate D after TASK-044: deterministic spatial queries.  
Gate E after TASK-053: real iPad rendering/input works early.  
Gate F after TASK-064: image/3D coordinate integrity.  
Gate G after TASK-077: generic needle traverses fixture anatomy.  
Gate H after TASK-094: fixture end-to-end procedure/replay.  
Gate I after TASK-A18: medically grounded runtime asset.  
Gate J after TASK-112: MVP 0 complete.

# 7. Critical path

Repository
→ Schemas
→ Anatomy/Patient
→ Spatial Query
→ Rendering
→ Imaging
→ Needle Interaction
→ Events
→ Procedure
→ Replay
→ Validated Medical Asset
→ iPad Acceptance

The medical-asset lane should proceed in parallel once contracts permit.

# 8. Success definition

MVP 0 succeeds when validated anatomy + medical imaging + shared patient coordinates + generic instrument + spatial interaction + structured events + procedure evaluation + replay + iPad runtime all work together without architectural redesign.
