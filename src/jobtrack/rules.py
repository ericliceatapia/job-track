VALID_STATUSES = {
    "Applied",
    "Offer",
    "Rejected",
    "Withdrawn",
}

CLOSED_STATUSES = {
    "Offer",
    "Rejected",
    "Withdrawn",
}

VALID_OA_ACTIONS = {
    "received",
    "completed",
}

ALLOWED_STATUS_TRANSITIONS = {
    "Applied": {
        "Offer",
        "Rejected",
        "Withdrawn",
    },
    "Offer": set(),
    "Rejected": set(),
    "Withdrawn": set(),
}


def normalize_status(status: str) -> str:
    """Normalize and validate a status value."""

    normalized = status.strip().lower()

    status_map = {
        "applied": "Applied",
        "offer": "Offer",
        "rejected": "Rejected",
        "withdrawn": "Withdrawn",
    }

    if normalized not in status_map:
        raise ValueError(f"Invalid status: {status}")

    return status_map[normalized]


def normalize_oa_action(action: str) -> str:
    """Normalize and validate an OA action."""

    normalized_action = action.lower()

    if normalized_action not in VALID_OA_ACTIONS:
        raise ValueError(
            "Invalid OA action. Use 'received' or 'completed'."
        )

    return normalized_action


def normalize_status_change(
    current_status: str,
    new_status: str,
) -> str:
    """Normalize and validate an application status transition."""

    normalized_status = normalize_status(new_status)

    if current_status == normalized_status:
        raise ValueError(
            f"Application is already {normalized_status}."
        )

    allowed_statuses = ALLOWED_STATUS_TRANSITIONS.get(current_status)

    if allowed_statuses is None:
        raise ValueError(
            f"Application has an invalid current status: "
            f"{current_status}"
        )

    if normalized_status not in allowed_statuses:
        raise ValueError(
            f"Cannot change status from "
            f"{current_status} to {normalized_status}."
        )

    return normalized_status


def require_active_application(status: str) -> None:
    """Require an application to be active."""

    if status in CLOSED_STATUSES:
        raise ValueError(
            f"Cannot perform this action on an application "
            f"with status '{status}'."
        )


def validate_oa_lifecycle(
    action: str,
    *,
    has_received: bool,
    has_completed: bool,
) -> None:
    """Validate an OA action against its existing lifecycle."""

    if action == "received":
        if has_received:
            raise ValueError(
                "OA has already been recorded as received."
            )

        return

    if action == "completed":
        if not has_received:
            raise ValueError(
                "Cannot complete an OA before recording it as received."
            )

        if has_completed:
            raise ValueError(
                "OA has already been recorded as completed."
            )

        return

    raise ValueError(f"Invalid OA action: {action}")