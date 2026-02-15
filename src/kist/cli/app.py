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
        from kist.tui.app import run_tui

        run_tui()
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
    no_tui: bool = typer.Option(
        False, "--no-tui", help="Skip interactive wizard, use CLI defaults."
    ),
) -> None:
    """Initialise a new kist parts library."""
    import sys

    if not no_tui and sys.stdin.isatty():
        from kist.tui.app import run_tui

        run_tui(start_screen="init", init_path=path)
        return

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
def add(
    url_or_mpn: str | None = typer.Argument(None, help="URL or MPN to fetch."),
) -> None:
    """Add a part to the library."""
    from kist.tui.app import run_tui

    run_tui(start_screen="add", url_or_mpn=url_or_mpn)


@app.command()
def search(
    query: str = typer.Argument(help="Search term."),
) -> None:
    """Search for parts in the library."""
    from rich.console import Console
    from rich.table import Table

    from kist.core.database import PartsDatabase
    from kist.core.library import find_library
    from kist.errors import LibraryNotFoundError

    try:
        result = find_library()
    except LibraryNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None

    db = PartsDatabase(result.library_root / "parts.json")
    db.load()
    results = db.search(query)

    if not results:
        typer.echo("No parts found.")
        raise typer.Exit()

    table = Table(show_header=True)
    table.add_column("Name")
    table.add_column("Tier")
    table.add_column("Category")
    table.add_column("Description")

    for part in results:
        table.add_row(part.name, part.tier, part.category, part.description)

    Console().print(table)


@app.command()
def check() -> None:
    """Validate part names and check for duplicates."""
    from kist.core.check import check_library
    from kist.core.config import load_library_config
    from kist.core.database import PartsDatabase
    from kist.core.library import find_library
    from kist.errors import LibraryNotFoundError

    try:
        result = find_library()
    except LibraryNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None

    config = load_library_config(result.library_root)
    db = PartsDatabase(result.library_root / "parts.json")
    db.load()

    if not db.list_parts():
        typer.echo("No parts to check.")
        raise typer.Exit()

    typer.echo(f"Checking {len(db.list_parts())} parts...")

    issues = check_library(db, config)

    for issue in issues:
        if issue.kind == "name_drift":
            typer.echo(f"  Name mismatch: {issue.message}")
        elif issue.kind == "duplicate_identity":
            typer.echo(f"  Duplicate identity: {issue.message}")

    if issues:
        typer.echo(f"\n{len(issues)} issue(s) found.")
        raise typer.Exit(code=1)

    typer.echo("All clean.")


@app.command()
def sync() -> None:
    """Sync KiCad symbol files and lib tables with the parts database."""
    from kist.core.config import load_library_config
    from kist.core.database import PartsDatabase
    from kist.core.library import find_library
    from kist.core.sync import sync_sym_lib_table, sync_symbols
    from kist.errors import LibraryNotFoundError

    try:
        result = find_library()
    except LibraryNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None

    config = load_library_config(result.library_root)
    db = PartsDatabase(result.library_root / "parts.json")
    db.load()

    symbol_files = sync_symbols(result.library_root, db, config)
    typer.echo(f"Synced {len(symbol_files)} symbol libraries.")

    if result.project_dir:
        sync_sym_lib_table(result.project_dir, symbol_files, config)
        typer.echo(f"Updated sym-lib-table in {result.project_dir}")
    else:
        typer.echo("No project directory found; skipped sym-lib-table.")
