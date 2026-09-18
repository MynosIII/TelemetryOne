"""Adapts F1Predictor-companion project f1-driver-ranking's v8 output
(``driver_ranking_v8.parquet`` / ``driver_rating_history_v8.parquet`` --
position-based, DNF-fault-aware, bootstrapped-rookie rating; see that
repo's ``docs/ranking-architecture-v8.md``) into the schema
``visualizer_v8.py`` expects from a "retrospective" release.

This is a schema adapter, not a rating engine: every number here is a
rename, a join, or an honestly-labeled approximation of a v8 field the
visualizer's schema expects but v8 doesn't natively produce (see the
docstring on each approximation below). It never recomputes a rating.

Usage::

    python -m historical_xw.adapt_v8_source \\
        --source data/outputs/position_based_v8_source \\
        --output data/outputs/position_based_v8
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def _event_index(history: pd.DataFrame) -> pd.Series:
    events = (
        history[["season", "round"]]
        .drop_duplicates()
        .sort_values(["season", "round"], kind="stable")
        .reset_index(drop=True)
    )
    events["event_index"] = np.arange(1, len(events) + 1)
    merged = history.merge(events, on=["season", "round"], how="left", validate="many_to_one")
    return merged["event_index"]


def adapt(source_dir: Path, output_dir: Path) -> tuple[Path, Path]:
    history = pd.read_parquet(source_dir / "driver_rating_history_v8.parquet")
    ranking = pd.read_parquet(source_dir / "driver_ranking_v8.parquet")
    lookup = pd.read_csv(source_dir / "driver_id_lookup.csv")
    id_by_name = dict(zip(lookup["driver"], lookup["driver_id"], strict=True))

    history = history.copy()
    history["event_index"] = _event_index(history)
    history["driver_id"] = history["driver"].map(id_by_name)
    if history["driver_id"].isna().any():
        missing = sorted(history.loc[history["driver_id"].isna(), "driver"].unique())
        raise ValueError(f"No driver_id mapping for: {missing}")

    history["status_class"] = history["status_category"]
    history["retrospective_expected_performance"] = history["XP"]
    history["retrospective_rating"] = history["post_rating"]
    # v8 has no qualifying-specific signal (the whole point of its update is
    # a single race-level expected-vs-observed finishing percentile), so the
    # qualifying/race delta split the visualizer's schema expects is
    # honestly zero/all-in-race, not a fabricated split.
    history["retrospective_qualifying_delta"] = 0.0
    history["retrospective_race_delta"] = history["rating_delta"]
    # v8 does not do F1DB-backed car-model continuity tracking (the exact
    # chassis/model across its real lifespan) the way v7.6 does -- the
    # visualizer already has a documented, supported fallback for exactly
    # this ("constructor:{name}" -> rendered as "Model unresolved", scoped
    # per season in _build_car_data_v8), used here rather than fabricating
    # model identity v8 doesn't have.
    history["model_entity_id"] = "constructor:" + history["constructor"].astype(str)
    # v8's car-strength signal is XcW_score, a z-score (roughly mean 0,
    # std 1 within a season), not a calibrated win probability like v6/v7's
    # expected_car_win. A logistic squash gives a bounded, monotonic,
    # comparable-in-shape proxy for the visualizer's car view -- it is
    # labeled as an approximation in the catalog entry's description, not
    # presented as equivalent to the calibrated v6/v7 metric.
    history["expected_car_win_v8"] = 1.0 / (1.0 + np.exp(-history["XcW_score"].astype(float)))
    # _validate() hard-requires a literal "expected_car_win_v6" column to
    # exist (a schema-gate check, not a claim this is v6 data); the actual
    # display path in _car_win_column() prefers "expected_car_win_v8" first,
    # so this is only ever read if that preference logic changes.
    history["expected_car_win_v6"] = history["expected_car_win_v8"]
    # No separate eligibility concept in v8 (every counted race counts).
    history["rating_eligible"] = True

    ranking = ranking.copy()
    ranking["driver_id"] = ranking["driver"].map(id_by_name)
    if ranking["driver_id"].isna().any():
        missing = sorted(ranking.loc[ranking["driver_id"].isna(), "driver"].unique())
        raise ValueError(f"No driver_id mapping for: {missing}")
    ranking["eligible_races"] = ranking["races"]
    # v8 replaced win-probability (XW) with position-based XP entirely, so
    # it has no independent expected-win-count model; wins_above_expected
    # is reported as neutral (0) rather than reusing XP for a metric it
    # was never fit to predict. performance_above_expected (from
    # position_above_expected) is v8's real, analogous signal.
    ranking["expected_wins"] = ranking["wins"]
    ranking["wins_above_expected"] = 0.0
    ranking["sustained_prime_rating"] = ranking["prime_mean_rating"]
    ranking["performance_above_expected"] = ranking["position_above_expected"]

    output_dir.mkdir(parents=True, exist_ok=True)
    history_path = output_dir / "driver_rating_history_retrospective_v8.parquet"
    ranking_path = output_dir / "driver_ranking_retrospective_v8.parquet"
    history.to_parquet(history_path, index=False)
    ranking.to_parquet(ranking_path, index=False)
    return history_path, ranking_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/outputs/position_based_v8_source"))
    parser.add_argument("--output", type=Path, default=Path("data/outputs/position_based_v8"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    history_path, ranking_path = adapt(args.source, args.output)
    print(f"Wrote {history_path}")
    print(f"Wrote {ranking_path}")


if __name__ == "__main__":
    main()
