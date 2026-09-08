# TASK-072 — Spatial contact evidence

`SpatialContactQueryApi.queryContacts(PatientSpaceSegment)` is an additive
public capability implemented by `SpatialQueryService`. The original
`SpatialQueryApi` stays source-compatible; its three methods and their
semantics are unchanged. Interaction uses the public capability, never the
internal ContactQuery or geometry adapters.

The result is a frozen array of `SpatialContactInterval`: StructureId,
canonical EntityId, and start/end locations with PatientSpacePoint, dimensionless
t and Length distance from the supplied segment start.

## Geometric meaning

For each patient structure, intersect the segment with the union of its supplied
closed regions (interior plus surface). Return the maximal connected closed
intervals. A single tangent or endpoint touch has start.t == end.t.
This is geometric evidence, not an Interaction contact event, puncture, boundary
crossing, lumen transition or procedure judgment.

Use the existing finite-partition region contract and numerical validation.
Every reported interior intersection contributes a contact point; inside and
boundary open cells contribute their closures. Classify endpoints explicitly,
because the existing adapter contract permits endpoint intersection omission.
No fixed sampling step, epsilon clustering, mesh inspection, normal inference,
or new anatomical geometry is introduced.

Exactly overlapping/touching intervals belonging to the same StructureId merge.
Different structures remain separate, including coincident contacts. Real gaps,
however small, remain gaps. Multi-region structures require consistent canonical
identity; contradictions fail. Distance-query binding ambiguity still requires
explicit distanceEntries as before.

Sort by start.t, then StructureId using code-unit order, then end.t. Input region
order and duplicated intersection enumeration do not change results. Positions,
locations, intervals and the array are frozen snapshots. Adapters must describe
one fixed patient/asset state throughout a query.

## Edge cases and failure

- Start inside/on a region: its initial contact component starts at t=0.
- End on a surface: contact at t=1 is included.
- Isolated tangency: a zero-width contact interval.
- Surface following: a contact interval, without choosing a crossing direction.
- Zero displacement: empty, after coordinate validation; no geometry calls.
- Empty explicit region set: empty contact evidence.
- Invalid coordinates, overflowing arithmetic, off-segment intersections,
  unresolvable partitions, unknown classification, and adapter failures propagate.
  No anatomy/representation fallback is supplied.

This capability requires closed regions satisfying the existing finite-partition
contract. Unsupported/open surfaces require an explicit future representation
contract; do not fabricate closure. Contact correctness/completeness relies on
the adapter, not on a renderer or a structure's name. Existing intersection
consistency tolerance remains a numerical check, not anatomical accuracy.

`querySegment` still omits isolated tangency and endpoint-only crossings and
rejects finite boundary following. Tests preserve those semantics. This contact
capability is the minimal additional evidence needed for TASK-072.
