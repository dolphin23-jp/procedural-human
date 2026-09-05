# Procedural Human — Architecture Specification

## 1. Purpose and authority

This document defines software module responsibilities, dependency direction, ownership, runtime composition, and adapter boundaries.

MASTER_SPEC.md has higher authority.

Core medical concepts must remain independent of React, Three.js, Cornerstone, WebGPU APIs, SOFA, specific CFD solvers, 3D Slicer, and browser input APIs.

## 2. Repository layout

Primary structure:

~~~text
procedural-human/
  apps/web/
  packages/
    core/
    units/
    math/
    anatomy/
    patient/
    spatial/
    physiology/
    physics-api/
    physics-lite/
    instruments/
    interaction/
    imaging-core/
    imaging-cornerstone/
    rendering-core/
    rendering-three/
    procedures/
    event-log/
    session/
    asset-runtime/
    ui/
  schemas/
    anatomy/
    patient/
    assets/
    events/
    procedures/
    cases/
    sessions/
  authoring/
    python/
      ph_dicom/
      ph_segmentation/
      ph_geometry/
      ph_validation/
      ph_assets/
      ph_cli/
    slicer/
  procedures/
  cases/
  asset-manifests/
  fixtures/
  tests/
  tools/
~~~

## 3. Dependency direction

Dependencies flow downward.

UI depends on Session.

Session composes Procedures, Imaging, Interaction, Event Log, Patient, Spatial, Physiology, Physics, Instruments, and Asset Runtime.

Interaction depends on Instruments, Spatial, Physics API, Physiology, and controlled Patient state services.

Spatial depends on Patient/Anatomy and technology-neutral math/core contracts.

Anatomy depends only on low-level core, units, and math contracts.

Forbidden examples include:
- anatomy → procedures
- anatomy → rendering-three
- anatomy → React
- patient → procedures
- spatial → interaction
- instruments → procedures
- physics-api → Three.js
- imaging-core → Cornerstone
- procedures → React

These restrictions should be mechanically enforced in CI.

## 4. packages/core

Owns technology-independent identifiers and primitives such as EntityId, StructureId, PatientId, AssetId, ProcedureId, SessionId, Version, ContentHash, Timestamp, SimulationTime, Result, and DomainError.

It contains no anatomical, rendering, procedure, or browser logic.

## 5. packages/units

Owns explicit physical quantities such as Length, Area, Volume, Time, Angle, Pressure, Velocity, FlowRate, Force, and Torque.

Patient-space length is canonically millimetres.

High-performance internals may use normalized arrays, but domain boundaries preserve units.

## 6. packages/math

Owns technology-neutral Vec2, Vec3, Quaternion, Mat4, Transform, Plane, Ray, Segment, and BoundingBox.

Three.js vector classes do not leak into this package.

Adapters convert project math types to renderer-specific types at boundaries.

## 7. packages/anatomy

Owns canonical anatomical meaning.

Primary concepts:
- AnatomicalEntity
- AnatomicalGraph
- AnatomicalRelationship
- BoundaryEntity
- TissueDefinition
- RepresentationDescriptor
- RepresentationBundle
- Provenance
- ValidationStatus
- AccuracyProfile

It defines what a radial artery is, not exactly where one patient's radial artery is.

It must not depend on procedures, instruments, imaging, renderer, UI, or concrete physics backends.

## 8. packages/patient

Owns one patient's instantiated anatomy and baseline/runtime medical state.

Primary concepts:
- PatientInstance
- PatientAnatomy
- PatientMorphology
- PatientStructureInstance
- BaselinePhysiology
- PathologyState
- VariationProfile
- RuntimeMedicalState
- PatientStateTransitionService

Clinically meaningful state mutation is controlled through the state-transition service.

## 9. packages/spatial

One of the central packages.

Owns:
- PatientCoordinateSystem
- SpatialIndex
- SpatialQueryService
- PointQuery
- SegmentQuery
- RayQuery
- BoundaryQuery
- DistanceQuery
- TransformGraph
- DeformationField

Consumers ask shared spatial services instead of reading render meshes.

Spatial query results may include tissue, structures, boundaries, lumen membership, nearby structures, accuracy, and future mechanical/acoustic/physiological values.

## 10. Spatial representations

