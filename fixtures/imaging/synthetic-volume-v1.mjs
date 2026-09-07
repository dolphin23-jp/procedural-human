import { assetId, patientId } from '../../packages/core/dist/index.js';
import {
  patientSpaceDirection,
  patientSpacePoint,
} from '../../packages/math/dist/index.js';
import { millimetres } from '../../packages/units/dist/index.js';
import {
  createImagingObservation,
  createVolumeImagingFrame,
} from '../../packages/imaging-core/dist/index.js';

// Analytic non-medical scalar ramp, not CT attenuation or acquired image data.
export const syntheticVolumeProvenance = Object.freeze({
  sourceClass: 'development-fixture',
  sourceIdentifier: 'procedural-human/fixtures/imaging/synthetic-volume-v1.mjs',
  derivationMethod:
    'Deterministic scalar ramp: sample(i,j,k) = i + 10*j + 100*k; i fastest.',
  validation: Object.freeze({
    level: 'V0',
    notes: 'Software coordinate fixture only; no medical validation.',
  }),
  registrationAccuracy: null,
});

export function createSyntheticVolume() {
  const frame = createVolumeImagingFrame({
    kind: 'volume-3d',
    indexConvention: 'zero-based-sample-centers',
    origin: patientSpacePoint(13, -21, 34),
    directionI: patientSpaceDirection(0.6, 0.8, 0),
    directionJ: patientSpaceDirection(-0.48, 0.36, 0.8),
    directionK: patientSpaceDirection(0.64, -0.48, 0.6),
    handedness: 'right',
    spacing: { i: millimetres(0.7), j: millimetres(1.3), k: millimetres(2.5) },
    dimensions: { i: 4, j: 3, k: 3 },
  });
  const samples = [];
  for (let k = 0; k < 3; k++)
    for (let j = 0; j < 3; j++)
      for (let i = 0; i < 4; i++) samples.push(i + 10 * j + 100 * k);
  const observation = createImagingObservation({
    id: 'observation.fixture.synthetic-volume-v1',
    patientId: patientId('patient.fixture.synthetic-anatomy-v1'),
    assetId: assetId('asset.fixture.synthetic-volume-v1'),
    sourceType: 'synthetic',
    registrationStatus: 'registered',
    registrationId: 'registration.fixture.analytic-v1',
    frames: [frame],
  });
  return Object.freeze({
    frame,
    observation,
    provenance: syntheticVolumeProvenance,
    samples: Object.freeze(samples),
  });
}
