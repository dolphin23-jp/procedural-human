# MVP 0 forearm/wrist ROI

TASK-A04 defines how the left distal forearm/wrist authoring region is selected
and how its exact patient-space extent is recorded.

## Why the numeric extent is not pre-filled

The project does not treat Visible Human Female source filenames as patient
coordinates. The original cryosection sequence has known transverse offsets,
and CT/cryosection correspondence must not be promoted to an identity
registration without verification.

For that reason, `mvp0-left-distal-forearm-wrist.json` deliberately keeps the
measured extent, Frame of Reference UID, SOP Instance UID list, and pixel crop
empty until the selected source bytes have been acquired and an explicitly
aligned source series is available.

Putting plausible-looking numbers in those fields before that step would
violate DATA_POLICY.md and the imaging-coordinate rules.

## Reproducible procedure

1. Acquire the source files and produce an A02 SHA-256 archive snapshot.
2. Prepare or select an explicitly aligned anatomical DICOM series.
3. Ingest every candidate slice with `ph_dicom.read_dicom_record`.
4. Run `ph_dicom.validate_and_sort_series`; do not continue on missing or
   conflicting geometry.
5. Verify that the limb is the **left** limb from the image orientation and
   anatomy.
6. Mark the radiocarpal-joint center on the aligned source.
7. Select the longitudinal span specified by the ROI record.
8. Select one rectangular in-plane crop that contains the complete left-limb
   skin envelope across the span plus the specified engineering margin.
9. Record the exact SOP Instance UIDs and `PixelCrop`.
10. Compute the extent with `ph_dicom.patient_extent_for_crop` and write the
    returned millimetre AABB and Frame of Reference UID back into the ROI
    record.

The resulting numbers are derived from source spatial metadata. They are not
estimated from screenshots, filenames, or anatomical expectation.

## Acceptance boundary

The A04 **workflow and contract** are implemented in Git. The numeric source
measurement remains blocked until the external medical source is actually
materialized and aligned. That blocker must remain visible rather than being
replaced by synthetic coordinates.
