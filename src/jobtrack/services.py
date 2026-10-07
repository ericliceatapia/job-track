from datetime import date

from sqlalchemy import select

from sqlalchemy.orm import Session

from jobtrack.models import Application, ApplicationEvent


VALID_STATUSES = {
    "Applied",
    "Offer",
    "Rejected",
    "Withdrawn",
}


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

    try:
        application = Application(
            company=company,
            role_title=role_title,
            category=category,
            location=location,
            work_modality=work_modality,
            job_type=job_type,
            source=source,
            application_date=application_date,
            status="Applied",
            job_id=job_id,
            notes=notes,
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


def list_applications(session: Session) -> list[Application]:
    """Return all applications ordered by application date."""

    statement = select(Application).order_by(
        Application.application_date.desc(),
        Application.id.desc(),
    )

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

    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")

    old_status = application.status

    if old_status == new_status:
        raise ValueError(
            f"Application #{application_id} is already {new_status}."
        )

    try:
        application.status = new_status

        event = ApplicationEvent(
            application_id=application.id,
            event_type="STATUS_CHANGED",
            event_date=event_date,
            old_value=old_status,
            new_value=new_status,
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

    action = action.lower()

    if action not in {"received", "completed"}:
        raise ValueError(
            "Invalid OA action. Use 'received' or 'completed'."
        )

    received_event = session.scalar(
        select(ApplicationEvent).where(
            ApplicationEvent.application_id == application_id,
            ApplicationEvent.event_type == "OA_RECEIVED",
        )
    )

    completed_event = session.scalar(
        select(ApplicationEvent).where(
            ApplicationEvent.application_id == application_id,
            ApplicationEvent.event_type == "OA_COMPLETED",
        )
    )

    if action == "received":
        if received_event is not None:
            raise ValueError(
                f"Application #{application_id} already has an OA received event."
            )

        event_type = "OA_RECEIVED"

    else:
        if received_event is None:
            raise ValueError(
                "Cannot complete an OA before recording it as received."
            )

        if completed_event is not None:
            raise ValueError(
                f"Application #{application_id} already has an OA completed event."
            )

        event_type = "OA_COMPLETED"

    try:
        event = ApplicationEvent(
            application_id=application_id,
            event_type=event_type,
            event_date=event_date,
        )

        session.add(event)
        session.commit()
        session.refresh(event)

        return event

    except Exception:
        session.rollback()
        raise


def get_application_stage(application: Application) -> str:
    """Return the derived lifecycle stage for an application."""

    if application.status != "Applied":
        return application.status

    has_interview = any(
        event.event_type == "INTERVIEW"
        for event in application.events
    )

    if has_interview:
        return "Interviewing"

    return "Applied"


def record_interview(
    session: Session,
    application_id: int,
    event_date: date,
    notes: str | None = None,
) -> ApplicationEvent:
    """Record an interview event for an application."""

    application = session.get(Application, application_id)

    if application is None:
        raise ValueError(f"Application #{application_id} not found.")

    if application.status != "Applied":
        raise ValueError(
            f"Cannot record an interview for an application "
            f"with status '{application.status}'."
        )

    try:
        event = ApplicationEvent(
            application_id=application_id,
            event_type="INTERVIEW",
            event_date=event_date,
            notes=notes,
        )

        session.add(event)
        session.commit()
        session.refresh(event)

        return event

    except Exception:
        session.rollback()
        raise