from __future__ import annotations

import json
from pathlib import Path


BUILDER = Path("authoring/review/m8v_build_evidence_ledger.py")
TESTS = Path("authoring/source-acquisition/tests/test_m8v_evidence_ledger.py")
LEDGER_SCHEMA = Path("schemas/assets/m8v-evidence-ledger.v1.schema.json")
VALIDATOR = Path("tools/validate-schemas.mjs")
PAGES = Path(".github/workflows/pages.yml")


def patch_builder() -> None:
    text = BUILDER.read_text()

    marker = "\n\n\ndef load(path: Path) -> dict:\n"
    if "CLAIM_KIND_BY_ID" not in text:
        assert marker in text
        constants = '''

RADIAL_CLAIM_IDS = set(RADIAL_GATE_IDS.values())
SUPERFICIAL_TARGET_CLAIM_IDS = set(SUPERFICIAL_GATE_IDS.values()) | {
    "superficial.structure.observed",
    "superficial.identity.named-topology",
    "superficial.identity.named",
}
CLAIM_KIND_BY_ID = {
    "radial.gate.same-subject-anchor": "radial-artery-identity",
    "radial.gate.continuity": "track-continuity",
    "radial.gate.branch-topology": "branch-topology",
    "radial.gate.landmark-relationships": "landmark-relationship",
    "radial.gate.competitor-resolution": "competitor-resolution",
    "radial.gate.human-review": "radial-artery-identity",
    "superficial.gate.direct-extent": "track-continuity",
    "superficial.gate.continuity": "track-continuity",
    "superficial.gate.subcutaneous-relationship": "landmark-relationship",
    "superficial.gate.vein-class": "vessel-class",
    "superficial.gate.competitor-resolution": "competitor-resolution",
    "superficial.gate.human-review": "superficial-vein-structure",
    "superficial.structure.observed": "superficial-vein-structure",
    "superficial.identity.named-topology": "branch-topology",
    "superficial.identity.named": "named-superficial-vein-identity",
}
'''
        text = text.replace(marker, constants + marker, 1)

    start = text.index("def verify_review_session(")
    end = text.index("\n\ndef apply_human_reviews", start)
    verify = '''def verify_review_session(
    session_path: Path, v07_path: Path, v07: dict, track: dict
) -> dict:
    session = load(session_path)
    if session.get("schema") != "ph-m8v-human-adjudication-session.v1":
        raise ValueError("unexpected human adjudication session schema")
    if session.get("task") != "TASK-V08":
        raise ValueError("unexpected human adjudication task")
    expected_surface_hash = file_hash(v07_path)
    review_surface = session.get("reviewSurface", {})
    if review_surface.get("path") != portable_path(v07_path):
        raise ValueError("human review references a different TASK-V07 path")
    if review_surface.get("sha256") != expected_surface_hash:
        raise ValueError("stale human review: TASK-V07 hash mismatch")

    expected_snapshot = {
        (row["path"], row["schema"], row["sha256"]) for row in v07["inputEvidence"]
    }
    actual_rows = session.get("evidenceSnapshot", [])
    actual_snapshot = {
        (row["path"], row["schema"], row["sha256"]) for row in actual_rows
    }
    if actual_snapshot != expected_snapshot or len(actual_rows) != len(v07["inputEvidence"]):
        raise ValueError("stale human review: evidence snapshot mismatch")

    competitor_sets = {row["id"]: set(row["trackIds"]) for row in track["competitorSets"]}
    radial_targets = competitor_sets.get("vhf.m8v.competitors.branch-identity")
    superficial_targets = competitor_sets.get("vhf.m8v.competitors.superficial-structure")
    if not radial_targets or not superficial_targets:
        raise ValueError("TASK-V04 competitor sets are missing or empty")
    if radial_targets & superficial_targets:
        raise ValueError("TASK-V04 radial and superficial competitor sets overlap")

    first_frame = v07["frameCoverage"]["firstWholeBodyFrameIndex"]
    last_frame = v07["frameCoverage"]["lastWholeBodyFrameIndex"]
    per_domain_targets: dict[str, set[str]] = {"radial": set(), "superficial": set()}
    seen_claims: set[str] = set()
    for decision in session.get("decisions", []):
        claim_id = decision.get("claimId")
        if claim_id not in CLAIM_KIND_BY_ID:
            raise ValueError(f"unknown human adjudication claim: {claim_id}")
        if claim_id in seen_claims:
            raise ValueError(f"duplicate human adjudication claim in one session: {claim_id}")
        seen_claims.add(claim_id)
        if decision.get("kind") != CLAIM_KIND_BY_ID[claim_id]:
            raise ValueError(f"human adjudication kind mismatch for claim: {claim_id}")

        target_id = decision.get("targetId")
        if claim_id in RADIAL_CLAIM_IDS:
            if target_id not in radial_targets:
                raise ValueError(f"radial claim references non-radial competitor track: {target_id}")
            per_domain_targets["radial"].add(target_id)
        elif claim_id in SUPERFICIAL_TARGET_CLAIM_IDS:
            if target_id not in superficial_targets:
                raise ValueError(
                    f"superficial claim references non-superficial competitor track: {target_id}"
                )
            per_domain_targets["superficial"].add(target_id)

        frames = decision.get("evidenceFrameIndices", [])
        if decision.get("verdict") == "accepted" and not frames:
            raise ValueError("accepted human adjudication requires at least one evidence frame")
        if any(frame < first_frame or frame > last_frame for frame in frames):
            raise ValueError("human adjudication references a frame outside TASK-V07 coverage")

    for domain, targets in per_domain_targets.items():
        if len(targets) > 1:
            raise ValueError(f"human adjudication mixes multiple {domain} target tracks")
    return session
'''
    text = text[:start] + verify + text[end:]

    start = text.index("def apply_human_reviews(")
    end = text.index("\n\ndef build_ledger", start)
    apply = '''def apply_human_reviews(claims: list[dict], sessions: list[tuple[Path, dict]]) -> None:
    by_claim = {claim["id"]: claim for claim in claims}
    seen: dict[str, tuple[str, str]] = {}
    for _, session in sessions:
        for decision in session["decisions"]:
            claim_id = decision["claimId"]
            verdict = decision["verdict"]
            target_id = decision["targetId"]
            current = (verdict, target_id)
            previous = seen.get(claim_id)
            claim = by_claim[claim_id]
            if previous is not None and previous != current:
                claim["humanReviewStatus"] = "unresolved"
                claim["humanReviewTargetId"] = None
                claim["state"] = "conflicting"
                claim["validationLevel"] = "V2"
                claim["conflictingEvidence"].append(
                    {
                        "source": "TASK-V08 human adjudication",
                        "description": "Human adjudication sessions contain conflicting verdicts or target tracks for this claim.",
                    }
                )
                continue

            seen[claim_id] = current
            claim["humanReviewStatus"] = verdict
            claim["humanReviewTargetId"] = target_id
            description = decision.get("note") or f"Human anatomical adjudication verdict: {verdict}."
            description += f" Target track: {target_id}. Evidence frames: " + ", ".join(
                str(frame) for frame in decision.get("evidenceFrameIndices", [])
            )
            if verdict == "accepted":
                claim["state"] = "supported"
                claim["supportingEvidence"].append(
                    {"source": "TASK-V08 human adjudication", "description": description}
                )
                claim["missingEvidence"] = []
                claim["validationLevel"] = "V2"
            elif verdict == "rejected":
                claim["state"] = "conflicting"
                claim["conflictingEvidence"].append(
                    {"source": "TASK-V08 human adjudication", "description": description}
                )
                claim["validationLevel"] = "V2"
            else:
                claim["state"] = "unresolved"
                claim["conflictingEvidence"].append(
                    {"source": "TASK-V08 human adjudication", "description": description}
                )
                claim["validationLevel"] = "V2"
'''
    text = text[:start] + apply + text[end:]

    old = '''    verified_sessions: list[tuple[Path, dict]] = []
    for review_path in review_paths or []:
        verified_sessions.append((review_path, verify_review_session(review_path, v07_path, v07)))
    apply_human_reviews(claims, verified_sessions)

    by_id = {claim["id"]: claim for claim in claims}
    radial_required = list(RADIAL_GATE_IDS.values())
    superficial_required = list(SUPERFICIAL_GATE_IDS.values())
    radial_ready = all(by_id[claim_id]["state"] == "supported" for claim_id in radial_required)
    superficial_ready = all(
        by_id[claim_id]["state"] == "supported" for claim_id in superficial_required
    )
'''
    new = '''    for claim in claims:
        claim.setdefault("humanReviewTargetId", None)

    verified_sessions: list[tuple[Path, dict]] = []
    for review_path in review_paths or []:
        verified_sessions.append(
            (review_path, verify_review_session(review_path, v07_path, v07, track))
        )
    apply_human_reviews(claims, verified_sessions)

    by_id = {claim["id"]: claim for claim in claims}
    radial_required = list(RADIAL_GATE_IDS.values())
    superficial_required = list(SUPERFICIAL_GATE_IDS.values())

    def accepted_shared_target(claim_ids: list[str]) -> str | None:
        if not all(
            by_id[claim_id]["state"] == "supported"
            and by_id[claim_id]["humanReviewStatus"] == "accepted"
            for claim_id in claim_ids
        ):
            return None
        targets = {by_id[claim_id]["humanReviewTargetId"] for claim_id in claim_ids}
        if len(targets) != 1 or None in targets:
            return None
        return next(iter(targets))

    radial_target = accepted_shared_target(radial_required)
    superficial_target = accepted_shared_target(superficial_required)
    radial_ready = radial_target is not None
    superficial_ready = superficial_target is not None
'''
    assert old in text
    text = text.replace(old, new, 1)

    old = '''    if superficial_ready:
        structure_claim["state"] = "supported"
        structure_claim["missingEvidence"] = []
        structure_claim["supportingEvidence"].append(
'''
    new = '''    if superficial_ready:
        structure_claim["state"] = "supported"
        structure_claim["humanReviewTargetId"] = superficial_target
        structure_claim["missingEvidence"] = []
        structure_claim["supportingEvidence"].append(
'''
    assert old in text
    text = text.replace(old, new, 1)

    old = '''    named_topology = by_id["superficial.identity.named-topology"]["state"] == "supported"
    named_identity_review = (
        by_id["superficial.identity.named"]["humanReviewStatus"] == "accepted"
    )
    named_ready = superficial_ready and named_topology and named_identity_review
'''
    new = '''    named_topology_claim = by_id["superficial.identity.named-topology"]
    named_identity_claim = by_id["superficial.identity.named"]
    named_topology = (
        named_topology_claim["state"] == "supported"
        and named_topology_claim["humanReviewStatus"] == "accepted"
        and named_topology_claim["humanReviewTargetId"] == superficial_target
    )
    named_identity_review = (
        named_identity_claim["humanReviewStatus"] == "accepted"
        and named_identity_claim["humanReviewTargetId"] == superficial_target
    )
    named_ready = superficial_ready and named_topology and named_identity_review
'''
    assert old in text
    text = text.replace(old, new, 1)
    BUILDER.write_text(text)


