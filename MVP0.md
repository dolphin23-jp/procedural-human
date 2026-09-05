# Procedural Human — MVP 0 Specification

## 1. Purpose

MVP 0 validates the foundational architecture of Procedural Human.

It is not a complete clinical procedure.

Its job is to prove that medically grounded anatomy, patient-space coordinates, 3D rendering, medical imaging, generic instruments, anatomical interaction, structured events, procedure evaluation, replay, and desktop/iPad runtime can operate together without violating the project architecture.

## 2. MVP 0 definition

MVP 0 uses one limited left distal forearm/wrist patient region.

The user can:
1. inspect medically grounded 3D anatomy
2. show/hide structures and alter opacity
3. inspect provenance and accuracy metadata
4. view registered CT or trusted reference imaging
5. synchronize a 3D section plane with imaging
6. manipulate one generic needle
7. pass the needle through tissues
8. detect vessel wall and lumen traversal
9. distinguish venous from arterial entry
10. record structured events
11. evaluate a minimal venous-access goal
12. replay the session deterministically

The application must run in a supported desktop browser and real iPad Safari.

## 3. Target region

Primary region: left distal forearm and wrist.

Exact crop may be adjusted according to source-data quality.

## 4. Required anatomy

Mandatory where medically supportable:
- skin
- subcutaneous soft-tissue region
- radius
- ulna
- radial artery
- ulnar artery
- cephalic vein or an equivalent validated superficial target vein
- relevant major muscle/tendon structures

Strongly preferred:
- superficial radial nerve
- relevant additional superficial veins
- clinically relevant fascia/boundaries

Do not fabricate a structure merely to complete the list. Lower-confidence structures must expose their limitation.

## 5. Medical asset requirement

Development may initially use a clearly labeled synthetic fixture such as a skin slab, soft-tissue block, vein cylinder, and artery cylinder.

The fixture is non-medical-test-fixture and is never presented as educational anatomy.

The final MVP 0 acceptance build uses medically grounded anatomy.

Critically, replacing the fixture with the medical asset must not require redesign of the Interaction or Procedure Engine.

## 6. Required metadata

Clinically meaningful structures support:
- internal anatomical ID
- human-readable name
- type
- laterality where relevant
- provenance
- accuracy profile
- validation status
- available representations

## 7. Patient model

MVP 0 has one primary patient case:

Canonical Anatomy → Patient Instance → Runtime State.

Dynamic physiology, multiple patients, pathology generation, and variation generation are not required.

## 8. Physiology scope

Physiology may be static.

Not required:
- heartbeat
- vessel pulsation
- respiration
- blood pressure simulation
- dynamic venous pressure
- blood flow
- bleeding

Future-compatible interfaces must exist.

## 9. Required 3D functionality

The user can rotate, zoom, pan, select structures, hide/show structures, change opacity, identify structures, and inspect provenance/validation metadata.

Picking resolves to semantic anatomy, not only mesh names.

## 10. iPad requirement

iPad Safari is a first-class acceptance target.

Required:
- touch camera navigation
- pinch zoom
- pan
- structure selection
- imaging-plane interaction
- needle manipulation
- replay controls

Apple Pencil may initially behave as pointer input. Advanced pressure sensing is not required.

Hover-only interactions are prohibited for required MVP features.

## 11. Spatial Query requirement

MVP 0 provides a shared patient-space Spatial Query service.

At minimum it determines:
- point membership in defined tissue/structure
- trajectory intersections
- clinically significant boundary crossings
- vessel lumen membership
- venous versus arterial structure identity

## 12. Needle instrument

MVP 0 implements a generic NeedleDefinition and NeedleInstance with functional regions including tip, bevel, shaft, and lumen.

Runtime state includes pose, tip position, tip direction, trajectory, and penetration path.

The Needle contains no procedure-specific logic.

## 13. Needle interaction scope

Required:
- contact
- structure intersection
- traversal
- boundary crossing
- lumen entry
- lumen exit
- withdrawal

Not required:
- realistic puncture-force curve
- needle bending
- tissue deformation
- vascular-wall deformation
- bleeding
- aspiration physics
- tissue tearing

## 14. Boundary events

Clinically meaningful transitions produce structured events such as:
- instrument contacted structure
- boundary crossed
- lumen entered
- lumen exited

Patient-space crossing location and relevant actor/target identities are retained.

## 15. Medical imaging

