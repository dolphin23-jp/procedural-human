from pathlib import Path

path = Path("TASKS.md")
text = path.read_text()
if "# M8V — Vessel Identification Evidence Lane" in text:
    raise SystemExit("M8V already present; refusing duplicate insertion")

marker = "Gate S: complete — reusable whole-body source foundation exists and the missing MVP vascular identities have been re-evaluated using same-subject continuity evidence; this does not imply a whole-body Medical Master.\n\n# M8A — Medical Asset Authoring Lane"
if text.count(marker) != 1:
    raise SystemExit("expected unique Gate S to M8A insertion marker")

block = """Gate S: complete — reusable whole-body source foundation exists and the missing MVP vascular identities have been re-evaluated using same-subject continuity evidence; this does not imply a whole-body Medical Master.

# M8V — Vessel Identification Evidence Lane

This authoring-support lane resolves medically meaningful vascular identity claims after M8S and before Medical Master promotion. It preserves same-subject direct evidence, gaps, competing candidates, landmark and registration support, and human review as separate evidence dimensions. No scalar confidence, procedure role, atlas prior, or review UI may substitute for a missing promotion requirement.

Detailed policy and evidence contracts are maintained in `authoring/vessel-identification/VESSEL_IDENTIFICATION_EVIDENCE.md`.

## TASK-V01 — Same-subject radiological source inventory
Status: complete — same-subject CT/MRI availability and limitations are inventoried without claiming registration or vessel identity.

## TASK-V02 — Cryosection ↔ CT registration scaffold
Status: complete — bounded same-subject radius/ulna bone-landmark scaffold established for authoring support only; not Patient Space or medical registration.

## TASK-V03 — Upper-extremity landmark graph
Status: complete — bounded radius/ulna support, V0 generic tissue-region priors, and explicitly unresolved named muscle/styloid landmarks are represented separately.

## TASK-V04 — Candidate vessel source-index 3D track graph
Status: complete — 17 tracks and 900 direct observations preserve continuation, explicit gaps, and competing candidates in source-index coordinates without named-vessel promotion.

## TASK-V05 — Radial arterial identity evidence
Status: complete / blocked-unresolved — all six promotion gates were evaluated independently; no radial candidate is selected and radial/brachial/bifurcation identity remains unresolved.

## TASK-V06 — Superficial venous network evidence
Status: complete / blocked-unresolved — eight anonymous superficial tracks remain short and competing; no procedure-relevant directly continuous vein structure or vein class is established.

## TASK-V07 — Multimodal review surface
Status: complete — browser/iPad review is available at `?m8v-review=1`, synchronizing source cryosection, bounded CT support, V04 track overlays, V03 landmarks, V05/V06 gates, and provenance. Viewing does not itself confer human review, identity, validation, Patient Space, or procedure role.

## TASK-V08 — Evidence ledger and explicit human adjudication evidence
Status: next.
Create the durable machine-readable ledger linking each medically meaningful claim to supporting, conflicting, missing, algorithm-derived, and explicit human-review evidence. Claim-level human adjudication must be recorded as review evidence tied to immutable input hashes; merely opening or using the V07 surface is not a review receipt. Human anatomical review may satisfy only the claims actually reviewed and does not by itself confer V3 medical validation or procedure suitability.

## TASK-V09 — Identity promotion evaluator
Implement fail-closed promotion rules for radial-artery identity, subject-scoped superficial-vein structure, and named superficial-vein identity. Every required gate must pass independently; no single scalar confidence may replace required evidence.

## TASK-V10 — Feed M8V evidence into M8A
Feed only passed claims and representations into A06/A07/A08/A09 and reevaluate A10. Preserve historical evidence and valid ulnar work. If required gates still fail, A10 remains blocked.

Gate V after TASK-V10: vascular identity evidence required by the MVP has either passed explicit promotion gates and been fed into M8A, or remains fail-closed with the source limitation documented. Gate V never means that unresolved anatomy may be fabricated.

# M8A — Medical Asset Authoring Lane"""
text = text.replace(marker, block)

gates_marker = "Gate S (complete) after TASK-AS07: reusable whole-body source foundation exists and missing MVP vascular identities have been re-evaluated from same-subject continuity evidence. Gate S does not imply a whole-body Medical Master.  \nGate I after TASK-A18: medically grounded runtime asset."
gates_replacement = "Gate S (complete) after TASK-AS07: reusable whole-body source foundation exists and missing MVP vascular identities have been re-evaluated from same-subject continuity evidence. Gate S does not imply a whole-body Medical Master.  \nGate V after TASK-V10: vascular identity evidence has been explicitly adjudicated, promotion-gated, and fed forward or remains fail-closed with documented source limitation.  \nGate I after TASK-A18: medically grounded runtime asset."
if text.count(gates_marker) != 1:
    raise SystemExit("expected unique Critical Gates marker")
text = text.replace(gates_marker, gates_replacement)
path.write_text(text)
