# Historical ELO visualizer v8

Version 8 is a presentation-only layer over any compatible retrospective history and
ranking output. It does not import, rerun or alter a rating engine.

## Interface

- Browse all 801 drivers in a fixed-height, scrollable index and filter it with
  accent-insensitive search.
- Select drivers from the index for comparison or open a statistics profile with
  Wikipedia biography and image enrichment.
- Plot the complete historical field by default with a stable distinct color for every
  driver.
- Choose between **All drivers**, **Top 8** and **Compare drivers** before drawing.
- Add one, two or more comparison drivers without redrawing unexpectedly, then press
  the explicit plot button to apply the prepared view.
- Remove comparison drivers from chips or deselect everything into a clear empty state.
- Toggle the horizontal axis between championship race numbers and named Grand Prix
  events.
- Hover in the order: driver, season, round, event, event-level index position, ELO,
  event change, observed xP, expected xP, car expectation, constructor, qualifying,
  finish and status.
- Break plotted lines when a driver retires for more than one season and later returns.
- Automatically focus Top 8 and comparison charts on the careers currently selected;
  the all-driver overview retains the complete 1950-2025 range.
- Keep the ELO axis at or above zero while zooming and panning.

## Publishable records

The records are display summaries of the selected, already-produced files:

- **Best prime ever:** greatest supplied sustained-prime rating.
- **Best driver of all time:** greatest integral of ELO relative to each event's active
  field median. Retirement/return gaps are split and drivers need at least 25 events.
- **Lowest career rating:** minimum supplied retrospective career ELO.
- **Lowest final rating:** minimum supplied retrospective current/final ELO.
- **Lowest single-race rating:** minimum event-level retrospective ELO among drivers
  with at least five starts.
- **Biggest one-race rise:** largest combined retrospective qualifying and race update.
- **Longest at #1:** most event appearances ranked first among that event's participants.
- **Highest car expectation:** highest season-average v6 expected-car-win estimate for a
  model/constructor combination with at least four events.

Every driver record is clickable. The profile combines the embedded ranking statistics
with a live read-only Wikipedia introduction. If Wikipedia is unavailable, the profile
keeps the model statistics and offers a direct search link.

Records are calculated from the complete supplied files, not from whichever subset is
currently visible in the chart.

The Lewis Hamilton feature uses a CC0 photograph by Vsbraga from Wikimedia Commons;
the source and credit are linked inside the visualizer.

## Generate

The default source is v7.1:

```powershell
$env:PYTHONPATH = "src"
python -m historical_xw.visualizer_cli_v8
```

To point the same GUI at another compatible release:

```powershell
python -m historical_xw.visualizer_cli_v8 --source-dir data/outputs/another_release
```

Explicit artifacts and labels are also supported:

```powershell
python -m historical_xw.visualizer_cli_v8 `
  --history path/to/history.parquet `
  --ranking path/to/ranking.parquet `
  --source-label "Corrected rules v7.2" `
  --output data/outputs/visualizer_v8/corrected_rules_v7_2.html
```

With the default source, the generated output is:

- `data/outputs/visualizer_v8/rookie_backcast_v7_1_visualizer_v8.html`

`--source-dir` discovery looks only for existing retrospective history and ranking
Parquets. It never calls the rookie, car, circuit, xP or ranking engines.

The output is one HTML file with embedded model data. Plotly and the credited driver
photo are loaded over HTTPS, so those visual elements require an internet connection.
