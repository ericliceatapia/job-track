from datetime import date
from typing import Annotated

import typer

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
from jobtrack.rules import (
    VALID_CATEGORIES,
    VALID_JOB_TYPES,
    VALID_SOURCES,
    VALID_WORK_MODALITIES,
    STATUS_CHANGE_OPTIONS,
    VALID_OA_ACTIONS,
)


app = typer.Typer()


def prompt_option(
    label: str,
    options: tuple[str, ...],
) -> str:
    """Prompt the user to select an option from a numbered list."""

    typer.echo()
    typer.echo(label)

    for index, option in enumerate(options, start=1):
        typer.echo(f"{index}. {option}")

    while True:
        selection = typer.prompt(
            f"Select [1-{len(options)}]"
        )

        try:
            index = int(selection)
        except ValueError:
            typer.echo(
                "Enter a number.",
                err=True,
            )
            continue

        if 1 <= index <= len(options):
            return options[index - 1]

        typer.echo(
            f"Enter a number from 1 to {len(options)}.",
            err=True,
        )


def prompt_required_text(label: str) -> str:
    """Prompt until non-empty text is entered."""

    while True:
        value = typer.prompt(label).strip()

        if value:
            return value

        typer.echo(
            f"{label} cannot be empty.",
            err=True,
        )


def prompt_optional_text(label: str) -> str | None:
    """Prompt for optional text."""

    value = typer.prompt(
        label,
        default="",
        show_default=False,
    ).strip()

    return value or None


def prompt_date(
    label: str,
    default: date | None = None,
) -> date:
    """Prompt until a valid ISO date is entered."""

    default_date = default or date.today()

    while True:
        value = typer.prompt(
            label,
            default=default_date.isoformat(),
        ).strip()

        try:
            parsed_date = date.fromisoformat(value)
            if value != parsed_date.isoformat():
                raise ValueError("Use YYYY-MM-DD.")
            return parsed_date
        except ValueError:
            typer.echo(
                "Invalid date. Use YYYY-MM-DD.",
                err=True,
            )


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

    company = prompt_required_text("Company")
    role_title = prompt_required_text("Role title")

    category = prompt_option(
        "Category",
        VALID_CATEGORIES,
    )

    location = prompt_optional_text("Location")

    work_modality = prompt_option(
        "Work modality",
        VALID_WORK_MODALITIES,
    )

    job_type = prompt_option(
        "Job type",
        VALID_JOB_TYPES,
    )

    source = prompt_option(
        "Source",
        VALID_SOURCES,
    )

    application_date = prompt_date("Application date")

    job_id = prompt_optional_text("Job ID")
    notes = prompt_optional_text("Notes")

    try:
        with create_session() as session:
            application = create_application(
                session,
                company=company,
                role_title=role_title,
                category=category,
                location=location,
                work_modality=work_modality,
                job_type=job_type,
                source=source,
                application_date=application_date,
                job_id=job_id,
                notes=notes,
            )

            application_id = application.id
            application_company = application.company
            application_role = application.role_title

    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)

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
        application = get_application(
            session,
            application_id,
        )

        if application is None:
            typer.echo(
                f"Application #{application_id} not found.",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo(
            f"{application.company} - "
            f"{application.role_title}"
        )
        typer.echo()

        typer.echo(f"ID:               {application.id}")
        typer.echo(f"Status:           {application.status}")
        typer.echo(f"Category:         {application.category}")
        typer.echo(
            f"Location:         "
            f"{application.location or '--'}"
        )
        typer.echo(
            f"Work modality:    "
            f"{application.work_modality}"
        )
        typer.echo(f"Job type:         {application.job_type}")
        typer.echo(f"Source:           {application.source}")
        typer.echo(
            f"Application date: "
            f"{application.application_date}"
        )
        typer.echo(
            f"Job ID:           "
            f"{application.job_id or '--'}"
        )
        typer.echo(
            f"Notes:            "
            f"{application.notes or '--'}"
        )

        typer.echo()
        typer.echo("History")

        if not application.events:
            typer.echo("No events recorded.")
            return

        for event in sorted(
            application.events,
            key=lambda event: (
                event.event_date,
                event.id,
            ),
        ):
            event_description = event.event_type

            if (
                event.old_value is not None
                or event.new_value is not None
            ):
                event_description += (
                    f" | {event.old_value or '--'}"
                    f" -> {event.new_value or '--'}"
                )

            if event.notes:
                event_description += (
                    f" | {event.notes}"
                )

            typer.echo(
                f"{event.event_date} | "
                f"{event_description}"
            )


@app.command()
def status(
    application_id: int,
    new_status: Annotated[str | None, typer.Argument()] = None,
) -> None:
    """Change an application's status."""

    if new_status is None:
        new_status = prompt_option(
            "New status",
            STATUS_CHANGE_OPTIONS,
        )

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

    typer.echo()
    typer.echo(
        f"Updated #{application_id}: "
        f"{application_company} - {application_role}"
    )
    typer.echo(f"Status: {application_status}")


@app.command()
def oa(
    application_id: int,
    action: Annotated[str | None, typer.Argument()] = None,
) -> None:
    """Record an OA as received or completed."""

    if action is None:
        action = prompt_option(
            "OA action",
            VALID_OA_ACTIONS,
        )

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

    typer.echo()
    typer.echo(
        f"Recorded {event_type} for application "
        f"#{application_id}."
    )


@app.command()
def interview(
    application_id: int,
    notes: str | None = None,
) -> None:
    """Record an interview for an application."""

    if notes is None:
        notes = prompt_optional_text(
            "Interview notes"
        )

    try:
        with create_session() as session:
            event = record_interview(
                session,
                application_id=application_id,
                event_date=date.today(),
                notes=notes,
            )

            interview_date = event.event_date
            notes = event.notes

    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)

    typer.echo()
    typer.echo(
        f"Recorded interview for application "
        f"#{application_id} on {interview_date}."
    )

    if notes:
        typer.echo(f"Notes: {notes}")


def main() -> None:
    app()
