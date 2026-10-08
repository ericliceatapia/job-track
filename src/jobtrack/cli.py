from datetime import date
from pathlib import Path
from typing import Annotated

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
    edit_role_notes,
    record_note,
)
from jobtrack.rules import (
    VALID_CATEGORIES,
    VALID_JOB_TYPES,
    VALID_SOURCES,
    VALID_WORK_MODALITIES,
    STATUS_CHANGE_OPTIONS,
    VALID_OA_ACTIONS,
)


STATUS_STYLES = {
    "Applied": "blue",
    "Offer": "green",
    "Rejected": "red",
    "Withdrawn": "dim",
}


app = typer.Typer()
console = Console()


def prompt_option(
    label: str,
    options: tuple[str, ...],
) -> str:
    """Prompt the user to select an option from a numbered list."""

    console.print()
    console.print(Text(label, style="bold cyan"))

    for index, option in enumerate(options, start=1):
        choice = Text(f"  {index}. ", style="cyan")
        choice.append(option, style="default")
        console.print(choice)

    while True:
        selection = typer.prompt(
            typer.style(f"Select [1-{len(options)}]", fg=typer.colors.CYAN, bold=True)
        )

        try:
            index = int(selection)
        except ValueError:
            typer.echo(
                typer.style("Enter a number.", fg=typer.colors.RED),
                err=True,
            )
            continue

        if 1 <= index <= len(options):
            return options[index - 1]

        typer.echo(
            typer.style(
                f"Enter a number from 1 to {len(options)}.",
                fg=typer.colors.RED,
            ),
            err=True,
        )


def prompt_required_text(label: str) -> str:
    """Prompt until non-empty text is entered."""

    while True:
        value = typer.prompt(
            typer.style(label, fg=typer.colors.CYAN, bold=True)
        ).strip()

        if value:
            return value

        typer.echo(
            typer.style(f"{label} cannot be empty.", fg=typer.colors.RED),
            err=True,
        )


def prompt_optional_text(label: str) -> str | None:
    """Prompt for optional text."""

    value = typer.prompt(
        typer.style(label, fg=typer.colors.CYAN, bold=True)
        + typer.style(" (Enter to skip)", dim=True),
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
            typer.style(label, fg=typer.colors.CYAN, bold=True)
            + typer.style(" (YYYY-MM-DD)", dim=True),
            default=default_date.isoformat(),
        ).strip()

        try:
            parsed_date = date.fromisoformat(value)
            if value != parsed_date.isoformat():
                raise ValueError("Use YYYY-MM-DD.")
            return parsed_date
        except ValueError:
            typer.echo(
                typer.style("Invalid date. Use YYYY-MM-DD.", fg=typer.colors.RED),
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

    console.print("Add Application", style="bold cyan")
    console.print("Choose numbered options; press Enter to skip optional fields.", style="dim")
    console.print()

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
    notes = prompt_optional_text("Role notes")

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
def list_command(
    company: Annotated[str | None, typer.Option(
        "--company", help="Match part of a company name, ignoring case.",
    )] = None,
    status: Annotated[str | None, typer.Option(
        "--status", help="Filter by Applied, Offer, Rejected, or Withdrawn.",
    )] = None,
    category: Annotated[str | None, typer.Option(
        "--category", help="Filter by a category, such as Analytics or Software.",
    )] = None,
) -> None:
    """List applications. Combine filters to narrow the results."""

    with create_session() as session:
        try:
            applications = list_applications(
                session, company=company, status=status, category=category,
            )
        except ValueError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(code=1)

        filtered = any(value is not None for value in (company, status, category))
        if not applications and filtered:
            console.print("No applications match these filters.", style="dim")
            return

        if not applications:
            console.print(
                "No applications yet. Run jt add to create one.",
                markup=False,
            )
            return

        table = Table(
            title="Applications",
            caption=f"{len(applications)} matching application(s)" if filtered else f"{len(applications)} application(s)",
            show_lines=True,
            expand=True,
        )
        table.add_column("ID", justify="right", no_wrap=True)
        table.add_column("Applied", no_wrap=True)
        table.add_column("Company", ratio=2)
        table.add_column("Role", ratio=3)
        table.add_column("Location")
        table.add_column("Status", no_wrap=True)

        for application in applications:
            table.add_row(
                Text(str(application.id)),
                Text(application.application_date.isoformat()),
                Text(application.company),
                Text(application.role_title),
                Text(application.location or "--"),
                Text(
                    application.status,
                    style=STATUS_STYLES.get(application.status, ""),
                ),
            )

        console.print(table)


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

        status_style = STATUS_STYLES.get(application.status, "")
        heading = Text()
        heading.append(application.company, style="bold")
        heading.append(f"\n{application.role_title}")
        heading.append("\n\nStatus: ", style="dim")
        heading.append(application.status, style=status_style)
        console.print(Panel(
            heading,
            title=f"Application #{application.id}",
            title_align="left",
            border_style=status_style or "dim",
        ))
        console.print()

        details = Table.grid(padding=(0, 4))
        details.add_column(style="dim", no_wrap=True)
        details.add_column(overflow="fold")
        for label, value in (
            ("Category", application.category),
            ("Location", application.location or "--"),
            ("Work modality", application.work_modality),
            ("Job type", application.job_type),
            ("Source", application.source),
            ("Applied", application.application_date.isoformat()),
            ("Job ID", application.job_id or "--"),
            ("Created", application.created_at.strftime("%Y-%m-%d %H:%M:%S")),
            ("Last updated", application.updated_at.strftime("%Y-%m-%d %H:%M:%S")),
        ):
            details.add_row(label, Text(value))
        console.print(details)
        console.print()
        console.print(Panel(
            Text(application.notes or "No role notes yet. Use jt edit to add them."),
            title="Role notes",
            title_align="left",
            border_style="dim",
        ))

        console.print()
        console.print("History", style="bold")
        if not application.events:
            console.print("No events recorded.", style="dim")
            return

        event_labels = {
            "APPLICATION_CREATED": "Application created",
            "STATUS_CHANGED": "Status changed",
            "OA_RECEIVED": "OA received",
            "OA_COMPLETED": "OA completed",
            "INTERVIEW": "Interview",
            "NOTE_ADDED": "Note added",
        }
        history = Table.grid(padding=(0, 4))
        history.add_column(style="dim", no_wrap=True)
        history.add_column(overflow="fold")
        for event in sorted(
            application.events,
            key=lambda event: (event.event_date, event.id),
        ):
            description = Text(
                event_labels.get(event.event_type, event.event_type),
                style="bold",
            )
            if event.old_value is not None or event.new_value is not None:
                description.append("\n")
                description.append(
                    event.old_value or "--",
                    style=STATUS_STYLES.get(event.old_value, ""),
                )
                description.append(" -> ")
                description.append(
                    event.new_value or "--",
                    style=STATUS_STYLES.get(event.new_value, ""),
                )
            if event.event_type == "NOTE_ADDED" and event.notes:
                description.append(f"\n{event.notes}")
            history.add_row(Text(event.event_date.isoformat()), description)
        console.print(history)


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
) -> None:
    """Record an interview for an application."""

    try:
        with create_session() as session:
            event = record_interview(
                session,
                application_id=application_id,
                event_date=date.today(),
            )

            interview_date = event.event_date

    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)

    typer.echo()
    typer.echo(
        f"Recorded interview for application "
        f"#{application_id} on {interview_date}."
    )

