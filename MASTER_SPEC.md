# Procedural Human — Master Specification

## 1. Project definition

Procedural Human is a medically grounded, extensible human anatomy and medical-procedure simulation platform.

It is not primarily a static anatomy atlas, an AV fistula simulator, a CT viewer, an ultrasound simulator, or a surgical game. Those are applications built on top of one shared digital-human platform.

The fundamental model is:

Patient → Anatomy → Physiology → Physics → Imaging → Instruments → Interaction → Events → Procedure evaluation.

All subsystems must describe the same patient in the same spatial and temporal world.

## 2. Long-term scope

The architecture must permit expansion to procedures such as AV fistula creation, central venous and dialysis catheter insertion, arterial lines, PICC placement, lumbar puncture, thoracentesis, chest tubes, pericardiocentesis, tracheostomy, paracentesis, joint aspiration, biopsy, bone marrow procedures, regional anesthesia, endovascular procedures, and future surgery.

Adding a procedure should normally add procedure definitions, instruments, validated assets, or specialized evaluators—not redesign the human model.

## 3. Platform requirement

Computationally expensive authoring may use a desktop PC. Interactive runtime must treat iPad as a first-class target.

The preferred runtime is browser-first, using WebGPU where appropriate and compatible reduced-fidelity fallbacks where required.

Heavy preprocessing may include DICOM processing, segmentation, registration, mesh generation, tetrahedralization, CFD, FEM, acoustic reference simulation, and validation. These processes are not required to execute on iPad.

Medical accuracy must not be sacrificed merely to meet device performance targets. Reduce loaded region size, render quality, LOD, simulation fidelity, or solver complexity before altering validated medical truth.

## 4. Medical accuracy

Medical accuracy is a top-level requirement.

The system must distinguish:
- anatomical truth
- simulation approximation
- rendering approximation

A model is not medically accurate merely because it looks realistic. AI-generated anatomy is not validated anatomical truth.

Anatomical geometry must carry provenance, uncertainty, accuracy, and validation metadata.

The system must support different fidelity levels in different regions simultaneously. Whole-body navigation may be low detail while a procedure-specific operative field is high fidelity.

## 5. Accuracy and fidelity are separate

The architecture must independently represent, where relevant:
- anatomical geometry accuracy
- anatomical topology accuracy
- imaging registration accuracy
- mechanical simulation fidelity
- hemodynamic fidelity
- ultrasound fidelity
- cardiac-motion fidelity

A high-resolution mesh does not imply high anatomical accuracy. Accurate anatomy does not imply high-fidelity mechanics.

## 6. Canonical Anatomy, Patient Instance, Runtime State

Canonical Anatomy defines what structures exist, their medical meaning, and their relationships.

Patient Instance defines one patient's morphology, anatomical variation, baseline physiology, pathology, and imaging.

Runtime State contains simulation-time changes such as puncture, incision, clamp state, or cannulation.

Runtime State must not rewrite canonical anatomy.

Patient instances may be image-derived, cadaver-derived, synthetic under validated constraints, atlas-derived, or hybrid.

## 7. Anatomical entity model

An anatomical structure is not equivalent to a mesh.

An AnatomicalEntity may contain:
- identity
- type
- laterality
- region
- relationships
- provenance
- validation
- accuracy

It may have multiple replaceable representations:
- render surface
- collision surface
- segmentation volume
- lumen representation
- centerline
- signed-distance field
- deformable physics volume
- physiology binding

The semantic identity survives representation replacement.

## 8. Continuous tissue and boundaries

Diffuse tissue such as subcutaneous fat or generic connective tissue may be represented as fields or volumes rather than many named objects.

Medically significant interfaces must be representable explicitly as BoundaryEntity objects, including vessel walls, pleura, dura, arachnoid, pericardium, clinically important fascia, and ligamentum flavum.

Boundary crossing must be observable as an event.

## 9. Spatial reference

All medical spatial data must map to one patient coordinate system.

Canonical spatial unit: millimetres.

Image-derived cases should preserve DICOM patient-space and Frame-of-Reference relationships where available.

