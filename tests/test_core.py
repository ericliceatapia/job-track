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
                             oa=True, interview=True, activity_note="note", status="offer",
                             event_date=DAY)
    session.close()
    assert (a.company, a.status, a.notes) == ("New", "Offer", "role")
    assert [e.event_type for e in a.events] == [
        "APPLICATION_CREATED", "OA_RECEIVED", "INTERVIEW", "NOTE_ADDED", "STATUS_CHANGED"]
    assert a.events[4].old_value == "Applied"

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

@pytest.mark.parametrize("field,value", [
    ("company", " "), ("role_title", " "), ("category", "invalid"),
    ("work_modality", "invalid"), ("job_type", "invalid"), ("source", "invalid"),
    ("notes", 123), ("application_date", "2026-10-01"),
])
def test_creation_validation(session, make, field, value):
    from jobtrack.errors import ValidationError
    with pytest.raises(ValidationError):
        make(**{field: value})
    assert session.scalars(select(Application)).all() == []
    assert session.scalars(select(ApplicationEvent)).all() == []


def test_date_then_id_order_and_oa_chronology(session, make):
    later = make(application_date=date(2026, 10, 3))
    earlier = make(application_date=DAY)
    tied = make(application_date=DAY)
    assert [a.id for a in s.list_applications(session)] == [earlier.id, tied.id, later.id]
    s.record_oa(session, earlier.id, "received", DAY)
    with pytest.raises(ValueError, match="cannot precede"):
        s.record_oa(session, earlier.id, "completed", date(2026, 9, 1))
    assert len(s.get_application(session, earlier.id).events) == 2


def test_validation_rolls_back_owned_session(session, make):
    a = make()
    a.company = "Uncommitted"
    with pytest.raises(ValueError):
        s.update_application(session, a.id, status="invalid")
    assert a.company == "Acme"


def test_core_has_no_interface_imports():
    import ast
    from pathlib import Path
    root = Path(__file__).parents[1] / "src" / "jobtrack"
    forbidden = {"typer", "rich", "textual", "PySide6", "jobtrack.cli"}
    for path in root.glob("*.py"):
        if path.name == "cli.py":
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = ([node.module] if isinstance(node, ast.ImportFrom) else
                     [item.name for item in node.names] if isinstance(node, ast.Import) else [])
            assert not any(name and (name in forbidden or name.split('.')[0] in forbidden)
                           for name in names), path


def test_automatic_oa_proposals_and_completion(session, make):
    a = make()
    received = s.propose_online_assessment(session, a.id, event_date=DAY)
    assert (received.event_type, received.event_date) == ("OA_RECEIVED", DAY)
    assert len(a.events) == 1
    s.update_application(session, a.id, oa=True, expected_oa=received.event_type,
                         event_date=received.event_date)
    completed = s.propose_online_assessment(session, a.id, event_date=DAY)
    assert completed.event_type == "OA_COMPLETED"
    s.update_application(session, a.id, oa=True, expected_oa=completed.event_type,
                         event_date=completed.event_date)
    timestamp = a.updated_at
    assert s.propose_online_assessment(session, a.id).event_type is None
    with pytest.raises(ValueError, match="Online assessment already completed"):
        s.update_application(session, a.id, oa=True, metadata={"company": "Changed"})
    assert a.company == "Acme" and a.updated_at == timestamp
    assert [e.event_type for e in a.events] == ["APPLICATION_CREATED", "OA_RECEIVED", "OA_COMPLETED"]


def test_oa_proposal_cancellation_does_not_flush(session, make):
    a = make()
    timestamp = a.updated_at
    a.company = "Pending unrelated change"
    def forbidden(*args):
        raise AssertionError("Proposal must not flush or commit")
    event.listen(session, "before_flush", forbidden)
    event.listen(session, "before_commit", forbidden)
    try:
        assert s.propose_online_assessment(session, a.id, event_date=DAY).event_type == "OA_RECEIVED"
        # Cancel: never call update_application.
    finally:
        event.remove(session, "before_flush", forbidden)
        event.remove(session, "before_commit", forbidden)
    session.rollback()
    assert (a.company, a.updated_at, len(a.events)) == ("Acme", timestamp, 1)


