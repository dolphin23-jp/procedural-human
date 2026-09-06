# TASK-042 ordered penetration path

`OrderedPenetrationPathQuery` is a stateless, patient-scoped Spatial capability.
Its bindings and adapters must describe one fixed patient/asset state for the
entire execution. It returns a frozen array of `PenetrationPathElement`, a
`span | transition` discriminated union. It is not a UI layer sequence or an
Interaction event stream. TASK-043's combined public query facade is not added.

## Input and identity

`SpatialRegionBinding` extends the existing `SpatialIndexEntry` with a required
`SpatialRegionId` and TASK-039's `RegionSpatialRepresentationAdapter` capability.
This explicitly opts into complete contact enumeration and three-way region
classification. Legacy TASK-035–041 interfaces are unchanged.

Multiple region bindings may share a `StructureId`. Every supplied region has
one authoritative adapter for this query; duplicate region IDs fail. Existing
`SpatialRegionId` is sufficient to identify each occupancy binding independently
of its patient structure, so no new ID brand or representation registry is needed.
A replaceable adapter is not the semantic region or the patient structure.
Non-region representations such as open collision surfaces and centerlines do
not automatically define occupancy and cannot be passed without a region model.
TASK-041's duplicate-StructureId rejection remains local to DistanceQuery.

Optional `PenetrationBoundaryBinding` values associate a `BoundaryEntity` with a
region ID. The query resolves the region's authoritative adapter and StructureId
by that ID to construct TASK-039 bindings. It never equates representations by
JavaScript object identity, names, geometry, size, or coordinates. Unknown region
IDs and duplicate boundary bindings for a region fail explicitly.

## Output model

A span has `start`, `end`, and all active `memberships`. Its parameter interval is
non-zero. Each location has dimensionless `t`, a `PatientSpacePoint` position,
and a `Length` distance from the segment start:

`p(t) = start + t * (end - start)`, with `0 <= t <= 1`.

Position and distance are retained alongside t to provide concrete, canonical
query snapshots consistent with BoundaryCrossing. No separate span length or
redundant full before/after occupancy is stored. The non-zero query covers the
whole supplied segment, including outside spans with empty memberships.

Each membership retains `regionId`, `structureId`, `canonicalEntityId`, `tissue`,
and `lumen`. These describe spatial occupancy and explicit semantic roles, not
an exclusive anatomical layer. Tissue and lumen roles may coexist. `lumen: null`
means no lumen role; `lumen: { vascularLumenKind: null }` means a known lumen with
no supplied vascular classification. TASK-040's venous/arterial metadata is copied
without inference or clinical judgment. An arterial traversal is ordinary output.

A transition has one `at` location, coincident `entered` and `exited` membership
sets, and the actual TASK-039 `boundaryCrossings` at that t. Entered/exited sets
are spatial region occupancy changes, not fabricated BoundaryCrossing values.
The latter retain boundary identity, StructureId, SpatialRegionId, from/to sides,
entry/exit direction, patient position and Length exactly as BoundaryQuery emits.
A region change need not have an authored medically meaningful boundary.

## Construction and numerical rules

1. Validate finite patient-space endpoints and finite segment length.
2. For each supplied region, use the shared internal `region-partition.ts`
   helper extracted from TASK-039 without changing its numerical semantics.
   Convert contacts to dominant-axis t, validate points, sort and deduplicate
   exactly, then classify the midpoint of every open geometric interval.
3. Reject any finite boundary-following interval explicitly. No arbitrary side
   or unique crossing point is selected for such a traversal.
4. Union all per-region knots by exact t equality. Memberships in each refined
   interval follow from the already-classified constant per-region cells. This
   is actual region state, not an assumed alternation of raw intersections.
5. Overlay BoundaryQuery results, and emit a transition only for occupancy
   changes or genuine BoundaryCrossing results. Coalesce adjacent unchanged
   spans around isolated tangencies or redundant contacts.

