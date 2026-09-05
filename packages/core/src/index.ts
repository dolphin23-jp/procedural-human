declare const identifierBrand: unique symbol;
declare const versionBrand: unique symbol;
declare const contentHashBrand: unique symbol;

type Identifier<Kind extends string> = string & {
  readonly [identifierBrand]: Kind;
};

export type EntityId = Identifier<'EntityId'>;
export type StructureId = Identifier<'StructureId'>;
export type PatientId = Identifier<'PatientId'>;
export type AssetId = Identifier<'AssetId'>;
export type ProcedureId = Identifier<'ProcedureId'>;
export type CaseId = Identifier<'CaseId'>;
export type SessionId = Identifier<'SessionId'>;

export type Version = string & { readonly [versionBrand]: 'Version' };
export type SchemaVersion = string & {
  readonly [versionBrand]: 'SchemaVersion';
};
export type ContentHash = string & {
  readonly [contentHashBrand]: 'ContentHash';
};

export const entityId = (value: string): EntityId => value as EntityId;
export const structureId = (value: string): StructureId => value as StructureId;
export const patientId = (value: string): PatientId => value as PatientId;
export const assetId = (value: string): AssetId => value as AssetId;
export const procedureId = (value: string): ProcedureId => value as ProcedureId;
export const caseId = (value: string): CaseId => value as CaseId;
export const sessionId = (value: string): SessionId => value as SessionId;

export const version = (value: string): Version => value as Version;
export const schemaVersion = (value: string): SchemaVersion =>
  value as SchemaVersion;
export const contentHash = (value: string): ContentHash => value as ContentHash;
