import { assetId, patientId } from '../../packages/core/src/index';
import {
  ImagePatientTransform,
  ImagePlaneTransform,
  createVolumeImagingFrame,
  type VolumeImagingFrame,
  type ImagingObservation,
  type ImagingSourceType,
} from '../../packages/imaging-core/src/index';
import { ImageRenderCoordinateBridge } from '../../packages/session/src/index';
import {
  imageVoxelCoordinate,
  patientSpacePoint,
  patientSpaceVector,
  renderSpacePoint,
} from '../../packages/math/src/index';

declare const frame: VolumeImagingFrame;
declare const image: ImagePatientTransform;
declare const plane: ImagePlaneTransform;
declare const bridge: ImageRenderCoordinateBridge;
image.voxelToPatient(imageVoxelCoordinate(0.5, 1, 2));
image.patientToVoxel(patientSpacePoint(1, 2, 3));
bridge.renderToVoxel(renderSpacePoint(1, 2, 3));
// @ts-expect-error Render points cannot enter Patient APIs.
image.patientToVoxel(renderSpacePoint(1, 2, 3));
// @ts-expect-error Patient points are not voxel coordinates.
image.voxelToPatient(patientSpacePoint(1, 2, 3));
// @ts-expect-error Tuples cannot enter coordinate APIs.
image.voxelToPatient([1, 2, 3]);
// @ts-expect-error Numbers cannot enter coordinate APIs.
image.voxelToPatient(1);
// @ts-expect-error Untagged indices cannot enter coordinate APIs.
image.voxelToPatient({ i: 1, j: 2, k: 3 });
// @ts-expect-error Physical displacements cannot replace directions.
createVolumeImagingFrame({ ...frame, directionI: patientSpaceVector(1, 0, 0) });
// @ts-expect-error Spacing requires physical Length.
createVolumeImagingFrame({ ...frame, spacing: { i: 1, j: 2, k: 3 } });
// @ts-expect-error A 2D plane inverse uses pixel coordinates, not a 3D voxel.
plane.pixelToPatient(imageVoxelCoordinate(1, 2, 0));
// @ts-expect-error Composition cannot accept patient points as render points.
bridge.renderToVoxel(patientSpacePoint(1, 2, 3));
// @ts-expect-error Source classes remain distinct from data-policy provenance.
const invalidSource: ImagingSourceType = 'development-fixture';
void invalidSource;
// @ts-expect-error Unknown registration cannot supply patient geometry.
const unknown: ImagingObservation = {
  id: 'a',
  patientId: patientId('p'),
  assetId: assetId('a'),
  sourceType: 'synthetic',
  registrationStatus: 'unknown',
  registrationId: null,
  frames: [frame],
};
void unknown;
