import type { StructureId } from '@procedural-human/core';
import type { PatientSpacePoint } from '@procedural-human/math';
import type { FlowRate, Pressure, Velocity } from '@procedural-human/units';

export interface PhysiologyProvider {
  pressureAt(
    structureId: StructureId,
    position: PatientSpacePoint,
  ): Pressure | null;
  velocityAt(
    structureId: StructureId,
    position: PatientSpacePoint,
  ): Velocity | null;
  flowFor(structureId: StructureId): FlowRate | null;
  cardiacPhase(): number | null;
  respiratoryPhase(): number | null;
  complianceFor(structureId: StructureId): number | null;
}

export class StaticUnavailablePhysiology implements PhysiologyProvider {
  pressureAt(): Pressure | null {
    return null;
  }

  velocityAt(): Velocity | null {
    return null;
  }

  flowFor(): FlowRate | null {
    return null;
  }

  cardiacPhase(): number | null {
    return null;
  }

  respiratoryPhase(): number | null {
    return null;
  }

  complianceFor(): number | null {
    return null;
  }
}
