from datetime import date

from sqlalchemy import select

from sqlalchemy.orm import Session

from jobtrack.models import Application, ApplicationEvent


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