def patch_tests() -> None:
    text = TESTS.read_text().replace(
        '"targetId": "structure.radial_artery.left",',
        '"targetId": "vhf.m8v.branch-anonymous.01",',
    ).replace(
        '"evidenceFrameIndices": [3000],',
        '"evidenceFrameIndices": [1800],',
    )
    anchor = '''    def test_accepted_review_requires_evidence_frame(self) -> None:
        session = valid_session()
        session["decisions"][0]["evidenceFrameIndices"] = []
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "requires at least one evidence frame"):
                build([path])
'''
    assert anchor in text
    if "test_unknown_claim_is_rejected" not in text:
        extra = anchor + '''
    def test_unknown_claim_is_rejected(self) -> None:
        session = valid_session("radial.unknown")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "unknown human adjudication claim"):
                build([path])

    def test_kind_mismatch_is_rejected(self) -> None:
        session = valid_session()
        session["decisions"][0]["kind"] = "vessel-class"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "kind mismatch"):
                build([path])

    def test_radial_claim_cannot_target_superficial_track(self) -> None:
        session = valid_session()
        session["decisions"][0]["targetId"] = "vhf.m8v.superficial-anonymous.01"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "non-radial competitor track"):
                build([path])

    def test_review_frame_outside_v07_coverage_is_rejected(self) -> None:
        session = valid_session()
        session["decisions"][0]["evidenceFrameIndices"] = [999999]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "outside TASK-V07 coverage"):
                build([path])

    def test_duplicate_claim_in_one_session_is_rejected(self) -> None:
        session = valid_session()
        session["decisions"].append(dict(session["decisions"][0]))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps(session))
            with self.assertRaisesRegex(ValueError, "duplicate human adjudication claim"):
                build([path])
'''
        text = text.replace(anchor, extra, 1)
    TESTS.write_text(text)


