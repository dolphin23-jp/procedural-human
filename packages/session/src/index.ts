import { ImagePatientTransform } from '@procedural-human/imaging-core';
import type {
  ImageVoxelCoordinate,
  RenderSpacePoint,
} from '@procedural-human/math';
import { PatientRenderTransform } from '@procedural-human/rendering-core';

/**
 * Pure coordinate composition, not TASK-082 SimulationSession lifecycle.
 * The caller binds both transforms to the same patient's coordinate reference.
 * No registration inference, renderer/viewer objects, or duplicate transform math.
 */
export class ImageRenderCoordinateBridge {
  readonly #image: ImagePatientTransform;
  readonly #render: PatientRenderTransform;
  constructor(image: ImagePatientTransform, render: PatientRenderTransform) {
    if (
      !(image instanceof ImagePatientTransform) ||
      !(render instanceof PatientRenderTransform)
    )
      throw new TypeError(
        'Explicit ImagePatientTransform and PatientRenderTransform are required.',
      );
    this.#image = image;
    this.#render = render;
    Object.freeze(this);
  }
  voxelToRender(voxel: ImageVoxelCoordinate): RenderSpacePoint {
    return this.#render.patientPointToRender(this.#image.voxelToPatient(voxel));
  }
  renderToVoxel(point: RenderSpacePoint): ImageVoxelCoordinate {
    return this.#image.patientToVoxel(this.#render.renderPointToPatient(point));
  }
}
