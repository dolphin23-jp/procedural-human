# Procedural Human — Medical Data Policy

## 1. Purpose

This document defines how medical, anatomical, imaging, simulation, and derived data are classified, transformed, stored, validated, and used.

The primary goal is to prevent uncertain, inferred, synthetic, or visually optimized data from being silently treated as validated anatomical truth.

MASTER_SPEC.md has higher authority.

## 2. Core principle

Every medically meaningful datum must answer:
- where did it come from?
- what transformations were applied?
- what is actually known?
- how accurate is it?
- what has been validated?
- what remains uncertain?
- is it suitable for this educational use?

Visual realism and AI confidence are not sufficient.

## 3. Source classes

### acquired
Actual patient imaging or measurements such as CT, CTA, MRI, ultrasound, radiography, or clinical segmentation.

Acquired status applies only to what the source reliably demonstrates.

### cadaver-derived
Cryosection or dissected anatomical datasets.

High-fidelity reference does not make one individual universal normal anatomy.

### atlas-derived
Geometry or relationships derived from validated anatomical atlases/reference works.

Atlas-derived anatomy must not be presented as patient-specific merely because it is registered to a patient.

### literature-derived
Parameter ranges or properties from published literature, such as vessel diameters, variant prevalence, tissue mechanics, acoustics, or physiology.

Exact sources are traceable.

### algorithm-derived
Automatic segmentation, centerline extraction, surface reconstruction, registration, LOD generation, and related processing.

Algorithmic derivation is not medical validation.

### human-edited
Data manually corrected or constructed using anatomical/medical judgment.

Manual edits and review status are recorded where practical.

### ai-inferred
Geometry, metadata, relationships, segmentation, or properties materially inferred by generative/predictive AI where the source does not directly establish the result.

AI-inferred data is unvalidated by default and is never automatically medically validated.

### synthetic
Simulation-generated anatomy, pathology, or imaging created under explicit constraints.

Synthetic may be medically useful but remains distinguishable from acquired data.

### development-fixture
Simplified boxes, cylinders, slabs, spheres, or other geometry used solely for software testing.

Never presented as validated educational anatomy.

## 4. Authority hierarchy

For patient-specific geometry, default priority is:

patient-specific acquired evidence
→ same-subject cadaver/image evidence
→ validated image-derived anatomy
→ validated atlas-derived anatomy
→ literature-constrained inference
→ expert inference
→ AI inference

The hierarchy is question-dependent. A small nerve invisible on CT must not be falsely labeled image-derived simply because it has been registered to the CT.

## 5. Medical Master

Medical Master is the authoritative validated representation from which runtime assets are derived.

It may include:
- segmentation volumes
- reference surfaces
- centerlines
- anatomical graph
- boundary definitions
- semantic metadata
- provenance
- validation results
- mappings between representations

Render meshes, LODs, collision meshes, and physics meshes are derived products.

## 6. Immutable source principle

Original source data is never destructively overwritten.

Processing produces new derived artifacts:

SOURCE → DERIVED → VALIDATED DERIVED → RUNTIME.

Runtime corrections never silently flow backward into source/Medical Master.

## 7. Provenance and transformation lineage

Medically relevant structures retain sufficient lineage, including where applicable:
- sourceClass
- sourceDataset/sourceIdentifier
- derivationMethod
- derivationSoftware/version
- manualEdits
- reviewer/reviewStatus
- parentAsset
- contentHash
- registration method
- transformation history

A final runtime LOD still traces back to the validated source representation.

## 8. Automatic segmentation

Automatic segmentation is encouraged as an efficiency tool.

Default status is draft, not validated.

Review requirements depend on intended use. A segmentation may be acceptable for whole-body orientation but unacceptable for an AVF operative field.

## 9. AI usage

AI may assist with code, metadata extraction, pipeline automation, candidate segmentation review, format conversion, literature organization, and validation tooling.

AI must not silently establish medical truth.

If AI proposes a change to validated anatomy:
1. preserve the validated version
2. create a candidate revision
3. record the change
4. run technical validation
5. obtain appropriate medical review
6. release a new version only if accepted

## 10. Validation levels

Recommended levels:

V0 — Unreviewed  
V1 — Technical validation complete  
V2 — Human anatomical review complete  
V3 — Medical review complete  
V4 — Procedure-specific medical validation complete

Technical mesh validity is not medical validation.

A structure may be V3 for general anatomy and not V4 for a specific procedure.

## 11. Accuracy profile

Accuracy is multi-dimensional and may include:
- identityAccuracy
- topologyAccuracy
- geometryAccuracy
- registrationAccuracy
- diameterAccuracy
- relationshipAccuracy

Simulation fidelity is separate:
- mechanicalFidelity
- hemodynamicFidelity
- acousticFidelity

Do not collapse these into one confidence score.

## 12. Uncertainty and no false precision

Material uncertainty is represented explicitly.

Source resolution bounds downstream accuracy claims. A dense smoothed mesh derived from 1 mm imaging does not justify 0.1 mm anatomical accuracy.

Derived mesh density is not anatomical resolution.

## 13. Patient-specific image priority

Canonical anatomy provides semantic identity, not permission to overwrite observed patient anatomy.

When patient imaging reliably demonstrates a structure, patient evidence defines the patient-specific geometry.

## 14. Atlas registration

An atlas-derived structure registered to a patient remains atlas-derived and patient-registered.

Registration does not make it acquired patient anatomy.

## 15. Anatomical variation and synthetic patients

