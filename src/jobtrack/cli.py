import typer

from jobtrack.database import create_database_engine, get_database_path


app = typer.Typer()


@app.command()
def hello() -> None:
    """Verify that JobTrack is running."""
    typer.echo("JobTrack is running.")


@app.command()
def db() -> None:
    """Verify the database connection."""
    engine = create_database_engine()

    with engine.connect():
        typer.echo(f"Connected to database: {get_database_path()}")


def main() -> None:
    app()
