"""UI-independent operations. Writers own and commit the supplied transaction.

Use a dedicated session per operation. Failures roll back the entire session;
reads never commit. Returned applications include history and survive session close.
"""
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from jobtrack.models import Application, ApplicationEvent
from jobtrack.errors import ApplicationNotFound, ValidationError
from jobtrack.rules import (
    normalize_required_text, normalize_optional_text, normalize_category,
    normalize_job_type, normalize_source, normalize_work_modality,
    require_active_application, normalize_status_change, normalize_status,
    normalize_oa_action, validate_oa_lifecycle, normalize_date,
)


def _atomic(operation):
    @wraps(operation)
    def execute(session, *args, **kwargs):
        expire = session.expire_on_commit
        try:
            result = operation(session, *args, **kwargs)
            session.flush()
            session.expire(result, ["events"])
            result.events.sort(key=lambda event: (event.event_date, event.id))
            session.expire_on_commit = False
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.expire_on_commit = expire
    return execute


_METADATA = {
    "company": lambda v: normalize_required_text(v, "Company"),
    "role_title": lambda v: normalize_required_text(v, "Role title"),
    "category": normalize_category,
    "location": normalize_optional_text,
    "work_modality": normalize_work_modality,
    "job_type": normalize_job_type,
    "source": normalize_source,
    "application_date": lambda v: normalize_date(v, "Application date"),
    "job_id": normalize_optional_text,
    "notes": normalize_optional_text,
}


def _metadata(values):
    if not isinstance(values, Mapping):
        raise ValidationError("Metadata must be a mapping of editable fields.")
    if any(key not in _METADATA for key in values):
        raise ValidationError("Metadata contains an unknown or read-only field.")
    return {key: _METADATA[key](value) for key, value in values.items()}


def _event(session, application, event_type, event_date, **values):
    event = ApplicationEvent(application_id=application.id, event_type=event_type,
                             event_date=event_date, **values)
    application.updated_at = datetime.now()
    session.add(event)
    return event


@_atomic
def create_application(session: Session, *, company: str, role_title: str,
                       category: str, location: str | None, work_modality: str,
                       job_type: str, source: str, application_date: date,
                       job_id: str | None = None, notes: str | None = None) -> Application:
    """Create metadata and the initial event in one transaction."""
    values = _metadata(dict(company=company, role_title=role_title, category=category,
                            location=location, work_modality=work_modality,
                            job_type=job_type, source=source, application_date=application_date,
                            job_id=job_id, notes=notes))
    application = Application(**values, status="Applied")
    session.add(application)
    session.flush()
    _event(session, application, "APPLICATION_CREATED", application_date)
    return application


def _loaded(session, statement):
    applications = list(session.scalars(statement.options(selectinload(Application.events))).all())
    for application in applications:
        application.events.sort(key=lambda event: (event.event_date, event.id))
    return applications


def list_applications(session: Session, *, company: str | None = None,
                      status: str | None = None, category: str | None = None) -> list[Application]:
    """AND filters; literal company substring; ascending application date and ID."""
    statement = select(Application).order_by(Application.application_date, Application.id)
    if company is not None:
        statement = statement.where(Application.company.icontains(
            normalize_required_text(company, "Company filter"), autoescape=True))
    if status is not None:
        statement = statement.where(Application.status == normalize_status(status))
    if category is not None:
        statement = statement.where(Application.category == normalize_category(category))
    return _loaded(session, statement)


def get_application(session: Session, application_id: int) -> Application | None:
    """Return an application with ordered history, or None if absent."""
    _validate_id(application_id)
    applications = _loaded(session, select(Application).where(Application.id == application_id))
    return applications[0] if applications else None


def _validate_id(application_id):
    if type(application_id) is not int or application_id < 1:
        raise ValidationError("Application ID must be a positive integer.")


@_atomic
def update_application(session: Session, application_id: int, *,
                       metadata: Mapping | None = None, oa: str | None = None,
                       interview: bool = False, activity_note: str | None = None,
                       status: str | None = None, event_date: date | None = None) -> Application:
    """Atomically update metadata and/or append events; status is applied last.

    Omitted fields remain unchanged. None/blank clears optional metadata. Dates
    default to today for new events. Editing application_date preserves history.
    """
    _validate_id(application_id)
    if type(interview) is not bool:
        raise ValidationError("Interview must be a boolean.")
    values = _metadata(metadata) if metadata is not None else {}
    if not values and oa is None and not interview and activity_note is None and status is None:
        raise ValidationError("No application changes supplied.")
    day = normalize_date(event_date if event_date is not None else date.today(), "Event date")
    application = get_application(session, application_id)
    if application is None:
        raise ApplicationNotFound(f"Application #{application_id} not found.")
    for key, value in values.items():
        setattr(application, key, value)
    if oa is not None:
        require_active_application(application.status)
        action = normalize_oa_action(oa)
        types = {event.event_type for event in application.events}
        validate_oa_lifecycle(action, has_received="OA_RECEIVED" in types,
                              has_completed="OA_COMPLETED" in types)
        _event(session, application, f"OA_{action.upper()}", day)
    if interview:
        require_active_application(application.status)
        _event(session, application, "INTERVIEW", day)
    if activity_note is not None:
        _event(session, application, "NOTE_ADDED", day,
               notes=normalize_required_text(activity_note, "Activity note"))
    if status is not None:
        normalized = normalize_status_change(application.status, status)
        _event(session, application, "STATUS_CHANGED", day,
               old_value=application.status, new_value=normalized)
        application.status = normalized
    return application


# Compatibility adapters retain meaningful specialized entry points and returns.
def change_status(session, application_id, new_status, event_date):
    return update_application(session, application_id, status=new_status, event_date=event_date)


def edit_role_notes(session, application_id, notes):
    return update_application(session, application_id, metadata={"notes": notes})


def _latest_event(application, event_types):
    return max((event for event in application.events if event.event_type in event_types),
               key=lambda event: event.id)


def record_oa(session, application_id, action, event_date):
    return _latest_event(update_application(session, application_id, oa=action, event_date=event_date),
                         ("OA_RECEIVED", "OA_COMPLETED"))


def record_interview(session, application_id, event_date):
    return _latest_event(update_application(session, application_id, interview=True,
                                            event_date=event_date), ("INTERVIEW",))


def record_note(session, application_id, notes, event_date):
    return _latest_event(update_application(session, application_id, activity_note=notes,
                                            event_date=event_date), ("NOTE_ADDED",))


def export_application_data(session: Session, destination: Path, *, company=None,
                            status=None, category=None, overwrite=False) -> tuple[int, int]:
    """Export matching applications/history; return (application count, event count)."""
    from jobtrack.exporting import export_applications
    applications = list_applications(session, company=company, status=status, category=category)
    return len(applications), export_applications(applications, destination, overwrite=overwrite)
