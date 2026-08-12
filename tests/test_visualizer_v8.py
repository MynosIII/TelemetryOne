from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from historical_xw.visualizer_cli_v8 import build_parser
from historical_xw.visualizer_v8 import (
    add_visualizer_fields_v8,
    build_visualizer_payload_v8,
    infer_visualizer_source_label_v8,
    resolve_visualizer_inputs_v8,
    write_visualizer_catalog_v8,
    write_visualizer_v8,
)


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    ratings = {
        1: {"lauda": 1600.0, "reutemann": 1580.0},
        2: {"lauda": 1590.0, "reutemann": 1620.0},
    }
    for event_index, event in enumerate(("Monaco Grand Prix", "Spanish Grand Prix"), start=1):
        for position, driver_id in enumerate(("lauda", "reutemann"), start=1):
            rows.append(
                {
                    "season": 1978 if event_index == 1 else 1981,
                    "round": 5 if event_index == 1 else 7,
                    "event": event,
                    "event_index": event_index,
                    "driver_id": driver_id,
                    "driver": "Niki Lauda" if driver_id == "lauda" else "Carlos Reutemann",
                    "constructor": "Brabham" if driver_id == "lauda" else "Williams",
                    "position": position,
                    "status_class": "finished",
                    "XP": 1.0 - (position - 1),
                    "retrospective_expected_performance": 0.5,
                    "retrospective_rating": ratings[event_index][driver_id],
                    "retrospective_qualifying_delta": 1.0,
                    "retrospective_race_delta": 2.0,
                    "expected_car_win_v6": 0.4,
                    "model_entity_id": f"car-{driver_id}",
                    "rating_eligible": True,
                    "qualifying_position": position,
                }
            )
    history = pd.DataFrame(rows)
    ranking = pd.DataFrame(
        [
            {
                "rank": 1,
                "driver_id": "lauda",
                "driver": "Niki Lauda",
                "races": 2,
                "eligible_races": 2,
                "wins": 1,
                "expected_wins": 0.8,
                "wins_above_expected": 0.2,
                "current_rating": 1590.0,
                "sustained_prime_rating": 1600.0,
                "peak_rating": 1600.0,
                "career_rating": 1590.0,
                "performance_above_expected": 0.4,
            },
            {
                "rank": 2,
                "driver_id": "reutemann",
                "driver": "Carlos Reutemann",
                "races": 2,
                "eligible_races": 2,
                "wins": 1,
                "expected_wins": 1.2,
                "wins_above_expected": -0.2,
                "current_rating": 1620.0,
                "sustained_prime_rating": 1595.0,
                "peak_rating": 1620.0,
                "career_rating": 1585.0,
                "performance_above_expected": 0.2,
            },
        ]
    )
    return history, ranking


def test_event_driver_index_position_is_recalculated_each_race() -> None:
    history, _ = _inputs()
    enriched = add_visualizer_fields_v8(history)
    monaco = enriched[enriched["event"].eq("Monaco Grand Prix")].set_index("driver_id")
    spain = enriched[enriched["event"].eq("Spanish Grand Prix")].set_index("driver_id")
    assert monaco.loc["lauda", "driver_index_position"] == 1
    assert spain.loc["reutemann", "driver_index_position"] == 1


def test_payload_contains_searchable_drivers_and_ordered_hover_fields() -> None:
    history, ranking = _inputs()
    # Expand careers so the presentation-summary cards satisfy the 25-race threshold.
    history = pd.concat([history.assign(event_index=lambda frame: frame.event_index + 2 * i)
                         for i in range(13)], ignore_index=True)
    history["round"] = history.groupby("driver_id").cumcount() + 1
    payload = build_visualizer_payload_v8(history, ranking)
    assert set(payload["drivers"]) == {"lauda", "reutemann"}
    assert payload["drivers"]["lauda"]["points"][0][2:5] == [1978, 1, "Monaco Grand Prix"]
    assert "bestPrime" in payload["metrics"]
    assert payload["metrics"]["lowestCareerRating"]["driverId"] == "reutemann"
    assert payload["metrics"]["lowestCurrentRating"]["driverId"] == "lauda"


