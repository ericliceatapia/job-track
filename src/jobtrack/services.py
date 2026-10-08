from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobtrack.models import Application, ApplicationEvent
from jobtrack.rules import (
    normalize_required_text,
    normalize_optional_text,
    normalize_category,
    normalize_job_type,
    normalize_source,
    normalize_work_modality,
    require_active_application,
    normalize_status_change,
    normalize_status,
    normalize_oa_action,
    validate_oa_lifecycle,
)


def create_application(
    session: Session,
    *,
    company: str,
    role_title: str,
    category: str,
    location: str | None,
    work_modality: str,
    job_type: str,
    source: str,
    application_date: date,
    job_id: str | None = None,
    notes: str | None = None,
) -> Application:
    """Create an application and its initial event."""

    normalized_company = normalize_required_text(
        company,
        "Company",
    )
    normalized_role_title = normalize_required_text(
        role_title,
        "Role title",
    )
    normalized_category = normalize_category(category)

    normalized_location = normalize_optional_text(location)
    normalized_work_modality = normalize_work_modality(work_modality)
    normalized_job_type = normalize_job_type(job_type)
    normalized_source = normalize_source(source)

    normalized_job_id = normalize_optional_text(job_id)
    normalized_notes = normalize_optional_text(notes)

    try:
        application = Application(
            company=normalized_company,
            role_title=normalized_role_title,
            category=normalized_category,
            location=normalized_location,
            work_modality=normalized_work_modality,
            job_type=normalized_job_type,
            source=normalized_source,
            application_date=application_date,
            status="Applied",
            job_id=normalized_job_id,
            notes=normalized_notes,
        )

        session.add(application)
        session.flush()

        event = ApplicationEvent(
            application_id=application.id,
            event_type="APPLICATION_CREATED",
            event_date=application_date,
        )

        session.add(event)
        session.commit()
        session.refresh(application)

        return application

    except Exception:
        session.rollback()
        raise


def list_applications(
    session: Session,
    *,
    company: str | None = None,
    status: str | None = None,
    category: str | None = None,
) -> list[Application]:
    """Return applications matching all supplied filters, ordered by date."""

    statement = select(Application).order_by(
        Application.application_date.asc(),
        Application.id.asc(),
    )

    if company is not None:
        statement = statement.where(Application.company.icontains(
            normalize_required_text(company, "Company filter"), autoescape=True,
        ))
    if status is not None:
        statement = statement.where(Application.status == normalize_status(status))
    if category is not None:
        statement = statement.where(Application.category == normalize_category(category))

    return list(session.scalars(statement).all())


def get_application(
    session: Session,
    application_id: int,
) -> Application | None:
    """Return an application by ID."""

    return session.get(Application, application_id)


def change_status(
    session: Session,
    application_id: int,
    new_status: str,
    event_date: date,
) -> Application:
    """Change an application's status and record the change."""

    application = session.get(Application, application_id)

    if application is None:
        raise ValueError(f"Application #{application_id} not found.")

    normalized_status = normalize_status_change(
        current_status=application.status,
        new_status=new_status,
    )

    try:
        old_status = application.status
        application.status = normalized_status

        event = ApplicationEvent(
            application_id=application.id,
            event_type="STATUS_CHANGED",
            event_date=event_date,
            old_value=old_status,
            new_value=normalized_status,
        )

        session.add(event)
        session.commit()
        session.refresh(application)

        return application

    except Exception:
        session.rollback()
        raise


def record_oa(
    session: Session,
    application_id: int,
    action: str,
    event_date: date,
) -> ApplicationEvent:
    """Record an OA event for an application."""

    application = session.get(Application, application_id)

    if application is None:
        raise ValueError(f"Application #{application_id} not found.")

    require_active_application(application.status)

    normalized_action = normalize_oa_action(action)

    oa_event_types = set(session.scalars(
        select(ApplicationEvent.event_type).where(
            ApplicationEvent.application_id == application_id,
            ApplicationEvent.event_type.in_(("OA_RECEIVED", "OA_COMPLETED")),
        )
    ))

    validate_oa_lifecycle(
        normalized_action,
        has_received="OA_RECEIVED" in oa_event_types,
        has_completed="OA_COMPLETED" in oa_event_types,
    )

    event_type = (
        "OA_RECEIVED"
        if normalized_action == "received"
        else "OA_COMPLETED"
    )

    try:
        event = ApplicationEvent(
            application_id=application_id,
            event_type=event_type,
            event_date=event_date,
        )

        application.updated_at = datetime.now()
        session.add(event)
        session.commit()
        session.refresh(event)

        return event

    except Exception:
        session.rollback()
        raise


def record_interview(
    session: Session,
    application_id: int,
    event_date: date,
) -> ApplicationEvent:
    """Record an interview event for an application."""

    application = session.get(Application, application_id)

    if application is None:
        raise ValueError(f"Application #{application_id} not found.")

    require_active_application(application.status)

    try:
        event = ApplicationEvent(
            application_id=application_id,
            event_type="INTERVIEW",
            event_date=event_date,
        )

        application.updated_at = datetime.now()
        session.add(event)
        session.commit()
        session.refresh(event)

        return event

    except Exception:
        session.rollback()
        raise

def edit_role_notes(
    session: Session,
    application_id: int,
    notes: str | None,
) -> Application:
    """Replace role notes without adding a lifecycle event."""

    try:
        application = session.get(Application, application_id)
        if application is None:
            raise ValueError(f"Application #{application_id} not found.")

        application.notes = normalize_optional_text(notes)
        session.commit()
        session.refresh(application)
        return application
    except Exception:
        session.rollback()
        raise


def record_note(
    session: Session,
    application_id: int,
    notes: str,
    event_date: date,
) -> ApplicationEvent:
    """Append an activity note, including for closed applications."""

    try:
        application = session.get(Application, application_id)
        if application is None:
            raise ValueError(f"Application #{application_id} not found.")

        event = ApplicationEvent(
            application_id=application_id,
            event_type="NOTE_ADDED",
            event_date=event_date,
            notes=normalize_required_text(notes, "Activity note"),
        )
        application.updated_at = datetime.now()
        session.add(event)
        session.commit()
        session.refresh(event)
        return event
    except Exception:
        session.rollback()
        raise
