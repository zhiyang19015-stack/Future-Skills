# UI redesign v2

Screenshots of the redesign at commit `4975ea9`, taken with headless Microsoft Edge (`prefers-reduced-motion: reduce`, so the chart's grow-in animation is off). The `00-before-*` shots are `origin/main` at `3b14d6c` (PR #8), run locally on the same data.

| File | What |
|---|---|
| `00-before-home-1440`, `00-before-matches-1440`, `00-before-home-390` | Before: top navigation, one column of cards |
| `01`–`15` | Every page at 1440 px, light (full page); `02` dark; `03` Chinese; `07` Matches dark + Chinese |
| `16-radar-900-tablet` | Tablet: the sidebar becomes an icon rail |
| `20`–`33` | Every page at 390 px (first screen); `21` and `24` dark; `33` the More sheet |

## What changed

- **App shell.** A left sidebar holds Home, the six steps (numbered; step 1 shows a tick once there is a profile) and the tools (Lab, Team, Sources). The content sits on an inset sheet. The top bar shows where you are, the scenario switch every page uses (slow / moderate / fast), the AI-use data month and release date (opens Sources), language and theme.
- **Context rail** (1360 px and wider, not on Home): the current scenario in words with its adoption bar, whose answers are shown (with the Fictional mark), how to read the numbers, and the data date.
- **Phones.** No sidebar; a compact top bar with the scenario switch; a bottom bar with Home, You, Radar, Matches and More (a sheet with Pathway, SDG, Futures, Lab, Team, Sources; Esc closes it).
- **Tokens.** Green-grey canvas, white sheet, deep ink, brand teal `#0b7069` (dark: `#3cc7b6`); three scenario colours (blue, teal, amber) that also differ in lightness; a six-step teal ramp for AI share. All 46 text/background pairs pass WCAG AA (check 9). Still no web fonts and no images.
- **Home.** Two-column hero: the claim and two actions on the left; on the right a bar for each of the 22 fields, its height the field's AI share from `/api/radar` (moderate), the highest labelled, the top three listed. Below it: occupations measured, the rising / steady / declining split, AI use for work and full hand-over in Malaysia, each with its source.
- **Matches.** The ranked list now comes right after the verdict; the explanations (roadmap, robust choices, field fit, UN goals) follow it. The first match is drawn in the brand colour.
- **Everywhere.** One page-header band; flatter cards; quieter tables with row hover; segmented controls; a loading skeleton.

## Not changed

The API, the hash routes, `PAGES`, the `data-act` / `data-on` / `data-in` hooks, the i18n tables and the first-time path buttons (check 10). No data is invented: the chart and the key numbers come from the API answer the page already loads.

## Not measured

How long a first-time visitor needs, and whether people find the new layout easier: neither was tested with users.