def test_writer_builds_standalone_gui_from_existing_parquets(tmp_path: Path) -> None:
    history, ranking = _inputs()
    history = pd.concat([history.assign(event_index=lambda frame: frame.event_index + 2 * i)
                         for i in range(13)], ignore_index=True)
    history["round"] = history.groupby("driver_id").cumcount() + 1
    history_path = tmp_path / "history.parquet"
    ranking_path = tmp_path / "ranking.parquet"
    output_path = tmp_path / "visualizer.html"
    history.to_parquet(history_path, index=False)
    ranking.to_parquet(ranking_path, index=False)
    write_visualizer_v8(history_path, ranking_path, output_path)
    html = output_path.read_text(encoding="utf-8")
    assert "All drivers" in html
    assert "Plot all drivers" in html
    assert "Compare drivers" in html
    assert "Deselect all" in html
    assert "Race names" in html
    assert "Current driver index" in html
    assert 'id="driver-index-list"' in html
    assert "Lowest career rating" in html
    assert "Lowest final rating" in html
    assert "Wikipedia" in html
    assert 'minallowed: 0' in html
    assert 'id="language-toggle"' in html
    assert "Cada era." in html
    assert "es.wikipedia.org" in html
    assert "document.documentElement.lang = language" in html
    assert 'id="dataset-picker-button"' in html
    assert "__VISUALIZER_PAYLOAD__" not in html
    assert "__DATASET_CATALOG__" not in html
    assert "__VISUALIZER_DATA__" not in html


def test_catalog_writer_builds_lazy_datasets_and_planned_slots(tmp_path: Path) -> None:
    history, ranking = _inputs()
    history = pd.concat([history.assign(event_index=lambda frame: frame.event_index + 2 * i)
                         for i in range(13)], ignore_index=True)
    history["round"] = history.groupby("driver_id").cumcount() + 1
    for version in ("v7", "v7_2"):
        source = tmp_path / version
        source.mkdir()
        history.to_parquet(source / f"driver_rating_history_retrospective_{version}.parquet", index=False)
        ranking.to_parquet(source / f"driver_ranking_retrospective_{version}.parquet", index=False)
    catalog = {
        "schemaVersion": 1,
        "defaultId": "v7_2",
        "datasets": [
            {
                "id": "v7",
                "label": "v7",
                "title": "First model",
                "status": "available",
                "sourceDir": "v7",
                "dataFile": "data/datasets/v7.json",
            },
            {
                "id": "v7_2",
                "label": "v7.2",
                "title": "Second model",
                "status": "available",
                "sourceDir": "v7_2",
                "dataFile": "data/datasets/v7_2.json",
            },
            {
                "id": "speed_only",
                "label": "Speed only",
                "title": "Pace analysis",
                "status": "planned",
            },
        ],
    }
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    output = write_visualizer_catalog_v8(catalog_path, tmp_path / "public")
    html = output.read_text(encoding="utf-8")
    v7_payload = json.loads((tmp_path / "public/data/datasets/v7.json").read_text(encoding="utf-8"))
    assert v7_payload["meta"]["datasetId"] == "v7"
    assert 'id="dataset-catalog"' in html
    assert '"defaultId":"v7_2"' in html
    assert '"status":"planned"' in html
    assert "sourceDir" not in html
    assert "__DATASET_CATALOG__" not in html


def test_cli_defaults_to_v7_1_but_accepts_any_source_directory() -> None:
    args = build_parser().parse_args([])
    assert args.source_dir.endswith("rookie_backcast_v7_1")
    assert args.history is None
    assert args.ranking is None
    assert args.output is None


def test_source_artifacts_are_discovered_without_running_an_engine(tmp_path: Path) -> None:
    history = tmp_path / "driver_rating_history_retrospective_custom.parquet"
    ranking = tmp_path / "driver_ranking_retrospective_custom.parquet"
    history.touch()
    ranking.touch()
    resolved_history, resolved_ranking = resolve_visualizer_inputs_v8(tmp_path)
    assert resolved_history == history
    assert resolved_ranking == ranking


def test_source_label_is_inferred_from_release_directory() -> None:
    assert (
        infer_visualizer_source_label_v8(Path("data/outputs/rookie_backcast_v7_1"))
        == "Rookie Backcast v7.1"
    )