MVP 0 includes at least one acquired or trusted reference medical-image volume registered to patient space, preferably CT.

Required:
- image loading
- patient-space positioning
- axial viewing
- synchronized 3D section plane
- user-controlled section position

Arbitrary oblique MPR is a target requirement unless an explicit scope revision documents a substantial blocker.

## 16. CT/3D synchronization

The system demonstrates:
image coordinate ↔ patient coordinate ↔ 3D render coordinate.

Scrolling imaging moves the 3D plane. Moving the 3D plane updates imaging where supported.

Coordinate transforms are tested. Silent assumed registration is prohibited.

## 17. Imaging source integrity

Original acquired image data is immutable.

Segmentation, surfaces, annotations, and simulated overlays are derived data and remain distinguishable.

## 18. Event system

MVP 0 implements versioned structured events including at least:
- instrument contact
- boundary crossing
- lumen entry
- lumen exit
- procedure goal satisfied
- safety violation

All use the shared SimulationClock.

## 19. Minimal procedure

MVP 0 includes one deliberately small data-defined procedure: Venous Access Sandbox.

Primary goal: needle tip enters the designated target venous lumen.

The target vessel is supplied by case binding.

Procedure logic consumes events. It does not move instruments or modify anatomy.

## 20. Minimal safety evaluation

Target venous entry is success.

Arterial puncture is a safety violation, not a physically impossible action.

The physical interaction still occurs and the Procedure Engine evaluates its clinical meaning.

## 21. Event recording and replay

A session preserves needle trajectory, relevant anatomical interactions, procedure outcome, and safety violations.

Replay with the same case, initial state, compatible versions, input stream, and seed reproduces the same clinically relevant event sequence.

Pixel-identical graphics are not required.

## 22. Runtime provenance display

The user can inspect source class, accuracy, validation, and other relevant metadata for principal structures.

The UI can remain simple.

## 23. Explicitly out of scope

MVP 0 must not expand into:
- complete AVF surgery
- complete CVC
- dialysis catheter workflow
- lumbar puncture workflow
- chest drainage
- pericardiocentesis
- guidewire
- catheter
- dilator
- forceps
- scalpel
- scissors
- vascular clamp
- suturing
- interactive ultrasound
- Doppler
- synthetic CT
- MRI simulation
- X-ray/fluoroscopy simulation
- heartbeat
- respiration
- dynamic hemodynamics
- FEM/XPBD tissue deformation
- bleeding
- realistic needle-force simulation
- VR/AR
- multiplayer
- advanced haptics

Architecture placeholders are allowed; implementation is not.

## 24. Performance acceptance

MVP 0 performance is measured on at least one real target iPad.

Initial baseline: approximately 30 fps or better median during core interaction, with responsive camera and needle control.

Performance optimization must not alter Medical Master geometry.

## 25. Automated acceptance tests

Required categories:
- schema validity
- architecture dependency rules
- known spatial-query trajectories
- boundary detection
- coordinate round trips
- vein/artery interaction distinction
- venous success rule
- arterial safety violation rule
- deterministic replay
- required medical asset validation

## 26. Medical acceptance

Software success and medical acceptance are separate.

The final forearm asset must have documented review appropriate to MVP claims.

Principal vessels, relevant spatial relationships, image/3D relationship, and source provenance must be reviewable.

A technically successful but medically unreliable build does not satisfy MVP 0.

## 27. Completion demonstration

1. Open on desktop or iPad.
2. Inspect the left distal forearm/wrist in 3D.
3. Select structures and make skin partially transparent.
4. Inspect source/accuracy/validation metadata.
5. Open CT/reference imaging and scroll sections while the 3D plane follows.
6. Move the 3D plane and observe imaging follow.
7. Activate the generic needle.
8. Advance through skin/soft tissue into the target vein and achieve venous-access success.
9. In another attempt, enter the artery and record a safety violation.
10. Finish the session, inspect the event timeline and trajectory, and replay the clinically relevant sequence.

## 28. Exit criteria

MVP 0 is complete only when:
- architecture tests pass
- required schemas validate
- a medically grounded runtime asset loads
- desktop and real iPad runtime work
- imaging/3D coordinates synchronize
- generic needle uses the Interaction Engine
- vessel wall/lumen traversal is recognized
- venous and arterial interactions differ
- structured events are recorded
- minimal procedure evaluation works
- replay works
- provenance is inspectable
- no out-of-scope system was required to compromise the architecture
