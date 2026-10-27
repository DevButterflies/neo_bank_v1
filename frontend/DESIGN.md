---
name: NeoBank Admin
description: An operator console that reads lending as a transit line of pillar-coloured segments and stations.
colors:
  enamel-ground: "#f7f7f4"
  surface-white: "#ffffff"
  ink: "#161616"
  ink-soft: "#3d3d39"
  mute: "#5f5f59"
  rule: "#dcdcd4"
  rule-strong: "#b9b9b0"
  wash: "#efefe9"
  intake-blue: "#1f4fa0"
  credit-green: "#14917d"
  execution-amber: "#e2a21b"
  prudential-red: "#d03a3a"
  credit-green-text: "#0c6b5c"
  execution-amber-text: "#8a5a00"
  prudential-red-text: "#b02a2a"
  flash: "#fff1c2"
typography:
  display:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 800
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  label:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 700
    letterSpacing: "0.01em"
  micro:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 700
rounded:
  base: "2px"
  stroke: "5px"
  pill: "999px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "5": "24px"
  "6": "32px"
  "7": "48px"
  gutter: "clamp(16px, 2.2vw, 32px)"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface-white}"
    typography: "{typography.label}"
    rounded: "{rounded.base}"
    padding: "0 16px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.ink-soft}"
  button-secondary:
    backgroundColor: "{colors.surface-white}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.base}"
    padding: "0 16px"
    height: "36px"
  button-secondary-hover:
    backgroundColor: "{colors.wash}"
  button-danger:
    backgroundColor: "{colors.surface-white}"
    textColor: "{colors.prudential-red-text}"
    rounded: "{rounded.base}"
    padding: "0 16px"
    height: "36px"
  button-small:
    padding: "0 12px"
    height: "30px"
  input-field:
    backgroundColor: "{colors.surface-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "8px 12px"
    height: "38px"
  top-bar:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface-white}"
    height: "56px"
  count-badge:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface-white}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  card:
    backgroundColor: "{colors.surface-white}"
    rounded: "{rounded.base}"
    padding: "16px 24px"
  choice-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface-white}"
    rounded: "{rounded.base}"
    height: "32px"
  sheet:
    backgroundColor: "{colors.surface-white}"
    width: "min(440px, 100%)"
---

# Design System: NeoBank Admin

## Overview

**Creative North Star: "Transit Line"**

The lending book is a route, not a board of floating cards. Every lifecycle (the origination pipeline, the facility states, the audit trail) is drawn as a modernist transit diagram: thick round-capped line strokes in the colour of the pillar that owns that stretch, ink-ringed station marks, a spur for the branch that leaves the line, and a stop bar where it ends. Everything around the line is quiet: a white enamel ground, ink type, hairline rules and near-square white surfaces, so the four pillar colours are the only saturated thing on screen and always mean "which pillar owns this".

Density is operator density. Archivo carries everything, heavy (800) for station names and headings, tabular figures in every number column, 13px labels and 15px body. The ink top bar is the one dark mass; below it the page is flat paper. Depth exists only for the sheet that slides over the page. A frozen line is shown rather than hidden: a Pillar 4 veto hatches the segment it blocks and names itself in words.

**Key Characteristics:**
- Lifecycles drawn as lines with stations, spurs and stop bars, coloured by owning pillar.
- Enamel ground, ink type, white near-square surfaces (2px), hairline rules.
- Archivo 400/600/700/800 only, tabular figures by default.
- One ink top bar; flat page; a single soft shadow reserved for sheets.
- Risk and state are never colour-only: every state carries a mark shape and a word.

## Colors

A neutral enamel-and-ink field with four pillar line colours, each paired with a darker text variant.

