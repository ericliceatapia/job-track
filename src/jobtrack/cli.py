import typer

from jobtrack.database import (
    get_database_path,
    initialize_database
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


def main() -> None:
    app()
