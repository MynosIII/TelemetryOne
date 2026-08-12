# TelemetryOne

TelemetryOne is an interactive Formula 1 historical driver-rating visualizer. It presents
the already-calculated Circuit Shape + Pairwise Margin + Rookie Backcast v7.6
retrospective ELO history without rerunning or changing the analytical model.

## Live site

The production site is deployed as a Render Static Site from `public/index.html`:

**https://telemetry-one.onrender.com**

## Interface

- All 698 indexed drivers are visible by default with stable individual colors.
- An accessible EN/ES switch translates the interface, chart labels, statistics, and
  Wikipedia biography source without reloading the page.
- A fixed-height driver index supports search, selection, and multi-driver comparisons.
- The horizontal axis switches between championship race number and Grand Prix names.
- Hover details include the race, event-level driver index, ELO change, xP, car expectation,
  qualifying, finish, and status.
- Record cards open driver statistics and read-only Wikipedia biography enrichment.
- The ELO axis cannot be zoomed or panned below zero.

## Record definitions

Records are calculated from the complete embedded history and ranking outputs, regardless of
the drivers currently selected in the chart:

- **Lowest career rating:** minimum supplied retrospective career ELO.
- **Lowest final rating:** minimum supplied retrospective current/final ELO.
- **Lowest single-race rating:** minimum event-level retrospective ELO among drivers with at
  least five starts.
- **Best driver of all time:** greatest integral of ELO relative to each event's active-field
  median, with retirement gaps split and a 25-event minimum.

## Repository layout

- `public/index.html` — standalone production artifact with the rating data embedded.
- `src/historical_xw/visualizer_v8.py` — payload and record calculations.
- `src/historical_xw/visualizer_cli_v8.py` — presentation-only build command.
- `src/historical_xw/templates/rating_visualizer_v8.html` — GUI template.
- `tests/test_visualizer_v8.py` — focused generator and interface tests.
- `docs/VISUALIZER_V8.md` — detailed interface and regeneration notes.

## Local preview

```powershell
python -m http.server 8765 --directory public
```

Then open `http://127.0.0.1:8765`.

## Regenerating from compatible model outputs

The published HTML is self-contained. Regeneration requires compatible retrospective history
and ranking Parquet files produced elsewhere; raw model datasets are intentionally not copied
into this presentation repository.

```powershell
python -m pip install -e ".[dev]"
python -m historical_xw.visualizer_cli_v8 `
  --source-dir path/to/release `
  --output public/index.html
```

## Validation

```powershell
python -m pytest -q
python -m ruff check src tests
```
