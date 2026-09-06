import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { performance } from 'node:perf_hooks';
import { entityId, structureId } from '../packages/core/dist/index.js';
import { patientSpacePoint as p } from '../packages/math/dist/index.js';
import {
  AxisAlignedBoxSpatialAdapter as Box,
  SpatialQueryService,
  XAxisCylinderSpatialAdapter as Cylinder,
  patientSpaceSegment,
  spatialRegionId,
} from '../packages/spatial/dist/index.js';
import {
  millimetres as mm,
  toMillimetres,
} from '../packages/units/dist/index.js';

const DEFAULT_ITERATIONS = 20_000;

const finitePositiveInteger = (value, fallback) => {
  const parsed = Number.parseInt(value ?? '', 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

const memorySnapshot = () => {
  const value = process.memoryUsage();
  return {
    rssBytes: value.rss,
    heapTotalBytes: value.heapTotal,
    heapUsedBytes: value.heapUsed,
    externalBytes: value.external,
    arrayBuffersBytes: value.arrayBuffers,
  };
};

const measure = (iterations, operation) => {
  const warmup = Math.min(1_000, iterations);
  let checksum = 0;
  for (let i = 0; i < warmup; i += 1) checksum += operation(i);

  const started = performance.now();
  for (let i = 0; i < iterations; i += 1) checksum += operation(i);
  const elapsedMilliseconds = performance.now() - started;
  return {
    iterations,
    elapsedMilliseconds,
    queriesPerSecond: (iterations * 1000) / elapsedMilliseconds,
    checksum,
  };
};

const createFixtureService = async () => {
  const fixture = JSON.parse(
    await readFile('fixtures/anatomy/synthetic-anatomy-v1.json', 'utf8'),
  );
  const identities = [
    ['region.skin', 'structure.skin', ['tissue']],
    ['region.soft', 'structure.soft', ['tissue']],
    ['region.vein', 'structure.vein', ['lumen']],
    ['region.artery', 'structure.artery', ['lumen']],
  ];
  const regions = fixture.entities.map((entity, index) => {
    const geometry = entity.geometry;
    return {
      regionId: spatialRegionId(identities[index][0]),
      structureId: structureId(identities[index][1]),
      canonicalEntityId: entityId(entity.id),
      name: entity.name,
      membershipRoles: identities[index][2],
      vascularLumenKind: entity.vascularLumenKind,
      representation:
        geometry.shape === 'slab'
          ? new Box({
              center: p(...geometry.centerMm),
              size: geometry.sizeMm.map(mm),
            })
          : new Cylinder({
              center: p(...geometry.centerMm),
              radius: mm(geometry.radiusMm),
              length: mm(geometry.lengthMm),
            }),
    };
  });
  const boundary = (region, id) => ({
    regionId: region.regionId,
    boundary: {
      id: entityId(id),
      name: 'Development fixture boundary',
      separates: ['provisional-a', 'provisional-b'],
      provenance: fixture.provenance,
      accuracy: {},
      validation: { level: 'V0', notes: 'Software testing only' },
    },
  });
  const boundaries = [
    boundary(regions[2], 'boundary.vein-wall'),
    boundary(regions[3], 'boundary.artery-wall'),
  ];
  return {
    fixture,
    regions,
    boundaries,
    service: new SpatialQueryService({ regions, boundaries }),
  };
};

export const runSpatialPerformanceBaseline = async (
  requestedIterations = process.env.SPATIAL_BENCH_ITERATIONS,
) => {
  const baseIterations = finitePositiveInteger(
    requestedIterations,
    DEFAULT_ITERATIONS,
  );
  const memoryBeforeSetup = memorySnapshot();
  const { fixture, regions, boundaries, service } =
    await createFixtureService();
  const memoryAfterSetup = memorySnapshot();

  const pointSamples = [
    p(0, 0, 0),
    p(0, -10, 10),
    p(0, 10, 15),
    p(100, 100, 100),
  ];
  const segmentSamples = [
    patientSpaceSegment(p(0, -10, -5), p(0, -10, 20)),
    patientSpaceSegment(p(0, 10, -5), p(0, 10, 25)),
    patientSpaceSegment(p(0, 30, -5), p(0, 30, 20)),
  ];
  const distanceSamples = [
    [p(0, -10, 20), structureId('structure.vein')],
    [p(0, 10, 25), structureId('structure.artery')],
    [p(0, 0, -6), structureId('structure.skin')],
  ];

  const point = measure(baseIterations, (index) => {
    const result = service.queryPoint(
      pointSamples[index % pointSamples.length],
    );
    return result.structures.length + result.lumens.length;
  });
  const segmentIterations = Math.max(1, Math.floor(baseIterations / 5));
  const segment = measure(
    segmentIterations,
    (index) =>
      service.querySegment(segmentSamples[index % segmentSamples.length])
        .length,
  );
  const distance = measure(baseIterations, (index) => {
    const [pointValue, target] =
      distanceSamples[index % distanceSamples.length];
    return toMillimetres(service.distanceTo(pointValue, target).distance);
  });
  const memoryAfterQueries = memorySnapshot();

  return {
    schemaVersion: 1,
    task: 'TASK-044',
    environment: {
      node: process.version,
      platform: process.platform,
      arch: process.arch,
    },
    fixtureComplexity: {
      fixtureVersion: fixture.fixtureVersion,
      entityCount: fixture.entities.length,
      regionCount: regions.length,
      boundaryBindingCount: boundaries.length,
      primitiveCounts: fixture.entities.reduce((counts, entity) => {
        const shape = entity.geometry.shape;
        counts[shape] = (counts[shape] ?? 0) + 1;
        return counts;
      }, {}),
      indexStrategy: 'linear AABB candidate scan',
    },
    throughput: {
      queryPoint: point,
      querySegment: segment,
      distanceTo: distance,
    },
    memory: {
      beforeSetup: memoryBeforeSetup,
      afterSetup: memoryAfterSetup,
      afterQueries: memoryAfterQueries,
      setupHeapUsedDeltaBytes:
        memoryAfterSetup.heapUsedBytes - memoryBeforeSetup.heapUsedBytes,
      queryHeapUsedDeltaBytes:
        memoryAfterQueries.heapUsedBytes - memoryAfterSetup.heapUsedBytes,
    },
    notes: [
      'Development fixture only; no medical performance claim.',
      'No throughput or memory threshold is enforced.',
      'Memory is process-level and depends on garbage collection and runner state.',
    ],
  };
};

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  const baseline = await runSpatialPerformanceBaseline();
  console.log(JSON.stringify(baseline, null, 2));
}
