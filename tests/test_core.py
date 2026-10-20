from datetime import date

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from openpyxl import load_workbook

from jobtrack.models import Base, Application, ApplicationEvent
from jobtrack import services as s
from jobtrack.exporting import export_applications

DAY = date(2026, 10, 1)

@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()

@pytest.fixture
def make(session):
    def create(**changes):
        fields = dict(company=" Acme ", role_title=" Analyst ", category="analytics",
                      location="  ", work_modality="remote", job_type="full-time",
                      source="linkedin", application_date=DAY, job_id="00123")
        fields.update(changes)
        return s.create_application(session, **fields)
    return create

def test_creation(session, make):
    a = make()
    assert (a.company, a.role_title, a.category, a.location, a.status) == (
        "Acme", "Analyst", "Analytics", None, "Applied")
    assert [(e.event_type, e.event_date) for e in a.events] == [("APPLICATION_CREATED", DAY)]

@pytest.mark.parametrize("status", ["Offer", "Rejected", "Withdrawn"])
def test_terminal_status(session, make, status):
    a = make()
    s.change_status(session, a.id, f" {status.lower()} ", DAY)
    assert a.status == status
    for action in [lambda: s.change_status(session, a.id, "Applied", DAY),
                   lambda: s.change_status(session, a.id, status, DAY),
                   lambda: s.record_oa(session, a.id, "received", DAY),
                   lambda: s.record_interview(session, a.id, DAY)]:
        with pytest.raises(ValueError):
            action()
    s.edit_role_notes(session, a.id, " role ")
    s.record_note(session, a.id, " activity ", DAY)
    assert a.notes == "role"

def test_oa_and_interviews(session, make):
    a = make()
    with pytest.raises(ValueError):
        s.record_oa(session, a.id, "completed", DAY)
    for action in ("received", "completed"):
        assert s.record_oa(session, a.id, f" {action.upper()} ", DAY).event_type == f"OA_{action.upper()}"
        with pytest.raises(ValueError):
            s.record_oa(session, a.id, action, DAY)
    assert s.record_interview(session, a.id, DAY).id != s.record_interview(session, a.id, DAY).id

def test_notes_and_missing(session, make):
    a = make()
    s.edit_role_notes(session, a.id, " role ")
    s.edit_role_notes(session, a.id, None)
    assert a.notes is None
    assert s.record_note(session, a.id, " text ", DAY).notes == "text"
    with pytest.raises(ValueError):
        s.record_note(session, a.id, " ", DAY)
    assert s.get_application(session, 999) is None
    with pytest.raises(ValueError):
        s.edit_role_notes(session, 999, "x")

def test_filters(session, make):
    a = make(company="100% Acme")
    make(company="Other", category="software")
    assert s.list_applications(session, company="%", category=" ANALYTICS ", status="applied") == [a]
    assert s.list_applications(session, company="acme", category="software") == []
    assert [x.id for x in s.list_applications(session)] == [1, 2]
    with pytest.raises(ValueError):
        s.list_applications(session, status="invalid")

def test_export(session, make, tmp_path):
    a = make(company="=literal")
    s.record_note(session, a.id, "=note", date(2026, 9, 1))
    path = tmp_path / "result.xlsx"
    assert export_applications(s.list_applications(session), path) == 2
    book = load_workbook(path)
    assert book.sheetnames == ["Applications", "History"]
    assert book["Applications"]["B2"].data_type == "s"
    assert book["Applications"]["K2"].value == "00123"
    assert book["History"]["F2"].value == "NOTE_ADDED"
    book.close()
    with pytest.raises(ValueError):
        export_applications([a], path)
    assert export_applications([], path, overwrite=True) == 0

