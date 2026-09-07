import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import test from 'node:test';

// Exercise the dependency in a context with no Node require/module/events/url.
// The Node entry used previously builds successfully but crashes at browser load.
test('Cornerstone vtk XML dependency can initialize and build XML without Node built-ins', () => {
  const adapter = createRequire(
    new URL('../packages/imaging-cornerstone/package.json', import.meta.url),
  );
  const cornerstone = createRequire(adapter.resolve('@cornerstonejs/core'));
  const vtk = createRequire(
    cornerstone.resolve('@kitware/vtk.js/package.json'),
  );
  const browserBundle = vtk.resolve('xmlbuilder2/lib/xmlbuilder2.min.js');
  const context = {};
  runInNewContext(readFileSync(browserBundle, 'utf8'), context, {
    timeout: 5000,
  });
  const xml = context.xmlbuilder2
    .create({ version: '1.0' })
    .ele('calibration')
    .att('k', '7')
    .end();
  assert.match(xml, /<calibration k="7"\/>/);
});
