# TASK-040 lumen membership contract

TASK-037 already establishes generic point membership in a lumen. TASK-040 adds
only the semantic distinction needed by MVP 0 to tell venous lumen from arterial
lumen.

## Contract

`SpatialIndexEntry.vascularLumenKind` is optional explicit metadata with values
`venous` or `arterial`. It is valid only on entries that also carry the
`lumen` membership role.

`PointQueryResult.lumens` returns `LumenSpatialMatch` values. Each match carries
`vascularLumenKind`. A null value means the point is known to be in a lumen but
no venous/arterial classification was supplied.

Spatial does not infer vascular meaning from:

- structure or entity ID strings
- display names
- geometry shape, radius, position, or orientation
- BoundaryEntity identity or separates ordering
- renderer metadata

The semantic classification must be supplied by the patient/asset binding that
constructs the spatial index. Future medical assets may source that binding from
canonical anatomy and validated asset metadata without changing this query
contract.

## Fixture

The synthetic vein and artery now carry explicit `vascularLumenKind` metadata.
They remain development fixtures and make no medical-validation claim.

No persistent schema, BoundaryEntity, interaction event, ordered penetration path,
or renderer contract is changed by TASK-040.
