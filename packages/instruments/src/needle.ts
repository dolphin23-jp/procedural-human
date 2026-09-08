import { toMillimetres, type Length } from '@procedural-human/units';
import {
  createInstrumentDefinition,
  type InstrumentDefinition,
  type InstrumentDefinitionId,
  type InstrumentPart,
  type InstrumentPartId,
} from './base.js';

export interface NeedleFunctionalParts {
  readonly tip: InstrumentPartId;
  readonly bevel: InstrumentPartId;
  readonly shaft: InstrumentPartId;
  readonly lumen: InstrumentPartId;
}

export interface NeedleGeometry {
  readonly shaftLength: Length;
  readonly bevelLength: Length;
  readonly outerDiameter: Length;
  readonly lumenDiameter: Length;
}

export interface NeedleDefinition extends InstrumentDefinition {
  readonly kind: 'needle';
  readonly functionalParts: NeedleFunctionalParts;
  readonly geometry: NeedleGeometry;
}

function positiveLength(value: Length, label: string): Length {
  const millimetres = toMillimetres(value);
  if (!Number.isFinite(millimetres) || millimetres <= 0) {
    throw new RangeError(`${label} must be finite and greater than zero.`);
  }
  return value;
}

function copyFunctionalParts(
  parts: NeedleFunctionalParts,
  definition: InstrumentDefinition,
): NeedleFunctionalParts {
  const values = [parts.tip, parts.bevel, parts.shaft, parts.lumen];
  if (new Set(values).size !== values.length) {
    throw new RangeError('Needle functional part IDs must be distinct.');
  }
  const known = new Set(definition.parts.map((part) => part.id));
  for (const id of values) {
    if (!known.has(id)) {
      throw new RangeError(
        `Needle functional part ${id} is not in the instrument definition.`,
      );
    }
  }
  return Object.freeze({
    tip: parts.tip,
    bevel: parts.bevel,
    shaft: parts.shaft,
    lumen: parts.lumen,
  });
}

function copyGeometry(geometry: NeedleGeometry): NeedleGeometry {
  const shaftLength = positiveLength(
    geometry.shaftLength,
    'Needle shaft length',
  );
  const bevelLength = positiveLength(
    geometry.bevelLength,
    'Needle bevel length',
  );
  const outerDiameter = positiveLength(
    geometry.outerDiameter,
    'Needle outer diameter',
  );
  const lumenDiameter = positiveLength(
    geometry.lumenDiameter,
    'Needle lumen diameter',
  );

  if (toMillimetres(bevelLength) > toMillimetres(shaftLength)) {
    throw new RangeError('Needle bevel length must not exceed shaft length.');
  }
  if (toMillimetres(lumenDiameter) >= toMillimetres(outerDiameter)) {
    throw new RangeError(
      'Needle lumen diameter must be smaller than outer diameter.',
    );
  }

  return Object.freeze({
    shaftLength,
    bevelLength,
    outerDiameter,
    lumenDiameter,
  });
}

export function createNeedleDefinition(input: {
  readonly id: InstrumentDefinitionId;
  readonly name: string;
  readonly parts: readonly InstrumentPart[];
  readonly functionalParts: NeedleFunctionalParts;
  readonly geometry: NeedleGeometry;
}): NeedleDefinition {
  const definition = createInstrumentDefinition({
    id: input.id,
    name: input.name,
    parts: input.parts,
  });
  return Object.freeze({
    ...definition,
    kind: 'needle',
    functionalParts: copyFunctionalParts(input.functionalParts, definition),
    geometry: copyGeometry(input.geometry),
  });
}
