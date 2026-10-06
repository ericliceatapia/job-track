import typer

app = typer.Typer()


@app.command()
def hello() -> None:
    """Verify that JobTrack is running."""
    typer.echo("JobTrack is running.")


def main() -> None:
    app()