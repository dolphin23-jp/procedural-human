import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const forbiddenWorkspaceEdges = new Map([
  ['patient', new Set(['procedures', 'spatial'])],
  ['spatial', new Set(['interaction'])],
  ['instruments', new Set(['procedures'])],
]);

const anatomyAllowedWorkspaceTargets = new Set(['core', 'units', 'math']);

const sourceExtensions = new Set([
  '.js',
  '.jsx',
  '.mjs',
  '.cjs',
  '.ts',
  '.tsx',
]);

function ownerFor(relativePath) {
  const parts = relativePath.split(path.sep);

  if (parts[0] === 'packages' && parts[1]) {
    return { kind: 'package', name: parts[1] };
  }

  if (parts[0] === 'apps' && parts[1]) {
    return { kind: 'app', name: parts[1] };
  }

  return null;
}

function workspacePackageFromSpecifier(specifier) {
  const match = /^@procedural-human\/([^/]+)(?:\/.*)?$/.exec(specifier);
  return match?.[1] ?? null;
}

function extractImportSpecifiers(source) {
  const specifiers = new Set();
  const patterns = [
    /(?:import|export)\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]/g,
    /import\(\s*['"]([^'"]+)['"]\s*\)/g,
    /require\(\s*['"]([^'"]+)['"]\s*\)/g,
  ];

  for (const pattern of patterns) {
    for (const match of source.matchAll(pattern)) {
      if (match[1]) {
        specifiers.add(match[1]);
      }
    }
  }

  return [...specifiers];
}

function externalBoundaryViolation(owner, specifier) {
  const isReact =
    specifier === 'react' ||
    specifier.startsWith('react/') ||
    specifier === 'react-dom' ||
    specifier.startsWith('react-dom/');
  if (
    isReact &&
    !(owner.kind === 'app' && owner.name === 'web') &&
    !(owner.kind === 'package' && owner.name === 'ui')
  ) {
    return 'React may only be imported by apps/web or packages/ui';
  }

  const isThree = specifier === 'three' || specifier.startsWith('three/');
  if (
    isThree &&
    !(owner.kind === 'package' && owner.name === 'rendering-three')
  ) {
    return 'Three.js may only be imported by packages/rendering-three';
  }

  const isCornerstone = specifier.startsWith('@cornerstonejs/');
  if (
    isCornerstone &&
    !(owner.kind === 'package' && owner.name === 'imaging-cornerstone')
  ) {
    return 'Cornerstone may only be imported by packages/imaging-cornerstone';
  }

  return null;
}

async function collectSourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true }).catch(
    (error) => {
      if (error.code === 'ENOENT') {
        return [];
      }
      throw error;
    },
  );
  const files = [];

  for (const entry of entries) {
    if (entry.name === 'node_modules' || entry.name === 'dist') {
      continue;
    }

    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectSourceFiles(fullPath)));
    } else if (sourceExtensions.has(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }

  return files;
}

export async function checkPackageBoundaries(rootDir) {
  const roots = [path.join(rootDir, 'packages'), path.join(rootDir, 'apps')];
  const sourceFiles = (await Promise.all(roots.map(collectSourceFiles))).flat();
  const violations = [];

  for (const filePath of sourceFiles) {
    const relativePath = path.relative(rootDir, filePath);
    const owner = ownerFor(relativePath);
    if (!owner) {
      continue;
    }

    const source = await readFile(filePath, 'utf8');
    for (const specifier of extractImportSpecifiers(source)) {
      const workspaceTarget = workspacePackageFromSpecifier(specifier);
      if (
        owner.kind === 'package' &&
        owner.name === 'anatomy' &&
        workspaceTarget &&
        !anatomyAllowedWorkspaceTargets.has(workspaceTarget)
      ) {
        violations.push(
          `${relativePath}: @procedural-human/anatomy may only depend on @procedural-human/core, @procedural-human/units, or @procedural-human/math`,
        );
      } else if (
        owner.kind === 'package' &&
        workspaceTarget &&
        forbiddenWorkspaceEdges.get(owner.name)?.has(workspaceTarget)
      ) {
        violations.push(
          `${relativePath}: @procedural-human/${owner.name} must not depend on @procedural-human/${workspaceTarget}`,
        );
      }

      const externalViolation = externalBoundaryViolation(owner, specifier);
      if (externalViolation) {
        violations.push(`${relativePath}: ${externalViolation} (${specifier})`);
      }
    }
  }

  return violations.sort();
}

async function main() {
  const rootDir = process.cwd();
  const violations = await checkPackageBoundaries(rootDir);

  if (violations.length > 0) {
    console.error('Package boundary violations found:');
    for (const violation of violations) {
      console.error(`- ${violation}`);
    }
    process.exitCode = 1;
    return;
  }

  console.log('Package boundary check passed.');
}

const isDirectRun =
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isDirectRun) {
  await main();
}
