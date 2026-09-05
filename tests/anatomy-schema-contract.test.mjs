import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';

const schemaPath = fileURLToPath(
  new URL(
    '../schemas/anatomy/anatomical-entity.v1.schema.json',
    import.meta.url,
  ),
);
const validFixturePath = fileURLToPath(
  new URL(
    '../fixtures/schemas/anatomical-entity.v1.valid.json',
    import.meta.url,
  ),
);

const schema = JSON.parse(await fs.readFile(schemaPath, 'utf8'));
const validFixture = JSON.parse(await fs.readFile(validFixturePath, 'utf8'));
const validate = new Ajv2020({ allErrors: true, strict: true }).compile(schema);

const cloneFixture = () => structuredClone(validFixture);

test('anatomical entity v1 accepts the current bounded relationship and representation kinds', () => {
  assert.equal(validate(cloneFixture()), true);
});

test('anatomical entity v1 rejects an unassigned relationship type', () => {
  const candidate = cloneFixture();
  candidate.relationships[0].type = 'supplies';

  assert.equal(validate(candidate), false);
  assert.match(JSON.stringify(validate.errors), /enum/);
});

test('anatomical entity v1 rejects an unassigned representation kind', () => {
  const candidate = cloneFixture();
  candidate.representations[0].kind = 'signedDistanceField';

  assert.equal(validate(candidate), false);
  assert.match(JSON.stringify(validate.errors), /enum/);
});
