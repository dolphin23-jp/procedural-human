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
];

const ajv = new Ajv2020({ allErrors: true, strict: true });
const validators = new Map();

for (const [name, schemaPath] of contracts) {
  const schema = JSON.parse(await fs.readFile(path.join(root, schemaPath), 'utf8'));
  if (!schemaPath.endsWith('.v1.schema.json') || !schema.$id?.endsWith('/v1')) {
    throw new Error(`Schema version mismatch: ${schemaPath}`);
  }
  validators.set(name, ajv.compile(schema));
}

let failures = 0;

for (const [name] of contracts) {
  const validate = validators.get(name);
  for (const expectation of ['valid', 'invalid']) {
    const fixturePath = path.join(root, 'fixtures', 'schemas', `${name}.v1.${expectation}.json`);
    const data = JSON.parse(await fs.readFile(fixturePath, 'utf8'));
    const actualValid = validate(data);
    const expectedValid = expectation === 'valid';

    if (actualValid !== expectedValid) {
      failures += 1;
      const details = validate.errors ? JSON.stringify(validate.errors, null, 2) : 'no validation errors';
      console.error(`${path.relative(root, fixturePath)} expected ${expectation} but validation returned ${actualValid}.\n${details}`);
    }
  }
}

if (failures > 0) {
  process.exitCode = 1;
} else {
  console.log(`Validated ${contracts.length} schema versions and ${contracts.length * 2} fixtures.`);
}
