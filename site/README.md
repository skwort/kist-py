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

Available screens: `browse`, `detail`, `add`, `init`, `symbol-search`,
`footprint-search`.

Screenshots are saved to `site/assets/<screen>-screenshot.svg` by default.
The `--part` flag selects which part to open in the detail view
(default: `IC-STM32F405RGT6`).


## GIFs

Follow the steps below to generate GIFs.

1. Launch kitty (fixed size: 120x34)

```bash
kitty \
  -o remember_window_size=no \
  -o initial_window_width=120c \
  -o initial_window_height=34c \
  uv run python scripts/demo.py
````

2. Record with wf-recorder (force true RGB to preserve colours)

```bash
wf-recorder -g "$(slurp)" \
  --codec libx264rgb \
  --pixel-format rgb24 \
  -r 30 \
  -f tui.mp4
```

`libx264rgb + rgb24` avoids YUV color subsampling and preserves terminal colours.

3. Generate GIF palette

```bash
ffmpeg -i tui.mp4 \
  -filter_complex "fps=15,palettegen=stats_mode=diff" \
  palette.png
```

4. Generate GIF using the palette

```bash
ffmpeg -i tui.mp4 -i palette.png \
  -filter_complex "fps=15[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" \
  tui.gif
```

