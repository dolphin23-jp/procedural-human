from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class SemanticMappingError(ValueError):
    pass


@dataclass(frozen=True)
class SemanticIdentity:
    draft_label: str
    anatomical_id: str
    name: str
    type: str
    laterality: str
    region: str


KNOWN_IDENTITIES: tuple[SemanticIdentity, ...] = (
    SemanticIdentity(
        "skin",
        "structure.skin.left_distal_forearm_wrist",
        "Left distal forearm/wrist skin",
        "tissue",
        "left",
        "left-distal-forearm-wrist",
    ),
    SemanticIdentity(
        "subcutaneous_soft_tissue",
        "structure.subcutaneous_soft_tissue.left_distal_forearm_wrist",
        "Left distal forearm/wrist subcutaneous soft tissue",
        "tissue-region",
        "left",
        "left-distal-forearm-wrist",
    ),
    SemanticIdentity(
        "major_muscle_tendon_region",
        "structure.major_muscle_tendon_region.left_distal_forearm_wrist",
        "Left distal forearm/wrist major muscle/tendon region",
        "tissue-region",
        "left",
        "left-distal-forearm-wrist",
    ),
    SemanticIdentity(
        "radius",
        "structure.radius.left",
        "Left radius",
        "bone",
        "left",
        "left-distal-forearm-wrist",
    ),
    SemanticIdentity(
        "ulna",
        "structure.ulna.left",
        "Left ulna",
        "bone",
        "left",
        "left-distal-forearm-wrist",
    ),
    SemanticIdentity(
        "radial_artery",
        "structure.radial_artery.left",
        "Left radial artery",
        "artery",
        "left",
        "left-distal-forearm-wrist",
    ),
    SemanticIdentity(
        "ulnar_artery",
        "structure.ulnar_artery.left",
        "Left ulnar artery",
        "artery",
        "left",
        "left-distal-forearm-wrist",
    ),
)

_BY_LABEL = {item.draft_label: item for item in KNOWN_IDENTITIES}


def build_semantic_mapping_record(
    *,
    recorded_at: str,
    generated_labels: Iterable[str],
    blocked_labels: Iterable[str],
    target_superficial_vein_established: bool,
) -> dict[str, object]:
    generated = tuple(generated_labels)
    blocked = tuple(blocked_labels)
    if len(set(generated)) != len(generated):
        raise SemanticMappingError("generated labels must be unique")
    if len(set(blocked)) != len(blocked):
        raise SemanticMappingError("blocked labels must be unique")
    overlap = set(generated) & set(blocked)
    if overlap:
        raise SemanticMappingError(
            f"labels cannot be both generated and blocked: {sorted(overlap)}"
        )

    unknown = (set(generated) | set(blocked)) - set(_BY_LABEL)
    if unknown:
        raise SemanticMappingError(
            f"semantic identity is not defined for labels: {sorted(unknown)}"
        )

    mappings: list[dict[str, object]] = []
    for label in generated + blocked:
        identity = _BY_LABEL[label]
        generated_representation = label in generated
        mappings.append(
            {
                "draftLabel": label,
                "anatomicalId": identity.anatomical_id,
                "name": identity.name,
                "type": identity.type,
                "laterality": identity.laterality,
                "region": identity.region,
                "mappingStatus": (
                    "mapped-candidate-representation"
                    if generated_representation
                    else "semantic-id-reserved-no-representation"
                ),
                "representationAvailable": generated_representation,
                "validationLevel": "V0",
            }
        )

    unresolved: list[dict[str, object]] = []
    if target_superficial_vein_established:
        raise SemanticMappingError(
            "a target superficial vein cannot be mapped without an explicit named anatomical identity"
        )
    unresolved.append(
        {
            "draftLabel": "superficial_target_vein",
            "semanticRole": "venous_access_target",
            "anatomicalId": None,
            "reason": (
                "source evidence does not establish a named superficial vein identity; "
                "a procedure role must not be substituted for an anatomical entity ID"
            ),
        }
    )

    return {
        "schema": "ph-semantic-structure-mapping.v1",
        "schemaVersion": "1",
        "task": "TASK-A07",
        "recordedAt": recorded_at,
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
        },
        "mappings": mappings,
        "unresolved": unresolved,
        "claims": {
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "representationPresenceImpliedByIdentity": False,
            "procedureRoleUsedAsAnatomicalIdentity": False,
        },
    }