def test_failed_write_rolls_back(session, make):
    def fail(mapper, connection, target):
        raise RuntimeError("injected event failure")
    event.listen(ApplicationEvent, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            make()
    finally:
        event.remove(ApplicationEvent, "before_insert", fail)
    assert session.scalars(select(Application)).all() == []
    assert session.scalars(select(ApplicationEvent)).all() == []
    assert make().id == 1

def test_combined_update_and_detached_history(session, make):
    a = make()
    a = s.update_application(session, a.id, metadata={"company": " New ", "notes": "role"},
                             oa="received", interview=True, activity_note="note", status="offer",
                             event_date=date(2026, 9, 1))
    session.close()
    assert (a.company, a.status, a.notes) == ("New", "Offer", "role")
    assert [e.event_type for e in a.events] == [
        "OA_RECEIVED", "INTERVIEW", "NOTE_ADDED", "STATUS_CHANGED", "APPLICATION_CREATED"]
    assert a.events[3].old_value == "Applied"

@pytest.mark.parametrize("changes", [
    {"metadata": {"company": "Changed"}, "oa": "completed"},
    {"metadata": {"company": "Changed"}, "activity_note": " "},
    {"interview": True, "status": "invalid"},
    {"metadata": {"id": 3}}, {"metadata": {"company": None}},
    {"event_date": "2026-10-01", "interview": True},
    {"metadata": {"application_date": "2026-10-01"}}, {},
])
def test_invalid_update_is_atomic(session, make, changes):
    from jobtrack.errors import ValidationError
    a = make()
    with pytest.raises(ValidationError):
        s.update_application(session, a.id, **changes)
    assert a.company == "Acme"
    assert a.status == "Applied"
    assert len(s.get_application(session, a.id).events) == 1
    assert not session.new


def test_update_persistence_failure(session, make):
    a = make()
    original_updated = a.updated_at
    def fail(mapper, connection, target):
        raise RuntimeError("event write failed")
    event.listen(ApplicationEvent, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            s.update_application(session, a.id, metadata={"company": "changed"},
                                 interview=True, status="Offer")
    finally:
        event.remove(ApplicationEvent, "before_insert", fail)
    assert (a.company, a.status, a.updated_at) == ("Acme", "Applied", original_updated)
    assert len(a.events) == 1
    s.record_interview(session, a.id, DAY)


def test_metadata_fields_and_history(session, make):
    a = make()
    fields = dict(company="New", role_title="Engineer", category="software", location="NY",
                  work_modality="hybrid", job_type="contract", source="referral",
                  application_date=date(2026, 10, 2), job_id=None, notes="text")
    s.update_application(session, a.id, metadata=fields)
    assert a.category == "Software"
    assert a.job_type == "Contract"
    assert a.source == "Referral"
    assert a.work_modality == "Hybrid"
    assert a.job_id is None
    assert a.events[0].event_date == DAY
    s.update_application(session, a.id, metadata={"location": " ", "notes": None})
    assert a.location is None and a.notes is None


def test_read_results_survive_close(session, make):
    a = make()
    s.record_interview(session, a.id, DAY)
    applications = s.list_applications(session)
    result = s.get_application(session, a.id)
    session.close()
    assert len(applications[0].events) == len(result.events) == 2


def test_explicit_database_path_and_existing_schema(tmp_path, monkeypatch):
    from jobtrack import database
    def forbidden():
        raise AssertionError("Production database path must never be resolved")
    monkeypatch.setattr(database, "get_database_path", forbidden)
    path = tmp_path / "isolated.db"
    # Create the unchanged model schema before exercising the database API.
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    engine.dispose()
    database.initialize_database(path)
    assert database.create_database_engine(path) is database.create_database_engine(path)
    with database.create_session(path) as isolated:
        assert s.list_applications(isolated) == []
    database.create_database_engine(path).dispose()


def test_export_operation(session, make, tmp_path):
    make()
    make(company="Other")
    assert s.export_application_data(session, tmp_path / "filtered.xlsx", company="acme") == (1, 1)


def test_domain_errors(session):
    from jobtrack.errors import ApplicationNotFound, ValidationError
    with pytest.raises(ApplicationNotFound):
        s.update_application(session, 999, interview=True)
    with pytest.raises(ValidationError):
        s.get_application(session, True)