def test_stale_oa_confirmation_cannot_record_different_milestone(session, make):
    a = make()
    proposal = s.propose_online_assessment(session, a.id, event_date=DAY)
    s.update_application(session, a.id, oa=True, event_date=DAY)
    with pytest.raises(ValueError, match="history changed"):
        s.update_application(session, a.id, oa=True, expected_oa=proposal.event_type,
                             event_date=DAY, metadata={"company": "Changed"})
    assert a.company == "Acme" and len(a.events) == 2


@pytest.mark.parametrize("status", ["Offer", "Rejected", "Withdrawn"])
@pytest.mark.parametrize("milestones", [0, 1, 2])
def test_automatic_oa_closed_restrictions(session, make, status, milestones):
    a = make()
    for _ in range(milestones):
        s.update_application(session, a.id, oa=True, event_date=DAY)
    s.change_status(session, a.id, status, DAY)
    timestamp = a.updated_at
    for operation in (s.propose_online_assessment, s.update_application):
        kwargs = {"oa": True} if operation is s.update_application else {}
        with pytest.raises(ValueError, match="Cannot perform"):
            operation(session, a.id, event_date=DAY, **kwargs)
    assert len(a.events) == milestones + 2 and a.updated_at == timestamp


def test_oa_historical_dates_and_chronology(session, make):
    a = make()
    before_application = date(2026, 9, 30)
    received_day = date(2026, 10, 3)
    for operation in (s.propose_online_assessment, s.update_application):
        kwargs = {"oa": True} if operation is s.update_application else {}
        with pytest.raises(ValueError, match="application date"):
            operation(session, a.id, event_date=before_application, **kwargs)
    s.update_application(session, a.id, oa=True, event_date=received_day)
    for operation in (s.propose_online_assessment, s.update_application):
        kwargs = {"oa": True} if operation is s.update_application else {}
        with pytest.raises(ValueError, match="precede receipt"):
            operation(session, a.id, event_date=DAY, **kwargs)
    s.update_application(session, a.id, oa=True, event_date=received_day)
    assert [e.event_date for e in a.events] == [DAY, received_day, received_day]


def test_oa_inconsistent_legacy_history_is_not_repaired(session, make):
    a = make()
    session.add(ApplicationEvent(application_id=a.id, event_type="OA_COMPLETED", event_date=DAY))
    session.commit()
    with pytest.raises(ValueError, match="without receipt"):
        s.propose_online_assessment(session, a.id)
    with pytest.raises(ValueError, match="without receipt"):
        s.update_application(session, a.id, oa=True)
    assert len(s.get_application(session, a.id).events) == 2


def test_oa_proposal_missing_id_and_invalid_date(session):
    from jobtrack.errors import ApplicationNotFound, ValidationError
    with pytest.raises(ApplicationNotFound):
        s.propose_online_assessment(session, 999)
    with pytest.raises(ValidationError):
        s.propose_online_assessment(session, 1, event_date="2026-10-01")


def test_oa_rechecks_closure_after_proposal(session, make):
    a = make()
    proposal = s.propose_online_assessment(session, a.id, event_date=DAY)
    # A second interface closes the application while confirmation is pending.
    with Session(session.get_bind()) as other:
        s.change_status(other, a.id, "Rejected", DAY)
    assert a.status == "Applied"  # Original identity-map value is stale.
    with pytest.raises(ValueError, match="Cannot perform"):
        s.update_application(session, a.id, oa=True, expected_oa=proposal.event_type,
                             event_date=proposal.event_date)
    assert a.status == "Rejected"
    assert [e.event_type for e in a.events] == ["APPLICATION_CREATED", "STATUS_CHANGED"]
