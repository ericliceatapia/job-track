from datetime import date

from sqlalchemy import select

from sqlalchemy.orm import Session

from jobtrack.models import Application, ApplicationEvent


VALID_STATUSES = {
    "Applied",
    "Interviewing",
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