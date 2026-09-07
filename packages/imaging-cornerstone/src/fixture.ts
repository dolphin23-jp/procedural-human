import { createVolumeImagingFrame } from '@procedural-human/imaging-core';
import {
  patientSpaceDirection,
  patientSpacePoint,
} from '@procedural-human/math';
import { millimetres } from '@procedural-human/units';
import {
  validateImagingVolumeSource,
  type ImagingVolumeSource,
} from './source.js';

/**
 * Small deterministic calibration phantom for TASK-058/059.
 * It is a software development fixture, not anatomy and not synthetic CT.
 */
export function createSyntheticAxialVolumeFixture(): ImagingVolumeSource {
  const dimensions = { i: 48, j: 48, k: 9 };
  const frame = createVolumeImagingFrame({
    kind: 'volume-3d',
    indexConvention: 'zero-based-sample-centers',
    origin: patientSpacePoint(-18.8, -18.8, -8),
    directionI: patientSpaceDirection(1, 0, 0),
    directionJ: patientSpaceDirection(0, 1, 0),
    directionK: patientSpaceDirection(0, 0, 1),
    handedness: 'right',
    spacing: {
      i: millimetres(0.8),
      j: millimetres(0.8),
      k: millimetres(2),
    },
    dimensions,
  });

  const samples = new Uint16Array(dimensions.i * dimensions.j * dimensions.k);
  let offset = 0;
  for (let k = 0; k < dimensions.k; k += 1) {
    for (let j = 0; j < dimensions.j; j += 1) {
      for (let i = 0; i < dimensions.i; i += 1) {
        const checker = (Math.floor(i / 6) + Math.floor(j / 6) + k) % 2;
        const diagonal = Math.abs(i - j) <= 1 ? 260 : 0;
        const cross = Math.abs(i - 24) <= 1 || Math.abs(j - 24) <= 1 ? 180 : 0;
        samples[offset] = 120 + checker * 360 + k * 28 + diagonal + cross;
        offset += 1;
      }
    }
  }

  return validateImagingVolumeSource({
    id: 'fixture.synthetic-axial-calibration-v1',
    frameOfReferenceUID: 'procedural-human.fixture.synthetic-axial-v1',
    frame,
    scalarData: samples,
    display: {
      windowCenter: 520,
      windowWidth: 1040,
    },
    provenance: {
      sourceClass: 'development-fixture',
      sourceIdentifier:
        'packages/imaging-cornerstone/src/fixture.ts:createSyntheticAxialVolumeFixture',
      validationLevel: 'V0',
      notes:
        'Deterministic software calibration phantom only; no medical or anatomical validation.',
    },
  });
}
