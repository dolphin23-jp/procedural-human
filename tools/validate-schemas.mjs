import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const contracts = [
  ['anatomical-entity', 'schemas/anatomy/anatomical-entity.v1.schema.json'],
  ['asset-manifest', 'schemas/assets/asset-manifest.v1.schema.json'],
  ['patient-manifest', 'schemas/patient/patient-manifest.v1.schema.json'],
  ['simulation-event', 'schemas/events/simulation-event.v1.schema.json'],
  [
    'procedure-definition',
    'schemas/procedures/procedure-definition.v1.schema.json',
  ],
  ['case-manifest', 'schemas/cases/case-manifest.v1.schema.json'],
  ['session-record', 'schemas/sessions/session-record.v1.schema.json'],
];

const authoringContracts = [
  [
    'vhf-source-release-receipt',
    'schemas/assets/vhf-source-release-receipt.v1.schema.json',
    null,
  ],
  [
    'vhf-source-storage',
    'schemas/assets/vhf-source-storage.v1.schema.json',
    null,
  ],
  [
    'vhf-whole-body-inventory',
    'schemas/assets/vhf-whole-body-inventory.v1.schema.json',
    'authoring/source-archives/vhf-whole-body-inventory-20260910.json',
  ],
  [
    'm8v-radiological-source-inventory',
    'schemas/assets/m8v-radiological-source-inventory.v1.schema.json',
    'authoring/outputs/m8v-v01-radiological-source-inventory-20260910.json',
  ],
  [
    'm8v-ct-cryo-registration-scaffold',
    'schemas/assets/m8v-ct-cryo-registration-scaffold.v1.schema.json',
    'authoring/outputs/m8v-v02-ct-cryo-registration-scaffold-20260910.json',
  ],
  [
    'm8v-upper-extremity-landmark-graph',
    'schemas/assets/m8v-upper-extremity-landmark-graph.v1.schema.json',
    'authoring/outputs/m8v-v03-upper-extremity-landmark-graph-20260910.json',
  ],
  [
    'm8v-candidate-vessel-track-graph',
    'schemas/assets/m8v-candidate-vessel-track-graph.v1.schema.json',
    'authoring/outputs/m8v-v04-candidate-vessel-track-graph-20260910.json',
  ],
  [
    'm8v-radial-artery-identity-evidence',
    'schemas/assets/m8v-radial-artery-identity-evidence.v1.schema.json',
    'authoring/outputs/m8v-v05-radial-artery-identity-evidence-20260911.json',
  ],
  [
    'm8v-superficial-venous-network-evidence',
    'schemas/assets/m8v-superficial-venous-network-evidence.v1.schema.json',
    'authoring/outputs/m8v-v06-superficial-venous-network-evidence-20260911.json',
  ],
  [
    'm8v-multimodal-review-surface',
    'schemas/assets/m8v-multimodal-review-surface.v1.schema.json',
    'authoring/outputs/m8v-v07-multimodal-review-surface-20260911.json',
  ],
  ['vhf-source-chunk', 'schemas/assets/vhf-source-chunk.v1.schema.json', null],
  [
    'vhf-source-archive-index',
    'schemas/assets/vhf-source-archive-index.v1.schema.json',
    null,
  ],
  [
    'vhf-source-region',
    'schemas/assets/vhf-source-region.v1.schema.json',
    null,
  ],
  [
    'source-archive-record',
    'schemas/assets/source-archive-record.v1.schema.json',
    'authoring/source-archives/visible-human-female.json',
  ],
  [
    'authoring-roi',
    'schemas/assets/authoring-roi.v1.schema.json',
    'authoring/rois/mvp0-left-distal-forearm-wrist.json',
  ],
  [
    'draft-segmentation-manifest',
    'schemas/assets/draft-segmentation-manifest.v1.schema.json',
    null,
  ],
  [
    'vascular-feasibility-report',
    'schemas/assets/vascular-feasibility-report.v1.schema.json',
    null,
  ],
  [
    'manual-edit-provenance',
    'schemas/assets/manual-edit-provenance.v1.schema.json',
    'authoring/manual-inputs/a06-manual-correction-status-20260910.json',
  ],
  [
    'a06-human-review-session',
    'schemas/assets/a06-human-review-session.v1.schema.json',
    null,
  ],
  [
    'a06-human-review-receipt',
    'schemas/assets/a06-human-review-receipt.v1.schema.json',
    'authoring/manual-inputs/a06-human-review-receipt-20260910.json',
  ],
  [
    'a06-bone-candidate-provenance',
    'schemas/assets/a06-bone-candidate-provenance.v1.schema.json',
    'authoring/outputs/a06-support-aware-radius-ulna-provenance-20260909.json',
  ],
  [
    'a06-source-evidence-vessel-candidate-report',
    'schemas/assets/a06-source-evidence-vessel-candidate-report.v1.schema.json',
    null,
  ],
  [
    'a06-vessel-candidate-provenance',
    'schemas/assets/a06-vessel-candidate-provenance.v1.schema.json',
    'authoring/outputs/a06-source-evidence-vessel-provenance-20260909.json',
  ],
  [
    'a06-ulnar-continuous-segment-report',
    'schemas/assets/a06-ulnar-continuous-segment-report.v1.schema.json',
    null,
  ],
  [
    'a08-source-stack-centerline-candidate',
    'schemas/assets/a08-source-stack-centerline-candidate.v1.schema.json',
    null,
  ],
  [
    'a06-a08-ulnar-continuous-provenance',
    'schemas/assets/a06-a08-ulnar-continuous-provenance.v1.schema.json',
    'authoring/outputs/a06-a08-ulnar-continuous-provenance-20260909.json',
  ],
  [
    'a09-boundary-lumen-candidate',
    'schemas/assets/a09-boundary-lumen-candidate.v1.schema.json',
    null,
  ],
  [
    'a08-a09-ulnar-topology-provenance',
    'schemas/assets/a08-a09-ulnar-topology-provenance.v1.schema.json',
    'authoring/outputs/a08-a09-ulnar-topology-provenance-20260909.json',
  ],
  [
    'a07-atlas-fallback-provenance',
    'schemas/assets/a07-atlas-fallback-provenance.v1.schema.json',
    'authoring/outputs/a07-atlas-fallback-provenance-20260910.json',
  ],
  [
    'as06-same-subject-continuity-provenance',
    'schemas/assets/as06-same-subject-continuity-provenance.v1.schema.json',
    'authoring/outputs/as06-same-subject-continuity-provenance-20260910.json',
  ],
  [
    'as07-continuity-feed-forward',
    'schemas/assets/as07-continuity-feed-forward.v1.schema.json',
    'authoring/outputs/as07-continuity-feed-forward-20260910.json',
  ],
  [
    'semantic-structure-mapping',
    'schemas/assets/semantic-structure-mapping.v1.schema.json',
    'authoring/semantic/a07-semantic-structure-mapping-20260910.json',
  ],
  [
    'vessel-centerline-authoring-report',
    'schemas/assets/vessel-centerline-authoring-report.v1.schema.json',
    'authoring/outputs/a08-vessel-centerline-authoring-report-20260910.json',
  ],
  [
    'boundary-lumen-authoring-report',
    'schemas/assets/boundary-lumen-authoring-report.v1.schema.json',
    'authoring/outputs/a09-boundary-lumen-authoring-report-20260910.json',
  ],
  [
    'medical-master-readiness',
    'schemas/assets/medical-master-readiness.v1.schema.json',
    'authoring/outputs/a10-medical-master-readiness-20260910.json',
  ],
];

