import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

test('TASK-044 baseline command reports fixture complexity, throughput and memory without thresholds', () => {
  const result = spawnSync(
    process.execPath,
    ['tools/spatial-performance-baseline.mjs'],
    {
      cwd: process.cwd(),
      env: {
        ...process.env,
        SPATIAL_BENCH_ITERATIONS: '200',
      },
      encoding: 'utf8',
    },
  );
  assert.equal(result.status, 0, result.stderr);
  const baseline = JSON.parse(result.stdout);
  assert.equal(baseline.schemaVersion, 1);
  assert.equal(baseline.task, 'TASK-044');
  assert.deepEqual(
    {
      entityCount: baseline.fixtureComplexity.entityCount,
      regionCount: baseline.fixtureComplexity.regionCount,
      boundaryBindingCount: baseline.fixtureComplexity.boundaryBindingCount,
      primitiveCounts: baseline.fixtureComplexity.primitiveCounts,
    },
    {
      entityCount: 4,
      regionCount: 4,
      boundaryBindingCount: 2,
      primitiveCounts: { slab: 2, cylinder: 2 },
    },
  );
  for (const metric of Object.values(baseline.throughput)) {
    assert.ok(metric.iterations > 0);
    assert.ok(Number.isFinite(metric.elapsedMilliseconds));
    assert.ok(metric.elapsedMilliseconds > 0);
    assert.ok(Number.isFinite(metric.queriesPerSecond));
    assert.ok(metric.queriesPerSecond > 0);
    assert.ok(Number.isFinite(metric.checksum));
  }
  for (const snapshot of [
    baseline.memory.beforeSetup,
    baseline.memory.afterSetup,
    baseline.memory.afterQueries,
  ]) {
    assert.ok(snapshot.rssBytes > 0);
    assert.ok(snapshot.heapTotalBytes > 0);
    assert.ok(snapshot.heapUsedBytes > 0);
  }
});