The finite partition adapter contract establishes constant classification
between its contacts. No fixed-step sampling, offset probing, nearest-structure
query, renderer triangles or normals are used. An isolated tangent point is not
an interior traversal and is intentionally omitted; coalesced spans describe
open-cell occupancy, not a point-membership claim at such contacts.

Only exactly equal t values form a shared knot. Different t values are never
epsilon-clustered or treated as zero thickness. The existing
`boundaryIntersectionConsistencyTolerance` (Length, 1e-7 mm) only validates
roundoff perpendicular to the segment; it is not a thickness threshold, side
classification tolerance, or medical accuracy claim. Per-region intervals with
no resolvable midpoint raise the existing `BoundaryQueryFailure` instead of
inventing state. Arithmetic and adapter numerical limits remain explicit.

## Coincidence and determinism

A shared knot represents simultaneous changes, such as skin ending and soft
tissue beginning at one position. It creates no zero-length span and assigns
no physical precedence within the group. Memberships and entered/exited sets
sort by regionId using locale-independent code-unit string comparison.
Boundary crossings retain TASK-039's sort: boundaryId, regionId, StructureId,
direction within a shared t. These are serialization tie rules only.

Input region order, boundary binding order, membership-role order and duplicate
hit enumeration order cannot change successful serialized output. Metadata and
results are frozen snapshots; adapters remain caller-owned and must not mutate
while a query executes. Reversal recomputes distances from the new start and
reverses occupancy changes and boundary directions. IEEE-754 reconstruction may
introduce roundoff under reversal; bit-exact reversal at arbitrary scales is
not claimed. Identical inputs with fixed deterministic adapters are deterministic.

## Endpoints, tangency and zero length

- Starts inside: first span records that membership without fabricated entry.
- Ends inside: last span records that membership without fabricated exit.
- Starts/ends exactly on a surface: the first/last open interval describes its
  actual side. No transition or boundary crossing is emitted at t=0 or t=1.
  Genuine interior crossings still appear.
- Isolated tangency with unchanged occupancy: no penetration transition or lumen
  span. A raw contact is not promoted to a medically meaningful crossing.
- Finite boundary overlap: `PenetrationPathFailure`, even when that region has
  no authored BoundaryEntity. BoundaryQuery itself retains its established
  behavior of omitting crossings around boundary intervals.
- Zero length: frozen empty array, no geometry calls and no point snapshot.
  Invalid endpoints still fail. A non-zero segment with no supplied regions
  returns one outside span.

Splitting trajectories at an exact boundary does not synthesize cross-call
continuity. This query has no history; later Interaction owns that concern.

## Fixture acceptance and limitations

The development vein trajectory `(0,-10,-5)` to `(0,-10,20)` yields outside,
skin, soft tissue, a vein-wall entry knot, simultaneous soft tissue and venous
lumen occupancy, a vein-wall exit knot, and soft tissue. Fixture geometry is
unchanged and not Boolean-subtracted. An arterial trajectory preserves arterial
classification with no success, safety or complication judgment.

No vessel-wall thickness is invented. A future validated finite-thickness wall
region can supply an ordinary occupancy binding and explicit boundaries. This
model has no vessel-specific branching and can retain pleural, dural,
pericardial or fascial boundary identities in the same crossing collection.

TASK-039 still associates one BoundaryEntity with the **complete surface** of a
region. Partial surfaces with different medical identities remain unsupported
by that input bridge. The path result does not deepen that assumption; future
boundary authoring can extend the bridge without changing spans or coincident
crossing groups. Medical boundary bindings and validated assets remain future
work. Complete contact enumeration and correct classification are adapter
obligations; software tests cannot certify anatomical truth or arbitrary
third-party adapter completeness.

No persistent schemas, anatomy/patient ownership, package-boundary enforcement,
medical state, renderer, events, Interaction, procedures or TASK-043+ are changed.
