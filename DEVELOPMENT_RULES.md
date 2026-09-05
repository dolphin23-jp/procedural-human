# Procedural Human — Development Rules

## 1. Purpose and authority

These rules govern human and AI implementation work.

Authority order:
1. MASTER_SPEC.md
2. ARCHITECTURE.md
3. DATA_POLICY.md
4. MVP0.md
5. DEVELOPMENT_RULES.md
6. assigned task in TASKS.md

Lower-level instructions never silently override higher-level specifications.

## 2. Default development behavior

Before changing code:
1. read relevant specifications
2. identify the exact assigned task
3. inspect existing code/tests
4. identify allowed packages
5. preserve unrelated behavior
6. implement the smallest complete change
7. add/run appropriate tests
8. report unresolved issues explicitly

Do not expand scope because additional improvements look useful.

## 3. One task, one responsibility

Tasks should have one primary engineering objective.

Large concerns are decomposed before implementation.

High-risk modules such as Spatial Query, registration, Interaction, and Replay should usually be implemented in small bounded steps.

## 4. Scope discipline

Only files necessary for the assigned task should be changed.

Do not perform unrelated cleanup, whole-repo formatting, broad renames, unnecessary library migrations, or adjacent refactors.

If a broader change is truly required, document it as an architectural dependency rather than sneaking it into the task.

## 5. No silent architectural changes

If the task conflicts with governing specifications or package dependency rules:
1. identify the conflict
2. explain it
3. propose the smallest change
4. do not implement the violating design unless the specification is intentionally revised

Convenience is not justification for architecture drift.

## 6. Package ownership

Put code where the concept belongs:
- anatomical identity → anatomy
- patient-specific state → patient
- spatial interpretation → spatial
- needle definition → instruments
- needle/tissue interaction → interaction
- clinical evaluation → procedures
- presentation → ui
- composition → session

Do not place logic in a convenient package merely because it has access to needed objects.

## 7. Dependency direction

Never introduce forbidden reverse dependencies.

Use interfaces, adapters, events, dependency injection, or Session composition instead.

Architecture dependency rules should fail CI when violated.

## 8. External libraries remain behind adapters

Three.js, Cornerstone, React, future physics backends, and medical Python libraries remain confined to their owning adapter/package.

Domain packages use project-owned types and interfaces.

## 9. Public APIs remain small

Do not import private internal implementation paths across packages.

If another package needs a capability, define the smallest appropriate public interface and test that contract.

## 10. Persistent data is schema-first

Persistent serialized contracts are governed by schemas/.

Do not independently define incompatible shapes in TypeScript, Python, or hand-written JSON.

Schema changes require explicit compatibility/version reasoning.

Old fields are never silently reinterpreted.

## 11. Medical meaning is typed

Use typed IDs, schema-defined values, semantic roles, or enums for domain-significant concepts.

Avoid uncontrolled names such as artery1 or blueVein.

## 12. Units and coordinate spaces are explicit

Medically meaningful domain values carry units.

Every spatial API makes coordinate space explicit, such as PatientSpacePoint, RenderSpacePoint, or ImageVoxelCoordinate.

Medical event locations are stored in patient space.

Never silently assume identity transforms.

## 13. Render geometry is not medical truth

Render meshes are derived representations.

They do not automatically become the source for anatomical measurement, validation, or original segmentation.

Validated collision representations may be used for interaction but remain linked to Medical Master.

## 14. Do not alter medical data to fix software

If anatomy is inconvenient for the code, fix the code.

Do not move vessels, enlarge lumens, simplify nerves, alter registration, or change patient geometry to make tests pass.

Medical asset changes follow DATA_POLICY.md.

## 15. AI must not invent missing medical data

If required information is unavailable, mark it unavailable, use a clearly labeled fixture, use an explicitly lower-confidence source, or revise scope.

Do not fabricate plausible anatomy and label it validated.

## 16. Fixtures remain distinct

Synthetic fixtures are encouraged for fast deterministic engine tests.

They are explicitly non-medical and must never be exposed as validated educational anatomy.

## 17. Tests accompany behavior

New domain behavior requires appropriate tests:
- schema → validation tests
- spatial → geometric tests
- interaction → event tests
- procedure → evaluator tests
- replay → deterministic comparison
- imaging coordinate → round-trip tests

Compilation alone is not completion.

## 18. Never delete tests merely to pass

When a test fails, determine whether implementation or expected behavior is wrong.

Do not weaken, skip, delete, or arbitrarily broaden tolerances simply to obtain green CI.

Medical/geometric tolerance changes require rationale.

## 19. No hidden medical fallbacks

Forbidden examples:
- unknown registration → assume identity
- missing high-fidelity vessel → load generic cylinder
- unknown unit → assume mm

Medical ambiguity fails visibly or uses an explicitly configured, documented fallback.

## 20. Error handling

Errors must be actionable.

Do not broadly catch-and-ignore medically significant failures.

Registration, schema, spatial-integrity, or representation failures propagate as explicit domain errors.

## 21. Event separation

Physical event producers do not know procedure scoring or UI feedback.

