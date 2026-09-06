# Spatial performance baseline — TASK-044

## Purpose

TASK-044 establishes a pre-optimization baseline for the deterministic synthetic
fixture. It is measurement infrastructure, not a performance budget and not
permission to change medical geometry.

Run:

```sh
pnpm spatial:baseline
```

The command builds the contracts and prints one JSON document. CI also runs the
same command so the baseline is captured with the Node version and runner platform.

## Measurements

The report contains:

- fixture complexity: entity/region/boundary counts and primitive types
- point-query throughput through `SpatialQueryService.queryPoint`
- ordered-segment-query throughput through `SpatialQueryService.querySegment`
- distance-query throughput through `SpatialQueryService.distanceTo`
- process memory before service construction, after construction, and after query
  loops
- a checksum for each benchmark loop so query results are consumed
- runtime environment information

The default benchmark uses enough iterations to reduce timer noise while remaining
small enough for routine CI. `SPATIAL_BENCH_ITERATIONS` can override the base
iteration count for diagnostics and tests.

## Interpretation

No throughput or memory threshold is enforced in TASK-044. GitHub-hosted runners
and local machines are not comparable performance environments, and
`process.memoryUsage()` is process-level, GC-dependent data. The measurements are
there to make future optimization evidence-based.

Current fixture complexity is intentionally tiny: four primitive regions (skin,
soft tissue, venous lumen, arterial lumen) and two authored vessel-wall boundary
bindings. The current basic point index performs a linear bounding-box candidate
scan. Ordered penetration traverses the finite contact partitions of every supplied
region. TASK-044 does not replace either algorithm with a BVH, cache, GPU path, or
other optimization.

Future performance work should compare against this command while preserving the
same deterministic semantic outputs. Validated Medical Master geometry must never
be altered merely to improve these numbers.
