from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


DraftStatus = Literal["mask-created", "candidate-only", "blocked"]
SourceSupport = Literal["directly-visible", "uncertain", "not-established"]


@dataclass(frozen=True)
class DraftSegment:
    label_value: int
    local_name: str
    intended_anatomy: str
    laterality: Literal["left", "not-applicable"]
    generation_status: DraftStatus
    source_support: SourceSupport
    source_class: str = "cadaver-derived"
    derivation_class: str = "algorithm-derived"
    validation_level: str = "V0"
    review_status: str = "unreviewed"
    limitation: str | None = None


@dataclass(frozen=True)
class DraftSegmentationManifest:
    segmentation_id: str
    roi_id: str
    source_archive_id: str
    source_stack_hash: str
    coordinate_space: str
    registration_status: str
    segments: tuple[DraftSegment, ...]

    def __post_init__(self) -> None:
        if self.coordinate_space != "source-image-stack":
            raise ValueError(
                "TASK-A05 draft segmentation must remain in source-image-stack "
                "until an explicit patient-space registration is available"
            )
        if self.registration_status not in {"unverified", "explicitly-aligned"}:
            raise ValueError("registration status must be explicit")
        labels = [segment.label_value for segment in self.segments]
        if any(label <= 0 for label in labels) or len(labels) != len(set(labels)):
            raise ValueError("draft segmentation labels must be unique positive integers")
        names = [segment.local_name for segment in self.segments]
        if len(names) != len(set(names)):
            raise ValueError("draft segmentation local names must be unique")
        for segment in self.segments:
            if segment.validation_level != "V0" or segment.review_status != "unreviewed":
                raise ValueError(
                    "TASK-A05 automatic output cannot claim review or medical validation"
                )
            if (
                segment.generation_status == "mask-created"
                and segment.source_support == "not-established"
            ):
                raise ValueError(
                    "a mask cannot be created for anatomy not established by the source"
                )

    def to_json_dict(self) -> dict[str, object]:
        return asdict(self)


def mvp0_required_draft_segments() -> tuple[DraftSegment, ...]:
    """Local A05 labels only. Canonical semantic IDs are assigned in TASK-A07."""
    return (
        DraftSegment(
            1,
            "skin",
            "skin",
            "left",
            "candidate-only",
            "uncertain",
            limitation="Automatic boundary candidate requires manual correction in TASK-A06.",
        ),
        DraftSegment(
            2,
            "subcutaneous-soft-tissue",
            "subcutaneous soft-tissue region",
            "left",
            "candidate-only",
            "uncertain",
            limitation="Color-derived tissue class requires manual correction in TASK-A06.",
        ),
        DraftSegment(
            3,
            "radius",
            "radius",
            "left",
            "candidate-only",
            "directly-visible",
            limitation="Bone identity/extent remains V0 until manual anatomical review.",
        ),
        DraftSegment(
            4,
            "ulna",
            "ulna",
            "left",
            "candidate-only",
            "directly-visible",
            limitation="Bone identity/extent remains V0 until manual anatomical review.",
        ),
        DraftSegment(
            5,
            "radial-artery",
            "radial artery",
            "left",
            "blocked",
            "not-established",
            limitation=(
                "Do not fabricate an arterial mask before vessel visibility and continuity "
                "are established in the acquired stack."
            ),
        ),
        DraftSegment(
            6,
            "ulnar-artery",
            "ulnar artery",
            "left",
            "blocked",
            "not-established",
            limitation=(
                "Do not fabricate an arterial mask before vessel visibility and continuity "
                "are established in the acquired stack."
            ),
        ),
        DraftSegment(
            7,
            "superficial-target-vein",
            "cephalic vein or equivalent validated superficial target vein",
            "left",
            "blocked",
            "not-established",
            limitation=(
                "A superficial target vein must be directly established or supplied by a "
                "separately provenance-tracked source before a mask is created."
            ),
        ),
        DraftSegment(
            8,
            "major-muscle-tendon-region",
            "relevant major muscle/tendon structures",
            "left",
            "candidate-only",
            "directly-visible",
            limitation="Individual identities and boundaries require TASK-A06 review.",
        ),
    )