Variation may come from acquired evidence, cadaver data, validated literature distributions, expert-defined variants, or constrained synthetic generation.

Random unconstrained geometry mutation is prohibited for medically validated cases.

Future synthetic cases record generation parameters, source distributions, random seed, and model version.

## 16. Pathology

Synthetic pathology should be represented separately from baseline anatomy where practical.

Example: base thorax anatomy + pneumothorax state.

Pathology assets also require provenance and validation.

## 17. Patient data privacy

Real clinical data must be treated as potentially identifiable.

It must not be committed to the public source repository.

De-identification must consider DICOM metadata, filenames, burned-in annotations, reports, timestamps, accession identifiers, and potentially reconstructable anatomy—not only patient name.

Clinical data handling must follow applicable legal, institutional, ethical, and research requirements.

## 18. Clinical data isolation

Recommended storage classes:
- public-assets
- validated-reference-assets
- restricted-clinical-assets
- development-fixtures

Restricted clinical data must not become a transitive dependency of a public build without explicit permission.

## 19. Licensing

Every external dataset records licensing/usage conditions.

Before redistribution, determine permission for modification, redistribution, commercial use, public hosting, and derivative works.

Local technical usability does not imply legal redistributability.

## 20. Dataset identity and hashing

External datasets and important binary assets record:
- dataset identifier
- dataset version if available
- retrieval date
- SHA-256 content hash

This prevents silent upstream changes from altering validated assets.

## 21. Render, LOD, collision, and physics policy

Render assets may be smoothed, retopologized, compressed, and LOD-reduced only within documented tolerances.

LOD validation may include surface deviation, vessel diameter preservation, branch preservation, volume preservation, and boundary preservation.

Collision geometry may be simplified but must remain adequate for the medical interaction it evaluates.

Physics geometry may differ substantially from render geometry and must report its fidelity.

## 22. Imaging data policy

Imaging source types are:
- acquired
- synthetic
- hybrid

A real CT with a simulated needle overlay is hybrid.

Original acquired image data is immutable.

Derived segmentation, surface, annotation, and registration retain source references, derivation method, and validation.

Unknown registration is preferable to fabricated registration.

## 23. Promotion workflow

Recommended lifecycle:

DRAFT
→ TECHNICALLY_VALID
→ ANATOMICALLY_REVIEWED
→ MEDICALLY_VALIDATED
→ PROCEDURE_VALIDATED
→ RELEASED

Promotion is explicit.

## 24. Validation reports

Validation should produce machine-readable records where possible, including asset identity/version, validation level, technical metrics, reviewer scope/date where appropriate, and any waivers.

## 25. Procedure-specific validation

High-fidelity procedure regions validate clinically relevant relationships directly.

For future AVF use, examples include:
- superficial vein depth
- radial artery depth
- artery-vein relation
- nearby nerve course
- fascia
- vessel diameter
- branch points

General plausibility alone is insufficient.

## 26. Validation failure

If a required criterion fails, asset release fails unless the criterion is explicitly waived with rationale and the accuracy/fidelity claim is downgraded appropriately.

Tests are not deleted merely to permit release.

## 27. Corrections and historical reproducibility

Released asset corrections create new versions.

Old versions remain identifiable.

Dependent packages are rebuilt/revalidated as necessary.

Saved sessions retain asset IDs, versions, and hashes.

## 28. Storage separation

Git repository:
- code
- schemas
- manifests
- provenance
- validation metadata
- small fixtures

Local authoring cache:
- working data

External asset store:
- large validated binaries

Restricted storage:
- clinical data

## 29. Distribution

Runtime packages contain only the regions/assets necessary for their intended use.

This supports iPad performance, licensing control, reduced storage, and privacy isolation.

## 30. Asset Manifest

Every distributable medical asset package includes a manifest containing:
- assetId
- version
- contentHash
- region
- structures
- source/provenance
- accuracy
- validation
- representations
- dependencies
- license

Runtime medical meaning is not inferred from filenames.

## 31. No silent substitution

If a required high-fidelity representation is unavailable, the runtime must not silently substitute a lower-confidence one when medical meaning may change.

It must report the limitation, use an explicitly permitted fallback, or refuse the high-fidelity mode.

## 32. Educational transparency

Advanced users should be able to inspect source class, validation level, claimed accuracy, and simulation fidelity.

Explicit limitations are preferred over an illusion of perfect realism.

## 33. MVP 0 policy

MVP 0 uses:
- one medically grounded distal forearm/wrist runtime asset
- explicit provenance
- explicit validation
- clear fixture/medical separation
- immutable reference imaging
- versioned asset manifests

Development fixtures may be synthetic. Final educational acceptance does not use the fixture.

## 34. Prohibited practices

Prohibited unless policy is intentionally revised:
- AI-fabricated anatomy presented as validated
- automatic segmentation automatically promoted to medical validation
- modifying original DICOM as a normal processing step
- replacing Medical Master with prettier render geometry
- removing provenance for packaging convenience
- claiming mesh resolution as anatomical accuracy
- false precision unsupported by source resolution
- silently assuming image registration
- committing identifiable patient imaging to public Git
- mixing restricted clinical assets into public bundles
- undocumented manual anatomical correction
- deleting validation tests because assets fail
- redistributing unknown-license datasets without review
- silently substituting lower-confidence anatomy in a high-fidelity region

## 35. Decision rule

When uncertain, choose the lower confidence level.

If patient specificity is uncertain, do not claim it.

If AI inference is not validated, treat it as unvalidated.

If a transformation may have changed medical meaning, require review before release.
