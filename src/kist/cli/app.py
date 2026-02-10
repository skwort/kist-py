"""kist CLI entrypoint."""

import typer

from kist import __version__

app = typer.Typer(
    name="kist",
    help="KiCad parts manager.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version."),
) -> None:
    """KiCad parts manager."""
    if version:
        typer.echo(f"kist {__version__}")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        # No subcommand — launch TUI
        typer.echo("TUI not yet implemented. Use --help for CLI commands.")
        raise typer.Exit()


@app.command()
def init() -> None:
    """Initialise a kist parts library in the current directory."""
    typer.echo("Not yet implemented.")


@app.command()
def add() -> None:
    """Add a part to the library."""
    typer.echo("Not yet implemented.")


@app.command()
def search() -> None:
    """Search for parts in the library."""
    typer.echo("Not yet implemented.")
