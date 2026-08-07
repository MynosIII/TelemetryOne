from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


HAMILTON_PHOTO = {
    "url": (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/"
        "Lewis_Hamilton%2C_McLaren_MP4-23_Mercedes-Benz.jpg/"
        "960px-Lewis_Hamilton%2C_McLaren_MP4-23_Mercedes-Benz.jpg"
    ),
    "credit": "Lewis Hamilton · Photo by Vsbraga / Wikimedia Commons · CC0",
    "source": (
        "https://commons.wikimedia.org/wiki/"
        "File:Lewis_Hamilton,_McLaren_MP4-23_Mercedes-Benz.jpg"
    ),
}


def infer_visualizer_source_label_v8(path: Path) -> str:
    """Create a display label from an output directory without importing its engine."""

    name = path.name
    version_match = re.search(r"v(\d+)(?:[_-](\d+))?", name, flags=re.IGNORECASE)
    if version_match:
        version = version_match.group(1)
        if version_match.group(2):
            version += f".{version_match.group(2)}"
        stem = re.sub(r"[_-]?v\d+(?:[_-]\d+)?", "", name, flags=re.IGNORECASE)
        stem = stem.replace("_", " ").replace("-", " ").strip().title()
        return f"{stem} v{version}" if stem else f"Dataset v{version}"
    return name.replace("_", " ").replace("-", " ").strip().title()


