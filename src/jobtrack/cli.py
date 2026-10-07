from datetime import date

import typer

from jobtrack.database import (
    create_session,
    get_database_path,
    initialize_database,
)
from jobtrack.services import (
    create_application,
    list_applications,
)


app = typer.Typer()


@app.command()
def hello() -> None:
    """Verify that JobTrack is running."""
    typer.echo("JobTrack is running.")


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

    session = create_session()

    try:
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

    finally:
        session.close()

    typer.echo()
    typer.echo(
        f"Added application #{application_id}: "
        f"{application_company} - {application_role}"
    )


@app.command("list")
def list_command() -> None:
    """List job applications."""
    session = create_session()

    try:
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

    finally:
        session.close()


def main() -> None:
    app()
