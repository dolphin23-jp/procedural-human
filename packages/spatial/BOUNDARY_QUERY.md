# TASK-039 boundary query contract

BoundaryQuery is a patient-scoped, stateless Spatial query. Bindings and geometry
must describe one fixed patient/asset state throughout an execution.

## Identity and sides

A BoundaryEntity is a canonical semantic interface, not a geometric surface or
patient structure. Its provisional `separates` references do not define spatial
inside/outside and are intentionally unchanged. BoundaryRegionBinding explicitly
associates that entity with a typed SpatialRegionId, a patient StructureId and a
replaceable region representation. The complete surface of that region is the
bound surface. The same semantic boundary can bind multiple distinct regions;
each region has exactly one binding in a query. A region is not a lumen label.

Entry means outside → inside of the identified region. Exit is the reverse.
The two sides are identified by `{ regionId, side }`: outside is that region's
complement, not an inferred adjacent anatomical entity. There is no universal
anatomical inside, and no meaning is inferred from names, normals, winding,
`separates` tuple order, or representation identifiers. Future pleural, dural,
pericardial or fascial interfaces can choose explicit reference regions.
Authoring must establish that binding; geometry cannot validate medical meaning.

Spatial adds only a type dependency on anatomy for BoundaryEntity. Anatomy and
Patient do not depend on Spatial. No persistent schemas or canonical ontology
are reinterpreted. No third-party dependency was added.

## Geometry capability and conversion

TASK-035's boolean containment and unspecified contact list are insufficient:
closed-set containment conflates boundary and interior, and an incomplete contact
list cannot establish state transitions. RegionSpatialRepresentationAdapter is
an opt-in extension with three-way classifyPoint and a strengthened contact-list
contract. Legacy adapters and TASK-037/038 queries retain their interfaces.

The extension requires all isolated interior contacts and all interior endpoints
of boundary-overlap intervals. Between contacts, classification must be constant.
This applies to nonconvex and disconnected regions too. Segmentation/volume/SDF
adapters may implement the same partition without a triangle mesh. Open surfaces
need a declared region model; unsupported or unresolved geometry must fail, not
pretend that a normal establishes inside. Future adapters need conformance tests.

BoundaryQuery converts each hit to dimensionless t along the segment's dominant
axis, verifies it lies on the patient-space segment, sorts and deduplicates t,
and classifies a midpoint in each resulting open interval. Only an adjacent
outside/inside change produces a result. Position is reconstructed as
`start + t * (end - start)`; distanceFromStart is canonical Length, constructed
from `t * hypot(end - start)` in millimetres. Results have strictly 0 < t < 1.
No offset probing or fixed-step sampling is used.

The existing box adapter now reports endpoint contacts and surface-overlap ends
rather than excluding contacts using closed-set containment. The cylinder and
box implement strict interior/boundary/exterior classification. These primitives
remain development geometry, not medically validated anatomy.

## Degenerate and numerical behavior

- Tangent: unchanged side yields no crossing.
- Surface overlap: transitions involving a boundary interval yield no crossing;
  the query does not assign an arbitrary unique crossing point to a contact span.
- Endpoint on boundary: no crossing at t=0 or t=1. Later interior crossings still
  count. A sequence split exactly at a boundary requires later Interaction/path
  state to establish a transition across calls; this query keeps no history.
- Zero length: empty, including on the boundary; no adapter call.
- Exact repeated hits: one knot and at most one crossing per region there.
- Close distinct hits: kept distinct, including thin regions. No epsilon grouping
  or quantization. Adapters should canonicalize repeated approximate contacts;
  if an interval has no representable midpoint, BoundaryQueryFailure is raised.
- Invalid/nonfinite coordinates, out-of-range hits, missing classification,
  off-segment hits, or unresolvable arithmetic: explicit BoundaryQueryFailure.

The single new dimensional numerical tolerance is
`boundaryIntersectionConsistencyTolerance = millimetres(1e-7)`. It only permits
roundoff perpendicular to the segment when checking returned geometric points;
it does not classify sides, merge hits, clamp t, or change geometry. Positions
within that consistency bound are reconstructed on the segment. It is not an
anatomical accuracy claim. Primitive calculations use IEEE-754 arithmetic;
near tangency and extreme scales remain subject to adapter numerical accuracy.
The query cannot certify that a third-party adapter supplied a complete partition.

## Determinism and scope

Sort by t (physical progression), then boundaryId, regionId, structureId and
direction using locale-independent string comparison. Exactly coincident
crossings of different semantic boundaries remain separate. Numerically close
but unequal t retain physical order. Input binding order and hit enumeration
order do not control output. Results and position values are frozen snapshots.

TASK-042 reuses the numerical partition through an internal helper without
changing these crossing semantics; see PENETRATION_PATH.md for ordered occupancy
and coincident transition groups. Cross-call continuity, TASK-043 public
Human.query, Interaction events, procedure judgment, rendering and physics
remain outside this query. Partial surfaces
with different semantic boundary IDs on one region, general from-region/to-region
adjacency, medical asset bindings and validation remain future authoring/Spatial
extensions; no fabricated closure or lumen meaning is introduced here.