def patch_ledger_schema() -> None:
    schema = json.loads(LEDGER_SCHEMA.read_text())
    claim = schema["$defs"]["claim"]
    if "humanReviewTargetId" not in claim["required"]:
        index = claim["required"].index("humanReviewStatus") + 1
        claim["required"].insert(index, "humanReviewTargetId")
    claim["properties"]["humanReviewTargetId"] = {
        "type": ["string", "null"],
        "minLength": 1,
    }
    LEDGER_SCHEMA.write_text(json.dumps(schema, indent=2) + "\n")


def patch_validator() -> None:
    text = VALIDATOR.read_text()
    anchor = '''  [
    'm8v-multimodal-review-surface',
    'schemas/assets/m8v-multimodal-review-surface.v1.schema.json',
    'authoring/outputs/m8v-v07-multimodal-review-surface-20260911.json',
  ],
'''
    assert anchor in text
    if "'m8v-evidence-ledger'" not in text:
        addition = anchor + '''  [
    'm8v-human-adjudication-session',
    'schemas/assets/m8v-human-adjudication-session.v1.schema.json',
    null,
  ],
  [
    'm8v-evidence-ledger',
    'schemas/assets/m8v-evidence-ledger.v1.schema.json',
    'authoring/outputs/m8v-v08-evidence-ledger-20260911.json',
  ],
'''
        text = text.replace(anchor, addition, 1)
    VALIDATOR.write_text(text)


def patch_pages() -> None:
    text = PAGES.read_text()
    anchor = '''      - id: a06-review
        name: Build transient TASK-A06 human-review data
'''
    assert anchor in text
    if "Publish TASK-V08 fail-closed evidence ledger" not in text:
        addition = '''      - name: Publish TASK-V08 fail-closed evidence ledger
        run: |
          test -f authoring/outputs/m8v-v08-evidence-ledger-20260911.json
          mkdir -p apps/web/dist/m8v-review-data
          cp authoring/outputs/m8v-v08-evidence-ledger-20260911.json \\
            apps/web/dist/m8v-review-data/evidence-ledger.json

'''
        text = text.replace(anchor, addition + anchor, 1)
    PAGES.write_text(text)


def main() -> None:
    patch_builder()
    patch_tests()
    patch_ledger_schema()
    patch_validator()
    patch_pages()
    print("TASK-V08 deterministic patch applied")


if __name__ == "__main__":
    main()
