# kist

KiCad Inventory & Parts Manager. A CLI tool for managing KiCad component libraries.

## Development

Requires [Nix](https://nixos.org/) with flakes enabled.

```bash
direnv allow   # or: nix develop
uv sync --all-extras
kist --help
```

### Checks

```bash
uv run pytest                  # tests
uvx ruff check src/ tests/     # lint
uvx ty check                   # type check
```
