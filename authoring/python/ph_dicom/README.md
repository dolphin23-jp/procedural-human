# ph_dicom

`ph_dicom` owns source-image ingest and spatial-integrity extraction for the
authoring pipeline.

TASK-A03 intentionally reads DICOM metadata without decoding pixel data. Every
ingested instance records a SHA-256 hash and preserves the spatial fields needed
to place it in patient space:

- `PixelSpacing`
- `ImagePositionPatient`
- `ImageOrientationPatient`
- `FrameOfReferenceUID` when supplied
- `SpacingBetweenSlices` / `SliceThickness` when supplied
- study, series, SOP instance, and modality identifiers

Missing required geometry fails with `SpatialMetadataUnavailable`. Candidate
series with conflicting geometry fail with `SpatialMetadataConflict`. Unknown
registration is never converted to identity registration.

The Visible Human Female filename parser records only the nominal source index
encoded by names such as `avf1703b`. That value is **not patient space** and
must not be used as a substitute for registered image geometry.

Large source data remains outside Git. Source snapshots are recorded with
SHA-256 hashes after the bytes are acquired locally.
