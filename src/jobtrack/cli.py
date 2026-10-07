import typer

from datetime import date

from jobtrack.database import (
    create_session,
    get_database_path,
    initialize_database,
)
from jobtrack.services import (
    create_application,
    list_applications,
    get_application,
    change_status,
    record_oa,
    record_interview,
)


app = typer.Typer()


@app.command()
def db() -> None:
    """Initialize the database."""
    
    initialize_database()
    typer.echo(f"Database initialized: {get_database_path()}")


@app.command()
def add() -> None:
    """Add a new job application."""

    typer.echo("Add Application")
    typer.echo()

    company = typer.prompt("Company")
    role_title = typer.prompt("Role title")
    category = typer.prompt("Category")
    location = typer.prompt("Location", default="")
    work_modality = typer.prompt("Work modality")
    job_type = typer.prompt("Job type")
    source = typer.prompt("Source")

    application_date_input = typer.prompt(
        "Application date",
        default=date.today().isoformat(),
    )

    job_id = typer.prompt("Job ID", default="")
    notes = typer.prompt("Notes", default="")

    try:
        application_date = date.fromisoformat(application_date_input)
    except ValueError:
        typer.echo(
            "Invalid application date. Use YYYY-MM-DD.",
            err=True,
        )
        raise typer.Exit(code=1)

    with create_session() as session:
        application = create_application(
            session,
            company=company,
            role_title=role_title,
            category=category,
            location=location or None,
            work_modality=work_modality,
            job_type=job_type,
            source=source,
            application_date=application_date,
            job_id=job_id or None,
            notes=notes or None,
        )

        application_id = application.id
        application_company = application.company
        application_role = application.role_title

    typer.echo()
    typer.echo(
        f"Added application #{application_id}: "
        f"{application_company} - {application_role}"
    )


@app.command("list")
def list_command() -> None:
    """List job applications."""

    with create_session() as session:
        applications = list_applications(session)

        if not applications:
            typer.echo("No applications found.")
            return

        for application in applications:
            typer.echo(
                f"#{application.id} | "
                f"{application.application_date} | "
                f"{application.company} | "
                f"{application.role_title} | "
                f"{application.status}"
            )


@app.command()
def show(application_id: int) -> None:
    """Show an application and its event history."""

    with create_session() as session:
        application = get_application(session, application_id)

        if application is None:
            typer.echo(f"Application #{application_id} not found.", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"{application.company} — {application.role_title}")
        typer.echo()
        typer.echo(f"ID:               {application.id}")
        typer.echo(f"Status:           {application.status}")
        typer.echo(f"Category:         {application.category}")
        typer.echo(f"Location:         {application.location or '--'}")
        typer.echo(f"Work modality:    {application.work_modality}")
        typer.echo(f"Job type:         {application.job_type}")
        typer.echo(f"Source:           {application.source}")
        typer.echo(f"Application date: {application.application_date}")
        typer.echo(f"Job ID:           {application.job_id or '--'}")
        typer.echo(f"Notes:            {application.notes or '--'}")

        typer.echo()
        typer.echo("History")

        if not application.events:
            typer.echo("No events recorded.")
            return

        for event in sorted(
            application.events,
            key=lambda event: (event.event_date, event.id),
        ):
            event_description = event.event_type

            if event.old_value is not None or event.new_value is not None:
                event_description += (
                    f" | {event.old_value or '--'} → {event.new_value or '--'}"
                )
                
            if event.notes:
                event_description += f" | {event.notes}"

            typer.echo(
                f"{event.event_date} | {event_description}"
            )


@app.command()
def status(
    application_id: int,
    new_status: str,
) -> None:
    """Change an application's status."""

    try:
        with create_session() as session:
            application = change_status(
                session,
                application_id=application_id,
                new_status=new_status,
                event_date=date.today(),
            )

            application_company = application.company
            application_role = application.role_title
            application_status = application.status

    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)

    typer.echo(
        f"Updated #{application_id}: "
        f"{application_company} — {application_role} → {application_status}"
    )


@app.command()
def oa(
    application_id: int,
    action: str,
) -> None:
    """Record an OA as received or completed."""

    try:
        with create_session() as session:
            event = record_oa(
                session,
                application_id=application_id,
                action=action,
                event_date=date.today(),
            )

            event_type = event.event_type

    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)

    typer.echo(
        f"Recorded {event_type} for application #{application_id}."
    )


@app.command()
def interview(
    application_id: int,
    notes: str | None = None,
) -> None:
    """Record an interview for an application."""

    try:
        with create_session() as session:
            event = record_interview(
                session,
                application_id=application_id,
                event_date=date.today(),
                notes=notes,
            )

            interview_date = event.event_date

    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)

    typer.echo(
        f"Recorded interview for application "
        f"#{application_id} on {interview_date}."
    )


def main() -> None:
    app()
