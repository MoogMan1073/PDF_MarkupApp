---
tags: [audit, drc, extraction]
---

# Design Rule Check

The **Audit** tab checks a drawing set against its own conventions and lists
what to confirm: tags whose number disagrees with the sheet they sit on, wire
numbers that reference a sheet they never appear on, sections the drawing index
promises but the set does not contain, and family codes nobody has registered.

Run it with **Tools ▸ Run design rule check…** (or `F7`, or the **Run check**
button on the Audit tab).

> **It is a review, not a verdict.** Findings say *confirm this*, with the
> convention or clause they rest on. The authority having jurisdiction and the
> listing agency decide compliance — this tool never does.

## Reading the results

The line above the list is the important one:

    451 of 506 checked — 55 not checked (55 missing catalog).

**A skipped item is not a passing item.** A plotted drawing simply does not
carry some of what a rule needs, and the header says so rather than letting an
empty list look like a clean drawing. Findings come in three levels:

| Level | Means |
|---|---|
| **Definite violation** | The rule was broken and the evidence is unambiguous |
| **Potential issue** | Worth your eye; the tool may be missing context |
| **Informational** | An observation, usually a setting to adjust |

Double-click a finding to jump to it on the drawing. Each one is outlined on
the sheet, **underneath** your own markup — an audit mark can never cover
something you drew, and the eraser will not touch it.

## Cross-references between sheets

A signal leaving one sheet is marked with a connector — `to 70004`, `from
30014`, sometimes `to 70004 PG.700`. The number is a sheet-and-line reference:
`70004` is sheet 700, line 04. These come in pairs, and the pairing is what
gets checked: if sheet 300 line 14 goes **to** sheet 700 line 04, then sheet 700
line 04 should come **from** sheet 300 line 14.

Two things are reported. A connector pointing at a sheet or line that is not in
the set is the more definite of the two — it compares printed text against the
sheets you have, with nothing inferred. A connector whose counterpart is missing
or names a different line is worth confirming: the line a connector sits on is
read from the line-number gutter down the side of the sheet, and different
connector symbols place their text either side of it, so the check allows one
line of slack before it says anything.

Only ladder sheets take part. A network topology or panel layout references
other sheets by different conventions, and expecting a connector back from one
would report correct drafting as an error.

## What the title block claims

A title block states its own sheet number and the number of the sheet after it.
Both are claims, and both are checked against the set: a sheet whose title block
disagrees with its drawing number, or whose **next** pointer steps over the sheet
that actually follows, usually means a title block was copied from a neighbour
and only half updated.

## Waiving a finding

Every real panel has justified exceptions. Right-click a finding ▸ **Waive…**,
give a reason and your name, and it stays on the list struck through, so the
decision stays visible to the next reviewer.

Waivers are stored per project and **survive re-running the check**. They are
keyed to the finding itself rather than to where it sits, so re-extracting the
drawing or nudging a tag in a revision does not lose them.

## What the rules need

Some rules depend on data a plot does not contain — a device's catalog number,
a conductor's size. Those report as *not checked* rather than as clean, and the
coverage table in the exported report names them one by one.

Two pieces of per-sheet information do most of the work, and both are editable:

- **Sheet number** — read from the drawing number in the title block. Where the
  drawing does not say, the Sheet column stays blank and location rules skip
  that page rather than guess.
- **Sheet role** — whether a page is a schematic, a PLC I/O sheet, a panel
  layout, a terminal-block detail, and so on. This matters more than it sounds:
  a panel layout labels every device with the schematic sheet it comes from, so
  *every* tag on it is legitimately "off-sheet". Location rules only apply where
  the comparison means something.

## Settings

**[[Settings]] ▸ Design rules** lists every rule, with a checkbox to turn one
off and a severity you can override. Changes apply to the findings already on
screen — no need to run the check again to see the effect.

## Exporting

**Export report…** writes HTML, Markdown or CSV. All three carry the findings,
the clause each rests on, the evidence behind it, and the coverage statement.

## Related

- [[Component Labels]] — the tags the audit checks
- [[Wire Numbers]] — the conductors the audit checks
- [[Settings]] — rule selection and severities
- [[Storage and Files]] — where findings and waivers are kept

#audit
