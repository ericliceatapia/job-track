from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from jobtrack import cli, services
from jobtrack.models import Base

@pytest.fixture
def cli_db(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'cli.db').as_posix()}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(cli, "create_session", lambda: Session(engine))
    monkeypatch.setattr(cli, "initialize_database", lambda: Base.metadata.create_all(engine))
    monkeypatch.setattr(cli, "get_database_path", lambda: tmp_path / "cli.db")
    with Session(engine) as session:
        app = services.create_application(session, company="Acme", role_title="Analyst",
            category="Analytics", location=None, work_modality="Remote", job_type="Full-Time",
            source="LinkedIn", application_date=date(2026, 10, 1))
        application_id = app.id
    yield engine, application_id
    engine.dispose()


def test_public_commands(cli_db):
    runner = CliRunner()
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0, result.output
    from typer.main import get_command
    assert set(get_command(cli.app).commands) == {"db", "add", "list", "show", "update", "export"}
    for name in ("status", "oa", "interview", "edit", "log"):
        assert runner.invoke(cli.app, [name]).exit_code == 2


def test_update_flags(cli_db):
    engine, app_id = cli_db
    result = CliRunner().invoke(cli.app, ["update", str(app_id), "--company", "New",
        "--notes", "role", "--oa", "received", "--interview", "--activity-note", "note",
        "--status", "offer", "--event-date", "2026-10-02"])
    assert result.exit_code == 0, result.output
    with Session(engine) as session:
        a = services.get_application(session, app_id)
        assert (a.company, a.status, a.notes) == ("New", "Offer", "role")
        assert len(a.events) == 5

@pytest.mark.parametrize("args", [
    ["--notes", "x", "--clear-notes"], ["--event-date", "bad", "--interview"],
    ["--company", "Changed", "--oa", "completed"], ["--category", "bad"],
])
def test_invalid_cli_update(cli_db, args):
    engine, app_id = cli_db
    assert CliRunner().invoke(cli.app, ["update", str(app_id), *args]).exit_code != 0
    with Session(engine) as session:
        a = services.get_application(session, app_id)
        assert a.company == "Acme" and len(a.events) == 1

@pytest.mark.parametrize("selection", ["1\n1\nNew\n", "2\nrole\n", "3\n1\n", "4\n", "5\nnote\n", "6\n1\n"])
def test_guided_update(cli_db, selection):
    _, app_id = cli_db
    result = CliRunner().invoke(cli.app, ["update"], input=f"{app_id}\n{selection}")
    assert result.exit_code == 0, result.output


def test_clear_notes(cli_db):
    _, app_id = cli_db
    runner = CliRunner()
    assert runner.invoke(cli.app, ["update", str(app_id), "--notes", "x"]).exit_code == 0
    assert runner.invoke(cli.app, ["update", str(app_id), "--clear-notes"]).exit_code == 0


def test_read_export_db_add(cli_db, tmp_path):
    runner = CliRunner()
    for args in (["list", "--company", "acme"], ["show", "1"], ["db"],
                 ["export", str(tmp_path / "export.xlsx"), "--company", "acme"]):
        result = runner.invoke(cli.app, args)
        assert result.exit_code == 0, result.output
    result = runner.invoke(cli.app, ["add"], input="Other\nEngineer\n6\n\n3\n1\n2\n2026-10-01\n\n\n")
    assert result.exit_code == 0, result.output

@pytest.mark.parametrize("args", [["show", "0"], ["show", "999"], ["update", "999", "--interview"]])
def test_missing_or_invalid_id(cli_db, args):
    result = CliRunner().invoke(cli.app, args)
    assert result.exit_code == 1
    assert "positive integer" in result.output or "not found" in result.output
