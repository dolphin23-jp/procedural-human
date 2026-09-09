# MVP 0 Medical Source Dataset Selection

Status: TASK-A01 selection record  
Decision date: 2026-09-08  
Scope: left distal forearm/wrist for Procedural Human MVP 0

## 1. Selected primary source

**NLM Visible Human Project — Visible Human Female dataset**

Provider: U.S. National Library of Medicine (NLM), NIH  
Source class: cadaver-derived reference anatomy with associated radiological imaging  
Dataset page: https://datadiscovery.nlm.nih.gov/Images/Visible-Human-Project/ux2j-9i9a/about_data  
Access instructions: https://www.nlm.nih.gov/research/visible/getting_data.html  
Terms: https://www.nlm.nih.gov/databases/download/terms_and_conditions.html

This selection is for the MVP 0 Medical Master authoring lane. It does not imply that every required structure is already segmented or that all source modalities are perfectly registered for the intended procedure region.

## 2. Why this dataset is selected

MVP 0 requires a medically grounded left distal forearm/wrist region containing, where supportable, skin, subcutaneous tissue, radius, ulna, radial artery, ulnar artery, a superficial target vein such as the cephalic vein, and relevant major muscle/tendon structures.

The Visible Human Female dataset is selected because:

1. it is a whole-body anatomical source and therefore contains the distal forearm/wrist region;
2. its color anatomical sections are sampled at 0.33 mm intervals, matching the stated 0.33 mm in-plane pixel spacing and providing approximately cubic 0.33 mm anatomical voxels;
3. the same Visible Human project also provides CT and MRI data, giving the authoring lane a trusted reference-imaging source without inventing image/anatomy relationships;
4. the source is openly accessible through NLM and has explicit redistribution/use terms;
5. the color cryosection source is substantially better suited than ordinary non-contrast CT alone for manually distinguishing soft-tissue anatomy that may be required for the MVP operative region.

The selection deliberately favors traceable anatomical source quality over convenience or pre-existing meshes.

## 3. Available source modalities and stated resolution

### Color anatomical cryosections

Visible Human Female:
- axial anatomical images;
- 2048 x 1216 pixels;
- 24-bit color;
- approximately 0.33 mm pixel spacing in X-Y;
- 0.33 mm section interval in Z;
- 5,189 anatomical images;
- approximately 40 GB for the complete female dataset.

NLM explicitly notes that the 0.33 mm Z interval was chosen to match the 0.33 mm X-Y pixel spacing for three-dimensional reconstruction.

### CT

The Visible Human datasets include:
- axial whole-body CT;
- 512 x 512 pixels;
- 12-bit gray tone;
- 1 mm section interval.

Exact in-plane CT pixel spacing and the exact transform relationship between CT and the selected female cryosection ROI must be read from source metadata during ingest. They must not be inferred from image dimensions.

### MRI

The project also includes MRI data. MRI is not selected as the primary segmentation source for MVP 0. Its presence may be useful for reference, but no MRI-derived geometric claim is authorized by TASK-A01 alone.

## 4. Licensing and redistribution conditions

NLM describes the Visible Human Project as a publicly available/public-domain image library. Access no longer requires annual license registration.

The current NLM Terms and Conditions require users to:
- acknowledge NLM as the source using the phrase **"Courtesy of the U.S. National Library of Medicine"** in a clear and conspicuous manner;
- not imply NLM endorsement;
- when redistributing data, either maintain the current version or clearly state that the redistributed product may not reflect the most current/accurate NLM data.

No raw or derived large medical binaries will be committed to the main Git repository. Source files remain external and are identified through provenance and hashes according to DATA_POLICY.md.

Before any public redistribution of derived runtime assets, the project must re-check the then-current NLM terms and record that review.

## 4.1 2026-09-10 public review distribution terms re-check

Before enabling the temporary browser-based TASK-A06 human-review surface, the current NLM Visible Human Project terms were re-checked on 2026-09-10.

For the public review surface, the project must:

- display the phrase **"Courtesy of the U.S. National Library of Medicine"** clearly;
- not imply that NLM endorses Procedural Human;
- state that the redistributed review package is derived from the project's recorded 2026 source snapshot and may not reflect the most current or accurate NLM data;
- keep the review package explicitly separate from Medical Master, runtime medical anatomy, Patient Space, and medical validation claims.

The review surface is an authoring aid for the selected bounded source stack and V0 masks. It does not change the dataset's source class, validation level, or licensing provenance.

## 5. Intended MVP 0 use

The selected source will be used to define a reproducible **left distal forearm/wrist ROI** and to create a Medical Master through the authoring pipeline.