Rendering engines may use local coordinates for numerical stability, but conversion to and from patient space must be explicit.

A location in CT, 3D anatomy, segmentation, ultrasound, instrument geometry, and physiological fields must be referable to the same patient-space point.

## 10. Spatial Query API

Systems that need anatomical knowledge must use one shared spatial-query interface. Instruments, imaging, and procedure logic must not independently infer anatomy from render meshes.

A spatial query may eventually return tissue, named structures, crossed boundaries, lumen membership, nearby structures, distances, mechanical properties, acoustic properties, pressure, flow, velocity, accuracy, and provenance.

MVP implementations may support only the required subset while preserving the architecture.

## 11. Time and dynamic anatomy

Simulation time is a first-class concept, represented by one common SimulationClock.

Dynamic anatomy should be represented as deformation of reference anatomy rather than destructive rewriting.

The architecture must support later addition of heartbeat, valve motion, arterial pulsation, venous pressure changes, respiration, vascular collapse, and organ motion.

## 12. Physiology architecture

Physiology must be replaceable and progressively refinable.

The architecture must permit:
0D lumped physiology → 1D vascular hemodynamics → local 3D CFD / FSI

without replacing anatomy, imaging, instruments, or procedure definitions.

Relevant future state may include pressure, flow, volume, compliance, vascular resistance, chamber pressure, regional venous pressure, central venous pressure, and respiratory pressure effects.

High-fidelity physiology is not required for MVP 0, but its interfaces are.

## 13. Physics architecture

Domain objects must not depend directly on a particular physics engine.

Possible backends may include simplified logical physics, WebGPU solvers, XPBD, FEM, Cosserat-rod models, SOFA, CFD solvers, and precomputed reduced-order models.

PC and iPad may use different physical representations of the same medical object while preserving semantic identity and validated anatomy.

## 14. Instrument architecture

Instruments are generic functional objects, not procedure-specific objects.

Do not create CVCNeedle or AVFScalpel when a generic Needle or Scalpel is sufficient.

Definitions and runtime instances are separate. Instruments may contain functional parts such as needle tip, bevel, shaft, lumen, and hub; scalpel cutting edge; or forceps jaws and grasp region.

## 15. Interaction architecture

Interaction is determined from Instrument State + Spatial Query + Physics + Physiology.

The Interaction Engine—not the Procedure Engine—determines physical events such as contact, boundary crossing, lumen entry/exit, cutting, grasping, clamping, or aspiration.

Instruments must not directly mutate medical patient state. Changes pass through controlled state-transition services.

## 16. Procedure architecture

A procedure does not physically control the patient or instruments.

A procedure observes events and evaluates them clinically through goals, subgoals, dependencies, acceptable alternatives, safety rules, complication rules, completion criteria, and assessment rules.

Procedures should not generally be rigid forced linear sequences.

Unsafe but physically possible actions should remain possible in advanced simulation and be evaluated as unsafe rather than made impossible.

## 17. Complications

Complications should arise from patient-state changes whenever practical.

For example, pleural puncture should be modeled through boundary violation and physiological consequence rather than an arbitrary bad_action flag.

Procedure logic interprets clinical meaning; it does not fabricate underlying physics.

## 18. Imaging architecture

The imaging model separates Patient Truth → Observation → Presentation.

Imaging must not modify anatomy to make an image appear correct.

Source types must be distinguishable:
- acquired
- synthetic
- hybrid

Original acquired images are immutable.

The architecture must support eventual CT, MRI, ultrasound, Doppler, X-ray, fluoroscopy, and endoscopic visualization.

## 19. Imaging registration

Image-derived cases must preserve patient-space registration.

MVP 0 must demonstrate:
image coordinate ↔ patient coordinate ↔ 3D anatomical coordinate

with synchronized 3D anatomy and CT/reference slicing.

## 20. Ultrasound architecture

Ultrasound is an observation of the same dynamic patient.

Probe and needle both exist in patient space.

Future ultrasound rendering may use tissue acoustic fields, scattering, attenuation, anisotropy, interfaces, physiological deformation, and blood velocity.