### Primary
- **Ink** (#161616): all text, the top bar, primary buttons, station rings, count badges, the selected choice, the table header rule. Ink is the system's accent; it is what "selected" and "current" look like.

### Secondary (pillar lines)
- **Intake Blue** (#1f4fa0): the officer-approval segment of the origination line; also the focus-ring colour (`--focus`).
- **Credit Green** (#14917d): the Pillar 2 credit-scoring segment; the green decisioning zone dot.
- **Execution Amber** (#e2a21b): Pillar 3 disbursement and repayment segments, the whole facility line, delinquent/recovery/restructured status marks, Stage 2 tiles, the audit-trail stroke.
- **Prudential Red** (#d03a3a): Pillar 4: veto hatching, the Rejected spur, defaulted marks, breached meter fills, blocked gates, alert borders.

### Tertiary (pillar text)
- **Credit Green Text** (#0c6b5c), **Execution Amber Text** (#8a5a00), **Prudential Red Text** (#b02a2a): the same pillars when they carry words on white (segment labels, "Rejected", "Blocked", negative figures, danger buttons, Stage 2/3 labels). Intake Blue is dark enough to carry its own text.

### Neutral
- **Enamel Ground** (#f7f7f4): page background.
- **Surface White** (#ffffff): every card, table, band, tile, sheet and input.
- **Ink Soft** (#3d3d39): secondary text, table header labels, primary-button hover, bar fills.
- **Mute** (#5f5f59): meta lines, hints, tile labels, struck values.
- **Rule** (#dcdcd4): hairline borders on cards and rows, table row dividers.
- **Rule Strong** (#b9b9b0): hover borders, input strokes, disabled button borders, dashed empty states.
- **Wash** (#efefe9): secondary-button hover, meter track, current table row.
- **Flash** (#fff1c2): one-shot background on a row that moved after a monthly tick, fading to white over 1400ms.

On the ink top bar, text and controls use warm greys tuned for the dark ground (nav #c9c9c1, sub-brand #b8b8b0, outline #8b8b84, hover fill #2b2b28); the data-source dot is green (#3fc9a8) live, amber (#f0b53a) demo.

### Named Rules
**The Owner's Colour Rule.** A pillar colour appears only where that pillar owns the stage or the risk. It is never decoration, never a category palette, never a button fill.

**The Text Variant Rule.** Line colours fill strokes and dots; when a pillar colour must carry text on white, use its -text variant (Intake Blue excepted).

**The Never Colour-Only Rule.** Every risk or state carries a shape (ring, dot, stop bar, hatch) and a word or icon alongside its colour.

## Typography

**Display Font:** Archivo (with system-ui, sans-serif), self-hosted via @fontsource at 400, 600, 700, 800.

**Character:** One grotesque doing all the work, like transit signage: heavy, slightly tightened names over plain, steady body text. Numbers are tabular everywhere they stack; large single figures (meter values, tile values, recon totals) switch to proportional.

### Hierarchy
- **Display** (800, 2rem, 1.1, -0.02em): the page title in each area's head; large meter values.
- **Headline** (800, 1.5rem, 1.15, -0.015em): sheet titles, tile and recon values, stage counts.
- **Title** (800, 1.125rem, -0.01em): station names on the route map, section titles, card titles, the brand.
- **Body** (400, 0.9375rem, 1.45, tabular): default text and row names (row names at 700).
- **Label** (700, 0.8125rem): buttons, nav, form labels, table cells, segmented controls, count badges.
- **Micro** (700, 12px): segment labels, zone and frozen marks, table header labels, tile labels, meta lines (meta at 400 in mute).

### Named Rules
**The Heavy Station Rule.** Names of places on a line (stations, page titles, card titles) are set at 800 with slight negative tracking; nothing else is that heavy.

**The Sentence Case Rule.** All labels, headers and tile captions are sentence case at normal tracking. No uppercase label system.

## Layout

A single full-width column at a fluid gutter (clamp(16px, 2.2vw, 32px)) under a sticky 56px top bar; page padding 32px top, 48px bottom. Spacing runs on a 4px base (4, 8, 12, 16, 24, 32, 48); 24px separates major blocks, 12-16px sits inside cards.

The Pipeline opens on a white route-map band: four station cells in a four-column grid with 24px gaps, the line running through each cell at 48px, a Rejected spur dropping at 45 degrees from Scored and a Closed stop bar at the terminus. The band doubles as the status filter for the default Table layout; the Line layout hangs a list of rows under each station, aligned to the band's columns. Other areas use a compact state line (the same grammar at 8px stroke and 26px marks) above a table, three-up tiles or meters, and two-column cards.

Breakpoints: at 1100px tile rows, meters and two-column cards collapse to one column. At 860px the top bar wraps (nav on its own single row, demo controls on another), the horizontal band is replaced by a line running down the left edge with each station's rows hung off it, the compact state line becomes a two-column grid of stops without strokes, form pairs stack, and sheets cover the full viewport including the top bar.

## Elevation & Depth

Flat by default. Surfaces separate from the enamel ground by white fill and a 1px rule, never by shadow. Selection is shown with ink: a 1px inset ink ring on the current row card, a 3px inset ink bar on the left of the current table row. Depth appears once: the side sheet, which sits over a 32% ink scrim with a soft leftward shadow.

### Shadow Vocabulary
- **Sheet** (`box-shadow: -12px 0 32px rgb(22 22 22 / 0.16)`): only on the side sheet over its scrim.
- **Current row** (`box-shadow: inset 0 0 0 1px #161616` on cards; `inset 3px 0 0 #161616` on table rows): a selection stroke, not elevation.

### Named Rules
**The Flat Paper Rule.** Nothing on the page casts a shadow. The sheet is the only lifted layer, and it always brings a scrim.

## Shapes

Near-square surfaces (2px radius) for every card, row, input, button, tile and chip. Round geometry is reserved for the transit vocabulary: circular station marks, fully round-capped line strokes (radius half the stroke: 5px on the 10px line, 4px on the 8px line), pill count badges (999px), round zone dots. Stop bars are 6px-wide rounded bars. Borders are 1px hairlines for containers and 1.5px ink for buttons and segmented controls; the table header and footer sit on 2px ink rules.

**The Ring Means Station Rule.** A hollow ink ring is only ever a station. Empty station: white centre in a 6px ink ring. Occupied: ink centre inside a thin white inner ring. Zone marks are solid 9px dots, rejected and closed are stop bars, so no other element may borrow the ring.

## Components

### Buttons
Firm, ink-outlined, compact.
- **Shape:** near-square (2px), 1.5px ink border, 36px tall, 16px side padding; 30px and 12px when small.
- **Primary:** ink fill, white label; hover to Ink Soft. One per view region (New candidate, the sheet's main action).
- **Secondary:** white with ink border; hover to Wash.
- **Danger:** Prudential Red Text border and label on white; hover to a pale red (#fbeaea).
- **Disabled:** Rule Strong border, Mute label, not-allowed cursor.
- **On the top bar:** transparent with a warm grey outline; a destructive reset arms on first click (red outline, "Confirm reset") and disarms after 4 seconds.
- **Icons:** lucide-react at 15-16px, leading, aria-hidden.

### Segmented control and choices
- **Segmented:** a 1.5px ink outline split by ink dividers; the pressed segment fills ink. Used for the Table/Line layout switch.
- **Choice chips:** 32px, Rule Strong border, 600 label; hover to ink border; checked fills ink.

### Cards / Containers
- **Corner Style:** 2px.
- **Background:** Surface White on the enamel ground.
- **Shadow Strategy:** none (see Elevation).
- **Border:** 1px Rule; alert states swap the border to Prudential Red (status tiles, gates, balance checks), Stage 2 to Execution Amber.
- **Internal Padding:** 16px; 16px 24px on cards and bands.

### Inputs / Fields
- **Style:** white, 1px Rule Strong stroke, 2px radius, 38px tall, label above at 13px/700, hint and error below at 12px.
- **Focus:** the global 2px Intake Blue outline at 2px offset.
- **Hover:** border to Ink Soft. **Error:** Prudential Red border with a Prudential Red Text message.

### Navigation
The ink top bar: brand "NeoBank Admin" (800 with the sub-word at 500 in warm grey), five area links at 13px/600 in warm grey, white on hover; the current area turns white with a 3px white underline. Right side holds the data-source dot and label, the demo month and Advance/Reset. Below 860px the bar wraps onto three rows with the five links on one row.

### Tables
13px cells, 12px/700 Ink Soft headers on a 2px ink rule, 1px Rule row dividers, 24px outer cell padding. The whole row opens its record. Hover tints #fafaf7; current row takes Wash plus a 3px ink left bar; a moved row flashes once. Rejected or void rows strike the name and amount at 1.5px in Mute. Status cells pair a mark (occupied ring, amber or red dot, stop bar) with a 700 word.

### Route Map (signature)
The origination line as a transit diagram on a white band: stations with heavy names above, a 10px pillar-coloured segment leaving each 30px station mark, an ink pill count badge centred on each segment, the owning pillar's label below it in the -text colour. Selecting a station thickens its segment (scaleY 1.4) and dims the rest to 30%. A veto hatches the blocked segment in Prudential Red and white diagonal stripes with a red inner outline and relabels it "Suspended · Track 1 veto". A key under the band explains occupied, empty and hatched. Counts tick up when the month advances.

### State Line (signature)
The compact form of the route map for facility states: 8px segments, 26px station marks, name and count beneath each stop, a 45-degree spur for the branch state, selecting a stop filters the table.

### Sheet
The side panel every area uses: white, 420-440px wide, fixed to the right under the top bar (full viewport below 860px), with a 32% ink scrim at every width. Focus moves to the sheet title on open, Esc and scrim click close it, and focus returns to the opener. Header holds an 800 title, a muted subtitle and a 34px icon close button.

### Meters, bars and trail
- **Meter:** a ratio as a large proportional figure over an 8px Wash track with an ink fill and a 2px ink limit tick labelled above; breached meters fill Prudential Red and say so in words.
- **Buffer bars:** one series, Ink Soft fills squared on the left and rounded 4px on the right, direct-labelled, all bars on one baseline.
- **Audit trail:** a vertical 4px Execution Amber line with 18px ink-ring stops (the newest filled); veto events turn the stroke red.

## Do's and Don'ts

### Do:
- **Do** draw any lifecycle as a line: stations as ink rings, segments in the owning pillar's colour, branches as 45-degree spurs, ends as stop bars.
- **Do** use the -text variants (#0c6b5c, #8a5a00, #b02a2a) whenever a pillar colour carries words on white.
- **Do** pair every risk state with a shape and a word: the hatched segment plus "Suspended", the red stop bar plus "Rejected", the red dot plus "Defaulted".
- **Do** keep surfaces white with a 1px Rule border and a 2px radius on the enamel ground.
- **Do** open records in the side sheet over a scrim, moving focus in on open and back to the opener on close.
- **Do** keep figures tabular in columns and switch to proportional only for a single large value.

### Don't:
- **Don't** use a pillar colour for decoration, category coding or button fills.
- **Don't** reuse the hollow ink ring for anything that is not a station; zone marks are solid dots.
- **Don't** add shadows to cards, rows or tiles; the sheet is the only lifted layer.
- **Don't** round surfaces beyond 2px; roundness belongs to the line, marks and badges.
- **Don't** set labels in uppercase or tracked-out caps.
- **Don't** hide a blocked line: a veto is shown in place on the segment it suspends.
- **Don't** ship raster imagery or a second icon set; icons are lucide-react inline SVG.
