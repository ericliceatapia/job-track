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
    update_application,
    export_application_data,
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
        try:
            application = get_application(session, application_id)
        except ValueError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(code=1)

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
            Text(application.notes or "No role notes yet. Use jt update to add them."),
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
        for event in application.events:
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
def update(
    application_id: Annotated[int | None, typer.Argument(help="Application ID; prompts if omitted.")] = None,
    company: str | None = None,
    role_title: str | None = None,
    category: str | None = None,
    location: str | None = None,
    work_modality: str | None = None,
    job_type: str | None = None,
    source: str | None = None,
    application_date: Annotated[str | None, typer.Option(help="Correct metadata date (YYYY-MM-DD); preserves history.")] = None,
    job_id: str | None = None,
    notes: Annotated[str | None, typer.Option(help="Replace role notes.")] = None,
    clear_notes: bool = False,
    clear_location: bool = False,
    clear_job_id: bool = False,
    oa: Annotated[str | None, typer.Option(help="Assessment received or completed.")] = None,
    interview: bool = False,
    activity_note: str | None = None,
    status: str | None = None,
    event_date: Annotated[str | None, typer.Option(help="New event date (YYYY-MM-DD), default today.")] = None,
) -> None:
    """Update metadata, notes, assessments, interviews, or status atomically."""
    metadata = {key: value for key, value in {
        "company": company, "role_title": role_title, "category": category,
        "location": location, "work_modality": work_modality, "job_type": job_type,
        "source": source, "job_id": job_id, "notes": notes,
    }.items() if value is not None}
    for key, clear in (("notes", clear_notes), ("location", clear_location), ("job_id", clear_job_id)):
        if clear:
            if key in metadata:
                raise typer.BadParameter(f"Use either --{key.replace('_', '-')} or --clear-{key.replace('_', '-')}.")
            metadata[key] = None
    if application_date is not None:
        metadata["application_date"] = parse_date(application_date)
    day = parse_date(event_date) if event_date is not None else date.today()
    if application_id is None:
        application_id = typer.prompt("Application ID", type=int)
    if not metadata and oa is None and not interview and activity_note is None and status is None:
        action = prompt_option("Update", (
            "Application metadata", "Role notes", "Online assessment", "Interview",
            "Activity note", "Status",
        ))
        if action == "Application metadata":
            field = prompt_option("Field", (
                "company", "role_title", "category", "location", "work_modality",
                "job_type", "source", "application_date", "job_id",
            ))
            choices = {"category": VALID_CATEGORIES, "work_modality": VALID_WORK_MODALITIES,
                       "job_type": VALID_JOB_TYPES, "source": VALID_SOURCES}
            if field in choices:
                metadata[field] = prompt_option(field.replace("_", " ").title(), choices[field])
            elif field == "application_date":
                metadata[field] = prompt_date("Application date")
            elif field in ("location", "job_id"):
                metadata[field] = typer.prompt(f"{field} (Enter to clear)", default="", show_default=False)
            else:
                metadata[field] = prompt_required_text(field.replace("_", " ").title())
        elif action == "Role notes":
            metadata["notes"] = typer.prompt("Role notes (replaces text; Enter to clear)", default="", show_default=False)
        elif action == "Online assessment":
            oa = prompt_option("OA action", VALID_OA_ACTIONS)
        elif action == "Interview":
            interview = True
        elif action == "Activity note":
            activity_note = prompt_required_text("Activity note")
        else:
            status = prompt_option("New status", STATUS_CHANGE_OPTIONS)
    try:
        with create_session() as session:
            application = update_application(
                session, application_id, metadata=metadata, oa=oa, interview=interview,
                activity_note=activity_note, status=status, event_date=day,
            )
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Updated application #{application.id}: {application.company} - {application.role_title}")


def parse_date(value: str) -> date:
    """Parse explicit CLI dates without accepting alternate ISO formats."""
    try:
        parsed = date.fromisoformat(value)
        if value != parsed.isoformat():
            raise ValueError()
        return parsed
    except ValueError:
        raise typer.BadParameter("Invalid date. Use YYYY-MM-DD.")


@app.command("export")
def export_command(
    destination: Annotated[Path, typer.Argument(help="Output .xlsx file path.")],
    company: Annotated[str | None, typer.Option(help="Match part of a company name.")] = None,
    status: Annotated[str | None, typer.Option(help="Filter by application status.")] = None,
    category: Annotated[str | None, typer.Option(help="Filter by category.")] = None,
    overwrite: Annotated[bool, typer.Option(help="Replace an existing export file.")] = False,
) -> None:
    """Export matching applications and their complete history to Excel."""

    try:
        with create_session() as session:
            count, event_count = export_application_data(
                session, destination, company=company, status=status,
                category=category, overwrite=overwrite,
            )
    except (ValueError, OSError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Exported {count} applications and {event_count} events to {destination}.")


def main() -> None:
    app()