One anatomical identity may map to multiple representations:
- renderSurface
- collisionSurface
- segmentationVolume
- lumenVolume
- centerline
- signedDistanceField
- physicsVolume

No representation is the anatomical entity itself.

## 11. Patient space and render space

Medical truth is defined in patient space.

Rendering may use a local coordinate system, but transforms are explicit and reversible.

Medical events are stored in patient-space coordinates.

## 12. packages/physiology

Defines future-compatible physiological interfaces.

MVP 0 may use static/default values.

Future implementations may expose pressureAt, velocityAt, flowFor, cardiac phase, respiratory phase, and compliance without changing consumers.

## 13. packages/physics-api

Defines contracts only, such as CollisionService, SoftTissueSolver, BoundaryMechanics, FlexibleInstrumentSolver, ConstraintSolver, and FluidInteractionModel.

Third-party solver types are never exposed through public domain models.

## 14. packages/physics-lite

Implements lightweight browser/iPad runtime physics.

MVP 0 may be limited to logical collision, static geometry, and boundary traversal.

It does not require FEM, bleeding, tissue tearing, or fluid dynamics.

## 15. packages/instruments

Owns generic medical instrument definitions and runtime state.

Primary concepts:
- InstrumentDefinition
- InstrumentInstance
- InstrumentPart
- InstrumentCapability
- InstrumentPose
- NeedleDefinition
- NeedleInstance

Procedure-specific generic subclasses are prohibited unless the physical instrument is genuinely different.

## 16. Input and instrument control

Browser events are normalized:

Input Device → Input Adapter → Instrument Control Intent → Instrument Controller → Instrument Instance.

Needle implementations do not call browser pointer APIs directly.

## 17. packages/interaction

Combines Instrument State + Spatial Query + Physics + Physiology.

Responsibilities include contact, traversal, boundary crossing, lumen entry/exit, interaction requests, controlled medical-state transition, and event production.

It does not determine clinical correctness.

## 18. State transition ownership

Instruments and UI must not directly set fields such as vein.punctured.

Flow is:

Interaction Engine → StateTransitionRequest → PatientStateTransitionService → RuntimeMedicalState → SimulationEvent.

## 19. packages/event-log and Event Bus

SimulationEvent is versioned and includes event identity/type, simulation time, patient-space location when relevant, actor, target, and payload.

Producers emit to one Event Bus without knowing consumers.

Procedure evaluation, event persistence, and UI feedback subscribe independently.

## 20. Replay

Replay reconstructs a session from case definition, initial state, compatible versions, input stream or deterministic driving data, and random seed.

MVP 0 requires reproduction of clinically relevant event sequence, not pixel-identical rendering.

## 21. packages/imaging-core

Owns modality-independent concepts:
- ImagingDevice
- ImagingObservation
- ImagingSourceType: acquired, synthetic, hybrid
- AcquisitionParameters
- ImagingFrame
- ImagingFidelity

Imaging observes Patient Space and never mutates anatomical truth.

## 22. packages/imaging-cornerstone

Cornerstone adapter responsibilities may include DICOM/reference volume loading, viewport management, MPR, oblique slicing, and crosshair synchronization.

Cornerstone-specific types remain inside the adapter.

## 23. Imaging coordinate bridge

A dedicated bridge handles:

image pixel/voxel ↔ patient-space coordinate ↔ 3D render coordinate.

Round-trip transforms must be tested.

Unknown registration must never silently become identity registration.

## 24. packages/rendering-core

Owns rendering-neutral presentation concepts such as visibility, opacity, selection, clipping plane, and camera intent.

No Three.js classes.

## 25. packages/rendering-three

Owns Three.js/WebGPU implementation, including GLB integration, scene construction, camera, render meshes, clipping planes, picking, visibility, opacity, and patient/render transforms.

Picking must resolve to PatientStructureInstance or AnatomicalEntity identity.

## 26. packages/asset-runtime

Loads validated runtime packages.

Responsibilities:
- read manifests
- validate versions/schemas
- verify hashes where configured
- load region chunks and LOD
- resolve representations
- cache assets

Consumers request capabilities or representations, not hard-coded filenames.

## 27. packages/procedures

Owns clinical evaluation, not physical simulation.

Primary concepts:
- ProcedureDefinition
- ProcedureSession
- Goal
- Subgoal
- Dependency
- SafetyRule
- ComplicationRule
- AssessmentRule
- GuidancePolicy

