declare const quantityBrand: unique symbol;

type Quantity<Kind extends string> = number & {
  readonly [quantityBrand]: Kind;
};

export type Length = Quantity<'LengthMillimetres'>;
export type Time = Quantity<'TimeSeconds'>;
export type Angle = Quantity<'AngleRadians'>;
export type Pressure = Quantity<'PressurePascals'>;
export type Velocity = Quantity<'VelocityMillimetresPerSecond'>;
export type FlowRate = Quantity<'FlowRateCubicMillimetresPerSecond'>;
export type Volume = Quantity<'VolumeCubicMillimetres'>;
export type Force = Quantity<'ForceNewtons'>;

const cast = <T extends number>(value: number): T => value as T;

export const millimetres = (value: number): Length => cast<Length>(value);
export const centimetres = (value: number): Length => cast<Length>(value * 10);
export const metres = (value: number): Length => cast<Length>(value * 1_000);
export const toMillimetres = (value: Length): number => value;
export const toCentimetres = (value: Length): number => value / 10;
export const toMetres = (value: Length): number => value / 1_000;

export const seconds = (value: number): Time => cast<Time>(value);
export const milliseconds = (value: number): Time => cast<Time>(value / 1_000);
export const minutes = (value: number): Time => cast<Time>(value * 60);
export const toSeconds = (value: Time): number => value;
export const toMilliseconds = (value: Time): number => value * 1_000;
export const toMinutes = (value: Time): number => value / 60;

export const radians = (value: number): Angle => cast<Angle>(value);
export const degrees = (value: number): Angle =>
  cast<Angle>((value * Math.PI) / 180);
export const toRadians = (value: Angle): number => value;
export const toDegrees = (value: Angle): number => (value * 180) / Math.PI;

const PASCALS_PER_MMHG = 133.322_387_415;
export const pascals = (value: number): Pressure => cast<Pressure>(value);
export const kilopascals = (value: number): Pressure =>
  cast<Pressure>(value * 1_000);
export const millimetresOfMercury = (value: number): Pressure =>
  cast<Pressure>(value * PASCALS_PER_MMHG);
export const toPascals = (value: Pressure): number => value;
export const toKilopascals = (value: Pressure): number => value / 1_000;
export const toMillimetresOfMercury = (value: Pressure): number =>
  value / PASCALS_PER_MMHG;

export const millimetresPerSecond = (value: number): Velocity =>
  cast<Velocity>(value);
export const metresPerSecond = (value: number): Velocity =>
  cast<Velocity>(value * 1_000);
export const toMillimetresPerSecond = (value: Velocity): number => value;
export const toMetresPerSecond = (value: Velocity): number => value / 1_000;

export const cubicMillimetresPerSecond = (value: number): FlowRate =>
  cast<FlowRate>(value);
export const millilitresPerSecond = (value: number): FlowRate =>
  cast<FlowRate>(value * 1_000);
export const litresPerMinute = (value: number): FlowRate =>
  cast<FlowRate>((value * 1_000_000) / 60);
export const toCubicMillimetresPerSecond = (value: FlowRate): number => value;
export const toMillilitresPerSecond = (value: FlowRate): number =>
  value / 1_000;
export const toLitresPerMinute = (value: FlowRate): number =>
  (value * 60) / 1_000_000;

export const cubicMillimetres = (value: number): Volume => cast<Volume>(value);
export const millilitres = (value: number): Volume =>
  cast<Volume>(value * 1_000);
export const litres = (value: number): Volume =>
  cast<Volume>(value * 1_000_000);
export const toCubicMillimetres = (value: Volume): number => value;
export const toMillilitres = (value: Volume): number => value / 1_000;
export const toLitres = (value: Volume): number => value / 1_000_000;

export const newtons = (value: number): Force => cast<Force>(value);
export const millinewtons = (value: number): Force =>
  cast<Force>(value / 1_000);
export const toNewtons = (value: Force): number => value;
export const toMillinewtons = (value: Force): number => value * 1_000;