@app.command()
def log(
    application_id: int,
    message: Annotated[str | None, typer.Argument()] = None,
) -> None:
    """Append a dated activity note to application history."""

    if message is None:
        message = prompt_required_text("Activity note")

    try:
        with create_session() as session:
            record_note(session, application_id, message, date.today())
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Added activity note to application #{application_id}.")


@app.command()
def edit(
    application_id: int,
    notes: Annotated[str | None, typer.Option(
        "--notes",
        help="Replace role notes. Use edit without options for guided input.",
    )] = None,
    clear_notes: Annotated[bool, typer.Option(
        "--clear-notes", help="Clear the role notes panel.",
    )] = False,
) -> None:
    """Edit role notes. Without options, prompt for replacement text."""

    if clear_notes and notes is not None:
        raise typer.BadParameter("Use either --notes or --clear-notes.")

    if not clear_notes and notes is None:
        notes = prompt_required_text("Role notes (replaces current text)")
    if not clear_notes and not notes.strip():
        raise typer.BadParameter("Use --clear-notes to clear role notes.")

    try:
        with create_session() as session:
            edit_role_notes(session, application_id, None if clear_notes else notes)
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)

    action = "Cleared" if clear_notes else "Updated"
    typer.echo(f"{action} role notes for application #{application_id}.")


@app.command("export")
def export_command(
    destination: Annotated[Path, typer.Argument(help="Output .xlsx file path.")],
    company: Annotated[str | None, typer.Option(help="Match part of a company name.")] = None,
    status: Annotated[str | None, typer.Option(help="Filter by application status.")] = None,
    category: Annotated[str | None, typer.Option(help="Filter by category.")] = None,
    overwrite: Annotated[bool, typer.Option(help="Replace an existing export file.")] = False,
) -> None:
    """Export matching applications and their complete history to Excel."""

    from jobtrack.exporting import export_applications

    try:
        with create_session() as session:
            applications = list_applications(
                session, company=company, status=status, category=category,
            )
            count = len(applications)
            event_count = export_applications(
                applications, destination, overwrite=overwrite,
            )
    except (ValueError, OSError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Exported {count} applications and {event_count} events to {destination}.")


def main() -> None:
    app()
