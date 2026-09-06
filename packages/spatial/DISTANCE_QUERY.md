# TASK-041 distance query contract

DistanceQuery is a stateless patient-space query for the distance from a point to
one explicitly identified patient structure's bound spatial representation.

## Semantics

The caller supplies a `StructureId`. The query returns the matching semantic
identity together with a canonical `Length`.

The distance is unsigned and representation-defined. For the current solid box
and cylinder adapters it is zero when the point is inside or on the represented
region, and otherwise the Euclidean minimum distance to that solid region.

TASK-041 deliberately does not introduce:

- signed distance or inside/outside semantics
- distance specifically to a BoundaryEntity
- nearest-structure search
- tissue traversal or ordered penetration paths
- renderer geometry access
- procedure or interaction meaning

The target is never inferred from display names, IDs-as-text, vascular type,
proximity, or rendering metadata. The `StructureId` binding supplies semantic
identity and the adapter supplies geometry only.

## Failure behavior

Unknown structure IDs, duplicate structure bindings, non-finite patient-space
points, and non-finite or negative adapter distances fail explicitly.

No schema, anatomy, patient-state, boundary-query, lumen-classification,
interaction, or renderer contract is changed by TASK-041. TASK-043 may later
choose how this capability is exposed through the small public Spatial Query API.