Expected roles:
- cryosection images: primary high-detail anatomical reference for segmentation/manual correction;
- CT: trusted reference imaging for the imaging bridge and image/3D correspondence, subject to explicit registration verification;
- MRI: optional supporting reference only where source quality and metadata justify it.

The source remains immutable. Segmentation, centerlines, surfaces, labels, manual corrections, and registrations are derived artifacts with their own provenance.

## 6. Known limitations and mandatory safeguards

### Single cadaver

The female dataset represents one cadaver and must not be presented as universal normal anatomy. Anatomical variation remains a limitation.

### Cadaver state

Cryosection anatomy is post-mortem/frozen anatomy. Vessel caliber, lumen shape, soft-tissue shape, and relationships can differ from living anatomy. No physiological or dynamic claim may be derived from this dataset alone.

### Vessel visibility is not yet accepted

TASK-A01 does **not** establish that the radial artery, ulnar artery, cephalic vein, or other superficial veins can be segmented to the accuracy required for MVP interaction.

Before TASK-A05 is promoted beyond draft segmentation, the selected ROI must undergo a feasibility review confirming that required vessels are actually distinguishable in the source. If a required structure is not adequately supported, the project must downgrade the claim or explicitly revise the source strategy. It must not fabricate missing geometry.

### Nerve visibility is uncertain

The superficial radial nerve is strongly preferred by MVP0.md but is not mandatory when unsupported. It must not be labeled cryosection-derived unless it can be identified with defensible confidence and review.

### Registration must be verified

The presence of CT and anatomical images in the same project does not authorize an assumed identity transform.

TASK-A03/A04 and later registration work must preserve and verify source spatial metadata. Unknown registration remains unknown until established.

### Resolution is not accuracy

The 0.33 mm cryosection sampling does not imply 0.33 mm anatomical accuracy for every structure. Segmentation uncertainty, freezing effects, partial-volume effects, manual edits, and source interpretation must be reflected in the accuracy profile.

### Left-side ROI still needs exact definition

TASK-A01 selects the dataset, not the final crop. TASK-A04 must record the exact left distal forearm/wrist patient-space extent and source slice range reproducibly.

## 7. Secondary reference datasets

Other datasets may be used later as independent references or validation aids, but they are not silently merged into the Medical Master.

A notable candidate is the KU Leuven **Multimodal CT Dataset of Cadaveric Wrist Joints** (DOI: 10.48804/DWF4RG), which provides open CC-BY-SA-4.0 photon-counting CT of the full forearm, HR-pQCT of the full forearm, and 20 µm micro-CT of carpal bones for eight cadaveric wrists.

It is not selected as the primary MVP 0 source at TASK-A01 because its published dataset description does not establish contrast-enhanced visualization or validated segmentation of the superficial venous anatomy required for the venous-access target. It may later be useful for bone/CT cross-checking if provenance is kept separate.

## 8. Acceptance decision

**TASK-A01 decision: ACCEPT Visible Human Female as the primary MVP 0 source dataset, conditionally on ROI-level vessel feasibility verification before medical asset promotion.**

This decision authorizes source acquisition/recording work in TASK-A02 and ingest tooling in TASK-A03. It does not authorize medical validation, runtime release, or fabricated completion of structures not supported by the source.


## 7.1 2026-09-10 cross-subject atlas fallback diagnostic

A bounded Z-Anatomy/BodyParts3D vessel fallback was tested after the same-subject VHP source-first radial-artery and superficial-vein searches failed closed. The atlas remained explicitly `atlas-derived`; it was not treated as acquired VHP geometry.

The registration used the VHP radius/ulna candidates, then calibrated a constant source-stack translation on the first 53 frames of the human-reviewed bounded ulnar-artery segment and evaluated the final transform on the disjoint last 53 frames. The holdout median error was 26.09 source pixels and the P90 error was 33.81 pixels. The predeclared gross-mismatch triage gate required median <= 25 pixels and P90 <= 50 pixels, so the registration failed.

The mapped cephalic and basilic trajectories also had zero median overlap with the reviewed A05 subcutaneous candidate, while the mapped radial-artery trajectory strongly overlapped the major muscle/tendon candidate. These findings make direct cross-subject atlas substitution unsuitable for the current Medical Master strategy.

Decision: **REJECT direct registered-atlas vessel substitution for this VHP individual.** The diagnostic is retained as negative evidence. TASK-A07 and TASK-A10 remain unchanged, and no human anatomical-review, procedure-specific-review, Patient Space, or medical-validation claim is created. A materially different source strategy is required for the missing radial artery and superficial target vein.
