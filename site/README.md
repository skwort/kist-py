# Documentation Site

Source for [kist.sh](https://kist.sh), built with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

## Local preview

```
mkdocs serve
```

## Screenshots

The landing page uses SVG screenshots captured from the TUI via
`scripts/screenshot.py`. The script spins up a temporary library with
demo parts and exports Textual's SVG renderer output.

```bash
# Browse screen (default)
uv run python scripts/screenshot.py

# Detail modal
uv run python scripts/screenshot.py --screen detail

# Custom terminal size
uv run python scripts/screenshot.py --screen browse --size 140x40

# Specific output path
uv run python scripts/screenshot.py --screen detail --output /tmp/shot.svg
```

Available screens: `browse`, `detail`, `add`.

Screenshots are saved to `site/assets/<screen>-screenshot.svg` by default.
The `--part` flag selects which part to open in the detail view
(default: `IC-STM32F405RGT6-LQFP64`).
