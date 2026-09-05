import assert from 'node:assert/strict';
import test from 'node:test';

import { patientSpacePoint } from '../packages/math/dist/index.js';
import { patientSpaceSegment } from '../packages/spatial/dist/index.js';

test('patient-space segment preserves explicit patient-space endpoints', () => {
  const start = patientSpacePoint(1, 2, 3);
  const end = patientSpacePoint(4, 5, 6);
  const segment = patientSpaceSegment(start, end);

  assert.equal(segment.start.space, 'patient');
  assert.equal(segment.end.space, 'patient');
  assert.deepEqual(segment, { start, end });
  assert.equal(Object.isFrozen(segment), true);
});
