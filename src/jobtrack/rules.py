CLOSED_STATUSES = (
    "Offer",
    "Rejected",
    "Withdrawn",
)

VALID_STATUSES = ("Applied", *CLOSED_STATUSES)
STATUS_CHANGE_OPTIONS = CLOSED_STATUSES

ALLOWED_STATUS_TRANSITIONS = {
    "Applied": CLOSED_STATUSES,
    **{status: () for status in CLOSED_STATUSES},
}

VALID_CATEGORIES = (
    "Analytics",
    "Systems",
    "Operations",
    "Finance",
    "Strategy",
    "Software",
    "IT",
    "Cybersecurity",
    "Other",
)

VALID_WORK_MODALITIES = (
    "On-site",
    "Hybrid",
    "Remote",
)

VALID_JOB_TYPES = (
    "Full-Time",
    "Internship",
    "Part-Time",
    "Contract",
)

VALID_SOURCES = (
    "Company Website",
    "LinkedIn",
    "Handshake",
    "Referral",
    "Career Fair",
    "Recruiter",
    "Other",
)

VALID_OA_ACTIONS = (
    "received",
    "completed",
)


def normalize_oa_action(action: str) -> str:
    """Normalize and validate an OA action."""

    normalized_action = action.strip().casefold()

    if normalized_action not in VALID_OA_ACTIONS:
        raise ValueError(
            "Invalid OA action. Use 'received' or 'completed'."
        )

    return normalized_action


def normalize_status(status: str) -> str:
    """Normalize and validate a status value."""

    return _normalize_controlled_value(
        status,
        VALID_STATUSES,
        "status",
    )


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


def _normalize_controlled_value(
    value: str,
    valid_values: tuple[str, ...],
    field_name: str,
) -> str:
    """Normalize a controlled value to its canonical representation."""

    normalized_input = value.strip().casefold()

    value_map = {
        valid_value.casefold(): valid_value
        for valid_value in valid_values
    }

    if normalized_input not in value_map:
        raise ValueError(
            f"Invalid {field_name}: {value}"
        )

    return value_map[normalized_input]


def normalize_category(category: str) -> str:
    """Normalize and validate an application category."""

    return _normalize_controlled_value(
        category,
        VALID_CATEGORIES,
        "category",
    )


def normalize_work_modality(work_modality: str) -> str:
    """Normalize and validate a work modality."""

    return _normalize_controlled_value(
        work_modality,
        VALID_WORK_MODALITIES,
        "work modality",
    )


def normalize_job_type(job_type: str) -> str:
    """Normalize and validate a job type."""

    return _normalize_controlled_value(
        job_type,
        VALID_JOB_TYPES,
        "job type",
    )


def normalize_source(source: str) -> str:
    """Normalize and validate an application source."""

    return _normalize_controlled_value(
        source,
        VALID_SOURCES,
        "source",
    )


def normalize_required_text(
    value: str,
    field_name: str,
) -> str:
    """Strip and validate a required text field."""

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")

    return normalized


def normalize_optional_text(
    value: str | None,
) -> str | None:
    """Strip optional text and convert blank values to None."""

    if value is None:
        return None

    normalized = value.strip()

    return normalized or None


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