Interaction emits physical/semantic events.

Procedure interprets clinical meaning.

UI subscribes separately.

## 22. Procedure code does not simulate physics

Procedure may interpret arterial wall crossing as unsafe, but it does not decide whether the physical crossing occurred.

That belongs to Spatial/Interaction/Physics.

## 23. Instruments remain procedure-agnostic

Generic instruments do not contain CVC/AVF/LP correctness logic.

Procedure definitions specify acceptable instrument characteristics.

## 24. Controlled state mutation

Patient medical state changes only through designated state-transition mechanisms.

UI, instruments, renderer, and procedure logic do not arbitrarily mutate medical state.

## 25. Session is the composition root

High-level runtime dependencies are assembled in Session.

Avoid global singleton coupling.

Simulation-critical global mutable state is prohibited.

## 26. Determinism

Simulation-critical randomness uses session-scoped seeded sources.

Do not call uncontrolled randomness directly in domain logic.

Changes affecting replay semantics require versioning and compatibility reasoning.

## 27. Performance

Measure performance before optimizing.

Prefer spatial indexing, caching, region loading, LOD, render-quality reduction, collision simplification, reduced physics fidelity, GPU acceleration, and backend specialization.

Do not modify Medical Master geometry to chase performance.

## 28. iPad is not secondary

Required MVP features must work without hover, desktop-only keys, right-click, or desktop memory assumptions.

Browser input is normalized before core instrument logic.

## 29. No premature fidelity

Do not spontaneously implement future systems such as hemodynamics, ultrasound, bleeding, FEM, guidewire, or suturing before an explicit task authorizes them.

Interfaces may be prepared where specified.

## 30. No premature generalization, no MVP hard-coding

Avoid giant speculative frameworks.

At the same time, do not encode assumptions such as one patient can ever exist, only cephalic vein can be targeted, only one modality can exist, or every needle always targets the left wrist.

Implement the smallest abstraction consistent with established future architecture.

## 31. Dependencies

New third-party dependencies require justification for problem solved, bundle impact, iPad/browser compatibility, maintenance, and license.

Pin dependencies through lockfiles.

Upgrades should be explicit.

## 32. Reproducible build

A clean checkout with documented prerequisites can install, typecheck, test, and build without undocumented local hacks.

External medical assets are handled through explicit manifests/setup.

## 33. Repository hygiene

Do not accidentally commit:
- large source imaging
- generated medical binaries not intended for Git
- credentials or API keys
- identifiable clinical data
- restricted asset credentials

Generated files should be identifiable and preferably regenerated from source rather than manually edited.

## 34. Comments and medical claims

Comments explain why, medical assumptions, architectural constraints, numerical reasoning, and limitations.

Do not write unsupported medical claims in comments based only on model inference.

## 35. Commit discipline

Prefer small task-aligned commits containing the feature, its tests, and necessary documentation.

Suggested style:
TASK-027: add segment spatial query

## 36. Completion report

For each task report:
- Changed
- Files
- Tests
- Architecture/API/schema changes
- Limitations
- truly required follow-up

Do not present unrelated enhancements as required.

## 37. If blocked

Complete safe portions, identify the exact blocker, explain the minimal decision required, and avoid unrelated changes.

Do not silently invent medical assumptions.

Reasonable non-medical implementation defaults may be chosen when bounded and specification-compatible.

## 38. Medical review remains independent

Software success cannot upgrade V2 to V3/V4 if those levels require medical review.

AI review is not medical acceptance.

Geometry validation is not medical acceptance.

## 39. Astra-specific operating rules

When Astra is assigned a task:
1. read MASTER_SPEC.md
2. read ARCHITECTURE.md
3. read DEVELOPMENT_RULES.md
4. read relevant data/MVP specification
5. read the exact TASKS.md entry
6. inspect existing implementation
7. implement only the assigned task
8. preserve architecture boundaries
9. add/update tests
10. run relevant validation
11. do not delete tests to obtain success
12. report architecture conflicts instead of violating specifications

TODO comments do not authorize future work.

Astra must not replace existing correct modules merely because another implementation appears cleaner.

Astra must preserve medical uncertainty and must never fabricate evidence, reviewers, dataset versions, measured errors, confidence, or citations.

## 40. Task prompt template

A preferred implementation prompt is:

Read:
- MASTER_SPEC.md
- ARCHITECTURE.md
- DEVELOPMENT_RULES.md
- relevant specification
- TASKS.md entry TASK-XXX

Implement TASK-XXX only.

Allowed packages:
- ...

Do not modify:
- ...

Acceptance criteria:
- ...

Required tests:
- ...

Do not implement future roadmap features.

## 41. Definition of done

A task is complete only when:
- assigned behavior is implemented
- architecture remains valid
- types compile
- relevant tests pass
- schemas remain valid
- unrelated behavior is preserved
- public contract documentation is updated if changed
- limitations are reported
- scope was not expanded

A feature is not done merely because the UI appears to work.

## 42. Project-level principle

Procedural Human evolves through small validated changes, stable interfaces, and progressive fidelity—not repeated rewrites for each new procedure.
