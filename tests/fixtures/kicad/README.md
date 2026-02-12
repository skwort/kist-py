# KiCad test fixtures

Pristine `.kicad_sym` files copied from the system KiCad 9.0.5
installation.  Used for round-trip and snapshot testing of the
S-expression parser/writer.

## Source

```
/nix/store/lfwg5vggjc0maapn2q3hf1wkn07wx7q8-kicad-symbols-884133df0a/share/kicad/symbols/
```

KiCad symbols package version `884133df0a`, installed via Nix.

## Files

| File | Source | Notes |
|------|--------|-------|
| `Regulator_Current.kicad_sym` | Copied verbatim | 2 symbols, 209 lines |
| `Transistor_IGBT.kicad_sym` | Copied verbatim | 2 symbols, 595 lines |
| `power.kicad_sym` | Copied verbatim | 101 symbols, exercises `#`-prefixed values |
| `Device_RCL.kicad_sym` | Header + R/C/L symbols extracted from `Device.kicad_sym` | Raw lines, no reformatting |

## Do not edit

These files must stay as KiCad wrote them.  The snapshot tests pin our
writer output against these inputs -- modifying the fixtures invalidates
the snapshots.