Interactive iPad rendering may use reduced models; higher-fidelity PC simulation may be used for validation.

## 21. Medical data pipeline

The medical data pipeline is:

Source Data → Authoring → Medical Master → Validation → Derived Runtime Representations.

Medical Master is authoritative.

Render meshes, LODs, collision meshes, and physics meshes are derived representations and must never silently replace the Medical Master.

## 22. Provenance

Every medically relevant asset must be traceable to its source, derivation method, manual corrections, algorithm versions, validation status, and uncertainty.

AI-inferred structures remain explicitly inferred until validated.

## 23. Validation

Validation is multi-dimensional and may include identity, topology, geometry, spatial relationships, imaging correspondence, and procedure-specific relevance.

Automated validation is not medical validation.

High-fidelity procedure regions should require explicit procedure-specific medical validation.

## 24. Asset storage

Large medical binaries must not live directly in the main Git repository.

Git stores schemas, manifests, provenance, hashes, validation reports, and small fixtures.

Large source and runtime assets are stored externally and identified by content hash and version.

## 25. Event system

Meaningful simulation actions generate structured versioned events.

Events are the primary source for replay, assessment, debugging, analytics, and instructor review.

## 26. Deterministic replay

Where practical:

same case + same initial state + same compatible engine/model versions + same input stream + same seed

should produce the same clinically relevant event sequence.

## 27. Versioning

The project separately versions application, engine, schemas, event schema, canonical anatomy, anatomy assets, physics model, imaging model, procedure definitions, and case definitions where relevant.

Saved sessions retain enough version information to reconstruct their environment.

## 28. Runtime architecture

Browser runtime is primarily TypeScript.

Heavy authoring and preprocessing are primarily Python plus medical authoring tools such as 3D Slicer.

UI, rendering libraries, medical domain logic, and physics backends remain separated.

## 29. Input architecture

Mouse, touch, Apple Pencil, and future haptic devices map through an input abstraction layer.

Core instrument logic must not depend directly on browser input APIs.

## 30. Units

Medically meaningful public/domain APIs must not rely on ambiguous unitless values.

Internal high-performance solvers may use normalized or SI arrays if conversion is explicit and tested.

## 31. MVP 0

MVP 0 must demonstrate:
- desktop and iPad browser runtime
- one medically grounded distal forearm/wrist region
- AnatomicalEntity system
- provenance and accuracy metadata
- patient-space coordinates
- 3D visualization and structure selection
- CT/reference image synchronization
- generic needle abstraction
- spatial tissue/boundary queries
- vein-wall and vein-lumen traversal recognition
- arterial puncture recognition
- structured event logging
- deterministic replay
- minimal venous-access procedure evaluation

MVP 0 does not require complete AVF surgery, full CVC, ultrasound, guidewires, catheters, suturing, bleeding, heartbeat, hemodynamics, or tissue FEM.

## 32. Architectural prohibitions

Unless the specification is intentionally revised, the following are prohibited:
- equating an anatomical entity with one render mesh
- treating AI-generated anatomy as validated anatomy
- storing medical logic in React UI components
- anatomy depending on procedures or rendering libraries
- anatomy depending directly on a physics backend
- procedure-specific generic instruments
- instruments directly mutating patient medical state
- rigid linear-only procedure architecture
- silently modifying original medical data
- using render LOD geometry as medical ground truth
- altering validated Medical Master geometry for performance
- treating automatic segmentation as automatically medically validated
- requiring engine changes for every new procedure
- medically meaningful unitless values without explicit reason
- bypassing provenance or validation for convenience

## 33. Decision priority

When goals conflict, priority is:

1. medical correctness and traceability
2. architectural extensibility
3. reproducibility
4. separation of concerns
5. runtime usability
6. performance
7. visual polish
8. implementation convenience

## 34. Change policy

If an implementation conflicts with this specification, do not silently work around it.

Identify the conflict, explain why it exists, propose the smallest explicit specification change, and update the governing documents before implementing the architectural exception.
