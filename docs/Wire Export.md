---
tags: [wire, export]
---

# Wire Export

From the [[Wire Numbers]] tab, click **Export…**. Output is `.xlsx` or `.csv`.

## Two modes

- **Single file (`~sheet~`)** — all labels in one file, with a separator row
  before each sheet's labels using the form `~300~`. Defaults to **labels-only**
  (one column of repeated label strings) — exactly what a wire-label printer
  wants.
- **Per-sheet files** — one file per sheet (`WIRES_300.xlsx`, `WIRES_301.xlsx`,
  …) into a folder you choose. Defaults to the **full column set**:
  `Label | Sheet | Rung | WireIdx | Type | Page | Source`.

Tick **Labels only** to force single-column output in either mode.

## Options

- **Labels/wire** — how many times each label is repeated (default **2**), for
  printing multiple physical tags per wire.
- **Sort**:
  - *Numerical* — by sheet, then rung, then wire index.
  - *In drawing order* — spatial reading order (top-to-bottom by rung,
    left-to-right within a rung).
  - *By sheet* — grouped by sheet.
- **Dedupe** — collapse identical labels (on by default).
- **Show** filters (Conforming / Fixed-OEM / Jumpers) and the **✓** include
  toggles from the table are all honoured.

Defaults for mode, format, sort and labels-per-wire come from [[Settings]].

#export #wire