const ajv = new Ajv2020({ allErrors: true, strict: true });
const validators = new Map();

for (const [name, schemaPath] of [...contracts, ...authoringContracts]) {
  const schema = JSON.parse(
    await fs.readFile(path.join(root, schemaPath), 'utf8'),
  );
  if (!schemaPath.endsWith('.v1.schema.json') || !schema.$id?.endsWith('/v1')) {
    throw new Error(`Schema version mismatch: ${schemaPath}`);
  }
  validators.set(name, ajv.compile(schema));
}

let failures = 0;
for (const [name] of contracts) {
  const validate = validators.get(name);
  for (const expectation of ['valid', 'invalid']) {
    const fixturePath = path.join(
      root,
      'fixtures',
      'schemas',
      `${name}.v1.${expectation}.json`,
    );
    const data = JSON.parse(await fs.readFile(fixturePath, 'utf8'));
    const actualValid = validate(data);
    const expectedValid = expectation === 'valid';
    if (actualValid !== expectedValid) {
      failures += 1;
      console.error(
        `${path.relative(root, fixturePath)} expected ${expectation} but validation returned ${actualValid}.`,
      );
      if (validate.errors)
        console.error(JSON.stringify(validate.errors, null, 2));
    }
  }
}

for (const [name, , recordPath] of authoringContracts) {
  if (recordPath === null) continue;
  const validate = validators.get(name);
  const data = JSON.parse(
    await fs.readFile(path.join(root, recordPath), 'utf8'),
  );
  if (!validate(data)) {
    failures += 1;
    console.error(`${recordPath} failed ${name} schema validation.`);
    if (validate.errors)
      console.error(JSON.stringify(validate.errors, null, 2));
  }
}

if (failures > 0) process.exitCode = 1;
else
  console.log(
    `Validated ${contracts.length + authoringContracts.length} schema versions, ${contracts.length * 2} fixtures, and ${authoringContracts.filter(([, , recordPath]) => recordPath !== null).length} authoring records.`,
  );
