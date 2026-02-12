"""kist CLI entrypoint."""

from pathlib import Path

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
def init(
    path: Path = typer.Option(
        ".", "--path", "-p", help="Directory to initialise (default: cwd)."
    ),
    symbols_dir: str | None = typer.Option(
        None, "--symbols-dir", help="Symbol library directory name."
    ),
    footprints_dir: str | None = typer.Option(
        None, "--footprints-dir", help="Footprint library directory name."
    ),
    models_dir: str | None = typer.Option(
        None, "--models-dir", help="3D model directory name."
    ),
    blocks_dir: str | None = typer.Option(
        None, "--blocks-dir", help="Design blocks directory name."
    ),
) -> None:
    """Initialise a new kist parts library."""
    from kist.core.library import init_library
    from kist.errors import LibraryExistsError

    try:
        root = init_library(
            path,
            symbols_dir=symbols_dir,
            footprints_dir=footprints_dir,
            models_dir=models_dir,
            blocks_dir=blocks_dir,
        )
        typer.echo(f"Initialised kist library at {root}")
    except LibraryExistsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None


@app.command()
def link(
    library: Path = typer.Argument(help="Path to an existing kist library."),
    path: Path = typer.Option(
        ".", "--path", "-p", help="Project directory to link from (default: cwd)."
    ),
) -> None:
    """Link a project directory to an existing kist library."""
    from kist.core.library import link_library
    from kist.errors import LibraryExistsError, LibraryNotFoundError

    try:
        ref_path = link_library(path, library)
        typer.echo(f"Linked to library via {ref_path}")
    except (LibraryNotFoundError, LibraryExistsError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None


@app.command()
def add() -> None:
    """Add a part to the library."""
    typer.echo("Not yet implemented.")


@app.command()
def search() -> None:
    """Search for parts in the library."""
    typer.echo("Not yet implemented.")