def resolve_visualizer_inputs_v8(
    source_dir: Path,
    history_path: Path | None = None,
    ranking_path: Path | None = None,
) -> tuple[Path, Path]:
    """Resolve already-produced artifacts; never execute an analytical pipeline."""

    def newest(pattern: str, description: str) -> Path:
        candidates = sorted(
            source_dir.glob(pattern),
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(f"No {description} Parquet found in {source_dir}")
        return candidates[0]

    history = history_path or newest(
        "driver_rating_history_retrospective*.parquet", "retrospective history"
    )
    ranking = ranking_path or newest(
        "driver_ranking_retrospective*.parquet", "retrospective ranking"
    )
    if not history.is_file():
        raise FileNotFoundError(f"History file does not exist: {history}")
    if not ranking.is_file():
        raise FileNotFoundError(f"Ranking file does not exist: {ranking}")
    return history, ranking


def _validate(history: pd.DataFrame, ranking: pd.DataFrame) -> None:
    history_required = {
        "season",
        "round",
        "event",
        "event_index",
        "driver_id",
        "driver",
        "constructor",
        "position",
        "status_class",
        "XP",
        "retrospective_expected_performance",
        "retrospective_rating",
        "retrospective_qualifying_delta",
        "retrospective_race_delta",
        "expected_car_win_v6",
        "model_entity_id",
        "rating_eligible",
    }
    ranking_required = {
        "rank",
        "driver_id",
        "driver",
        "races",
        "eligible_races",
        "wins",
        "expected_wins",
        "wins_above_expected",
        "current_rating",
        "sustained_prime_rating",
        "peak_rating",
        "career_rating",
        "performance_above_expected",
    }
    if missing := history_required - set(history.columns):
        raise ValueError(f"Rating history is missing display columns: {sorted(missing)}")
    if missing := ranking_required - set(ranking.columns):
        raise ValueError(f"Rating ranking is missing display columns: {sorted(missing)}")


def add_visualizer_fields_v8(history: pd.DataFrame) -> pd.DataFrame:
    """Add global race coordinates and event-relative driver index positions."""

    data = history.copy().sort_values(["season", "round", "position"], kind="stable")
    events = (
        data[["event_index", "season", "round", "event"]]
        .drop_duplicates("event_index")
        .sort_values("event_index")
        .reset_index(drop=True)
    )
    events["race_index"] = np.arange(1, len(events) + 1)
    events["race_label"] = (
        events["season"].astype(str)
        + " R"
        + events["round"].astype(str)
        + " · "
        + events["event"].astype(str)
    )
    data = data.merge(
        events[["event_index", "race_index", "race_label"]],
        on="event_index",
        how="left",
        validate="many_to_one",
    )
    data["driver_index_position"] = (
        data.groupby("event_index")["retrospective_rating"]
        .rank(method="min", ascending=False)
        .astype(int)
    )
    data["event_field_size"] = data.groupby("event_index")["driver_id"].transform("nunique")
    data["event_field_median"] = data.groupby("event_index")[
        "retrospective_rating"
    ].transform("median")
    data["retrospective_total_delta"] = (
        pd.to_numeric(data["retrospective_qualifying_delta"], errors="coerce").fillna(0.0)
        + pd.to_numeric(data["retrospective_race_delta"], errors="coerce").fillna(0.0)
    )
    return data


def _career_curve_areas(data: pd.DataFrame, minimum_races: int = 25) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for driver_id, career in data.groupby("driver_id", sort=False):
        career = career.sort_values("event_index", kind="stable").drop_duplicates("event_index")
        if len(career) < minimum_races:
            continue
        adjusted = (
            career["retrospective_rating"] - career["event_field_median"]
        ).to_numpy(dtype=float)
        seasons = career["season"].to_numpy(dtype=int)
        split_points = np.flatnonzero(np.diff(seasons) > 1) + 1
        area = 0.0
        for segment in np.split(adjusted, split_points):
            if len(segment) == 1:
                area += float(segment[0])
            elif len(segment) > 1:
                area += float(np.trapezoid(segment, dx=1.0))
        rows.append(
            {
                "driver_id": str(driver_id),
                "driver": str(career.iloc[0]["driver"]),
                "career_curve_area": area,
                "career_events": int(len(career)),
                "career_stints": int(len(split_points) + 1),
                "mean_field_advantage": float(np.mean(adjusted)),
            }
        )
    return pd.DataFrame(rows)


def _driver_record(row: pd.Series) -> dict[str, Any]:
    return {
        "driverId": str(row["driver_id"]),
        "driver": str(row["driver"]),
    }


def compute_visualizer_metrics_v8(
    data: pd.DataFrame,
    ranking: pd.DataFrame,
) -> dict[str, Any]:
    areas = _career_curve_areas(data)
    best_area = areas.nlargest(1, "career_curve_area").iloc[0]
    best_prime = ranking.nlargest(1, "sustained_prime_rating").iloc[0]
    lowest_career = ranking.nsmallest(1, "career_rating").iloc[0]
    lowest_current = ranking.nsmallest(1, "current_rating").iloc[0]

    career_counts = data.groupby("driver_id")["event_index"].nunique()
    established_ids = career_counts[career_counts.ge(5)].index
    moments = data[data["driver_id"].isin(established_ids)].copy()
    worst_moment = moments.nsmallest(1, "retrospective_rating").iloc[0]
    biggest_rise = moments.nlargest(1, "retrospective_total_delta").iloc[0]

    number_one = (
        data[data["driver_index_position"].eq(1)]
        .groupby(["driver_id", "driver"])["event_index"]
        .nunique()
        .rename("events_at_one")
        .reset_index()
        .nlargest(1, "events_at_one")
        .iloc[0]
    )

    eligible = data[data["rating_eligible"]].copy()
    car_events = (
        eligible.groupby(
            ["season", "model_entity_id", "constructor", "event_index"], dropna=False
        )["expected_car_win_v6"]
        .mean()
        .rename("expected_car_win")
        .reset_index()
    )
    car_seasons = (
        car_events.groupby(["season", "model_entity_id", "constructor"], dropna=False)
        .agg(events=("event_index", "nunique"), expected_car_win=("expected_car_win", "mean"))
        .reset_index()
    )
    best_car = car_seasons[car_seasons["events"].ge(4)].nlargest(
        1, "expected_car_win"
    ).iloc[0]

    best_prime_record = {
        **_driver_record(best_prime),
        "value": round(float(best_prime["sustained_prime_rating"]), 1),
        "peak": round(float(best_prime["peak_rating"]), 1),
        "races": int(best_prime["races"]),
        "photo": HAMILTON_PHOTO if str(best_prime["driver_id"]) == "hamilton" else None,
    }
    return {
        "bestPrime": best_prime_record,
        "bestCareerCurve": {
            **_driver_record(best_area),
            "value": round(float(best_area["career_curve_area"])),
            "events": int(best_area["career_events"]),
            "stints": int(best_area["career_stints"]),
            "meanAdvantage": round(float(best_area["mean_field_advantage"]), 1),
        },
        "lowestCareerRating": {
            **_driver_record(lowest_career),
            "value": round(float(lowest_career["career_rating"]), 1),
            "races": int(lowest_career["races"]),
            "prime": round(float(lowest_career["sustained_prime_rating"]), 1),
        },
        "lowestCurrentRating": {
            **_driver_record(lowest_current),
            "value": round(float(lowest_current["current_rating"]), 1),
            "races": int(lowest_current["races"]),
        },
        "worstMoment": {
            **_driver_record(worst_moment),
            "value": round(float(worst_moment["retrospective_rating"]), 1),
            "season": int(worst_moment["season"]),
            "event": str(worst_moment["event"]),
        },
        "biggestRise": {
            **_driver_record(biggest_rise),
            "value": round(float(biggest_rise["retrospective_total_delta"]), 1),
            "season": int(biggest_rise["season"]),
            "event": str(biggest_rise["event"]),
        },
        "longestAtOne": {
            **_driver_record(number_one),
            "value": int(number_one["events_at_one"]),
        },
        "bestCar": {
            "season": int(best_car["season"]),
            "model": str(best_car["model_entity_id"]),
            "constructor": str(best_car["constructor"]),
            "events": int(best_car["events"]),
            "value": round(100.0 * float(best_car["expected_car_win"]), 1),
        },
    }


def _json_value(value: Any, digits: int = 3) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return round(float(value), digits)
    return str(value)


def build_visualizer_payload_v8(
    history: pd.DataFrame,
    ranking: pd.DataFrame,
    source_label: str = "External rating dataset",
) -> dict[str, Any]:
    _validate(history, ranking)
    data = add_visualizer_fields_v8(history)
    events = (
        data[["event_index", "race_index", "race_label", "season", "round", "event"]]
        .drop_duplicates("event_index")
        .sort_values("race_index")
    )
    ranking_lookup = ranking.set_index("driver_id")
    driver_payload: dict[str, Any] = {}
    for driver_id, career in data.groupby("driver_id", sort=False):
        career = career.sort_values("race_index", kind="stable")
        driver_id = str(driver_id)
        ranked = ranking_lookup.loc[driver_id] if driver_id in ranking_lookup.index else None
        points = []
        for row in career.itertuples(index=False):
            points.append(
                [
                    int(row.race_index),
                    _json_value(row.retrospective_rating, 2),
                    int(row.season),
                    int(row.round),
                    str(row.event),
                    int(row.driver_index_position),
                    int(row.event_field_size),
                    str(row.constructor),
                    _json_value(row.retrospective_total_delta, 2),
                    _json_value(row.XP, 3),
                    _json_value(row.retrospective_expected_performance, 3),
                    _json_value(row.expected_car_win_v6, 3),
                    _json_value(getattr(row, "qualifying_position", None), 0),
                    _json_value(row.position, 0),
                    str(row.status_class),
                    str(row.race_label),
                ]
            )
        driver_payload[driver_id] = {
            "id": driver_id,
            "name": str(career.iloc[0]["driver"]),
            "races": int(career["event_index"].nunique()),
            "debut": int(career["season"].min()),
            "lastSeason": int(career["season"].max()),
            "careerRating": (
                round(float(ranked["career_rating"]), 1) if ranked is not None else None
            ),
            "rank": int(ranked["rank"]) if ranked is not None else None,
            "eligibleRaces": int(ranked["eligible_races"]) if ranked is not None else None,
            "wins": int(ranked["wins"]) if ranked is not None else None,
            "expectedWins": (
                round(float(ranked["expected_wins"]), 2) if ranked is not None else None
            ),
            "winsAboveExpected": (
                round(float(ranked["wins_above_expected"]), 2)
                if ranked is not None
                else None
            ),
            "currentRating": (
                round(float(ranked["current_rating"]), 1) if ranked is not None else None
            ),
            "sustainedPrime": (
                round(float(ranked["sustained_prime_rating"]), 1)
                if ranked is not None
                else None
            ),
            "peakRating": (
                round(float(ranked["peak_rating"]), 1) if ranked is not None else None
            ),
            "performanceAboveExpected": (
                round(float(ranked["performance_above_expected"]), 2)
                if ranked is not None
                else None
            ),
            "points": points,
        }

    ranked_drivers = ranking.sort_values("rank")["driver_id"].astype(str).tolist()
    leaders = [driver_id for driver_id in ranked_drivers if driver_id in driver_payload][:8]
    metrics = compute_visualizer_metrics_v8(data, ranking)
    return {
        "meta": {
            "title": "F1 Historical Rating Lab",
            "model": source_label,
            "drivers": len(driver_payload),
            "observations": int(len(data)),
            "events": int(events["event_index"].nunique()),
            "seasons": int(data["season"].nunique()),
            "firstSeason": int(data["season"].min()),
            "lastSeason": int(data["season"].max()),
        },
        "events": [
            {
                "index": int(row.race_index),
                "label": str(row.race_label),
                "short": f"{int(row.season)} · {row.event}",
            }
            for row in events.itertuples(index=False)
        ],
        "drivers": driver_payload,
        "leaders": leaders,
        "metrics": metrics,
    }


def write_visualizer_v8(
    history_path: Path,
    ranking_path: Path,
    output_path: Path,
    source_label: str | None = None,
) -> Path:
    history = pd.read_parquet(history_path)
    ranking = pd.read_parquet(ranking_path)
    payload = build_visualizer_payload_v8(
        history,
        ranking,
        source_label=source_label or infer_visualizer_source_label_v8(history_path.parent),
    )
    template_path = Path(__file__).parent / "templates" / "rating_visualizer_v8.html"
    template = template_path.read_text(encoding="utf-8")
    payload_json = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    html = template.replace("__VISUALIZER_PAYLOAD__", payload_json.replace("</", "<\\/"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