Procedure Engine is generic code. Procedure Definition is data.

Simple new procedures should usually add data, not modify engine code.

## 28. Case binding

Procedures may use semantic roles rather than hard-coded structure IDs.

Example:
venous_access_target → structure.cephalic_vein.left

This permits the same procedure logic to bind to different anatomy.

## 29. packages/session

Session is the runtime composition root.

SimulationSession owns lifecycle and connects Patient, Spatial, SimulationClock, Physiology, Physics, Instruments, Interaction, Imaging, Procedure, Event Log, and Asset Runtime.

UI interacts primarily with Session-facing APIs or read-only state.

Global mutable simulation state is prohibited.

## 30. packages/ui and apps/web

React owns presentation, not medical truth.

UI does not directly mutate Patient medical state.

Commands flow through Session/domain services.

## 31. Authoring architecture

Runtime and authoring are separated.

Source Data → 3D Slicer / Python → Medical Master → Validation → Derived Representations → Runtime Package.

Runtime never requires authoring tools.

Python package roles:
- ph_dicom: ingest, metadata, spatial integrity, de-identification support
- ph_segmentation: segmentation I/O, draft automation, semantic mapping
- ph_geometry: surfaces, LOD, collision geometry, centerlines, representation mapping
- ph_validation: geometry/topology/registration/procedure-specific checks
- ph_assets: manifests, hashes, packaging, compression
- ph_cli: stable command-line entry points

3D Slicer is treated as an external authoring environment and exchanges explicit files/metadata with the Python workspace.

## 32. Schema ownership

Persistent contracts are defined under schemas/.

TypeScript and Python validate/generate corresponding models from the same contracts.

Runtime implementations must not silently redefine persistent formats.

## 33. Versioning

Saved Session Records identify application, engine, schema, event schema, canonical anatomy, asset versions/hashes, procedure, case, physics model, and imaging model where relevant.

## 34. Large asset policy

Large binaries remain external to the main source repository.

Git stores manifests, hashes, metadata, validation reports, schemas, and small fixtures.

## 35. Fixture architecture

Development fixtures are simple and explicitly non-medical.

They test engine behavior and must never be exposed as validated educational anatomy.

## 36. MVP 0 composition

MVP 0 composes:
- static PatientInstance
- AnatomicalGraph
- SpatialQueryService
- physics-lite
- generic NeedleInstance
- InteractionEngine
- EventBus
- EventLog
- Venous Access Sandbox Procedure
- rendering-three
- imaging-cornerstone
- React UI
- SimulationSession

## 37. Core MVP interaction flow

Pointer/Pencil intent → Input Adapter → Needle Controller → candidate pose → Interaction Engine → Spatial query → boundary/lumen transition → controlled State Transition → structured Event → Event Bus → Event Log + Procedure Evaluator.

No layer bypasses the chain for convenience.

## 38. Core MVP imaging flow

DICOM/reference volume → imaging-cornerstone → patient-space imaging plane → coordinate bridge → rendering-three 3D plane.

Moving either image slice or 3D plane updates the shared patient-space plane and then the other view.

## 39. External library isolation

Third-party ownership:
- Three.js → rendering-three
- Cornerstone → imaging-cornerstone
- React → ui/apps/web
- future SOFA bridge → physics-sofa
- Python DICOM libraries → ph_dicom

## 40. Error handling

Medically significant uncertainty must fail explicitly.

Examples:
- AssetNotFound
- RepresentationUnavailable
- CoordinateTransformUnavailable
- InvalidManifest
- UnsupportedSchemaVersion
- SpatialQueryFailure

Do not catch and silently continue when medical spatial integrity is uncertain.

## 41. Performance architecture

Prefer:
1. spatial indexing
2. streaming
3. LOD
4. caching
5. derived representation simplification
6. reduced simulation fidelity
7. GPU compute
8. backend specialization

Validated Medical Master geometry is not modified as a runtime shortcut.

## 42. Architectural testing

CI should test dependency rules, schema compatibility, coordinate round trips, spatial queries, event flow, replay, renderer isolation, and required medical asset validation.

## 43. Architectural change rule

If a task appears to require breaking these boundaries, document the conflict and propose the smallest explicit change. Do not perform out-of-scope architectural refactoring silently.
