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
    `Validated ${contracts.length + authoringContracts.length} schema versions, ${contracts.length * 2} fixtures, and 2 authoring records.`,
  );
