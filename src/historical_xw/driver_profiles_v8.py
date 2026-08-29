from __future__ import annotations

import html
import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

MODERN_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _f1db_driver_id(driver: pd.Series) -> str:
    value = driver.get("driver_id_f1db")
    if pd.notna(value) and str(value):
        return str(value)
    return _slug(str(driver["driver"]))


@cache
def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@cache
def _standings_index(f1db_root: Path) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    season_root = f1db_root / "seasons"
    if season_root.is_dir():
        for standings_path in sorted(season_root.glob("*/driver-standings.yml")):
            standings = _read_yaml(standings_path) or []
            year = int(standings_path.parent.name)
            for row in standings:
                index.setdefault(str(row.get("driverId")), []).append({**row, "season": year})
    return index


def _official_record(f1db_root: Path, f1db_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    biography = _read_yaml(f1db_root / "drivers" / f"{f1db_id}.yml") or {}
    official_points = 0.0
    titles: list[int] = []
    best_position: int | None = None
    seasons: list[dict[str, Any]] = []
    for row in _standings_index(f1db_root).get(f1db_id, []):
        year = int(row["season"])
        raw_position = row.get("position")
        position = int(raw_position) if str(raw_position).isdigit() else None
        points = float(row.get("points") or 0)
        official_points += points
        if position is not None:
            best_position = position if best_position is None else min(best_position, position)
        if position == 1:
            titles.append(year)
        seasons.append({"season": year, "position": raw_position, "points": points})
    return biography, {
        "officialPoints": round(official_points, 2),
        "championships": len(titles),
        "titleSeasons": titles,
        "bestChampionshipPosition": best_position,
        "seasonStandings": seasons,
    }


def build_driver_profile_v8(career: pd.DataFrame, ranking: pd.Series | None, f1db_root: Path) -> dict[str, Any]:
    career = career.sort_values(["season", "round"], kind="stable").copy()
    first = career.iloc[0]
    driver_id = str(first["driver_id"])
    f1db_id = _f1db_driver_id(first)
    biography, official = _official_record(f1db_root, f1db_id)
    positions = pd.to_numeric(career["position"], errors="coerce")
    qualifying = pd.to_numeric(career.get("qualifying_position"), errors="coerce")
    constructors = list(dict.fromkeys(career["constructor"].dropna().astype(str)))
    models = list(dict.fromkeys(
        value for value in career.get("model_entity_id", pd.Series(dtype=str)).dropna().astype(str)
        if not value.startswith("constructor:")
    ))
    modern_points = float(positions.map(MODERN_POINTS).fillna(0).sum())

    teammate_rows = []
    for (_, _, constructor), group in career.groupby(["season", "event_index", "constructor"]):
        # The event history contains one row per driver. Pairing happens in the caller.
        teammate_rows.append(group)

    peak = career.loc[pd.to_numeric(career["retrospective_rating"], errors="coerce").idxmax()]
    final = career.iloc[-1]
    recent = career.tail(12).iloc[::-1]
    return {
        "id": driver_id,
        "f1dbId": f1db_id,
        "name": str(first["driver"]),
        "wikipediaTitle": str(first["driver"]),
        "biography": biography,
        **official,
        "races": int(career["event_index"].nunique()),
        "seasons": int(career["season"].nunique()),
        "debut": int(career["season"].min()),
        "lastSeason": int(career["season"].max()),
        "wins": int(positions.eq(1).sum()),
        "podiums": int(positions.le(3).sum()),
        "poles": int(qualifying.eq(1).sum()),
        "bestFinish": int(positions.min()) if positions.notna().any() else None,
        "modernPoints": round(modern_points, 1),
        "constructors": constructors,
        "cars": models,
        "peak": {
            "rating": round(float(peak["retrospective_rating"]), 1),
            "season": int(peak["season"]),
            "event": str(peak["event"]),
        },
        "model": {
            "rank": int(ranking["rank"]) if ranking is not None else None,
            "finalEventRank": int(final["profile_event_rank"]),
            "finalEventFieldSize": int(final["profile_event_field_size"]),
            "rankStatus": "current" if bool(final["profile_active_driver"]) else "retirement",
            "rankSeason": int(final["season"]),
            "rankEvent": str(final["event"]),
            "careerRating": round(float(ranking["career_rating"]), 1) if ranking is not None else None,
            "currentRating": round(float(ranking["current_rating"]), 1) if ranking is not None else None,
            "sustainedPrime": round(float(ranking["sustained_prime_rating"]), 1) if ranking is not None else None,
            "expectedWins": round(float(ranking["expected_wins"]), 2) if ranking is not None else None,
            "winsAboveExpected": round(float(ranking["wins_above_expected"]), 2) if ranking is not None else None,
            "performanceAboveExpected": round(float(ranking["performance_above_expected"]), 2) if ranking is not None else None,
        },
        "recentResults": [
            {
                "season": int(row.season), "round": int(row.round), "event": str(row.event),
                "constructor": str(row.constructor), "grid": _number(getattr(row, "qualifying_position", None)),
                "finish": _number(row.position), "rating": round(float(row.retrospective_rating), 1),
            }
            for row in recent.itertuples(index=False)
        ],
    }


def _number(value: Any) -> int | None:
    return None if pd.isna(value) else int(value)


def _add_teammate_comparisons(profiles: dict[str, dict[str, Any]], history: pd.DataFrame) -> None:
    eligible = history[history["rating_eligible"].fillna(False)].copy()
    all_comparisons: dict[str, dict[str, dict[str, float]]] = {}
    for _, entrants in eligible.groupby(["season", "event_index", "constructor"], sort=False):
        rows = list(entrants.itertuples(index=False))
        for row in rows:
            comparisons = all_comparisons.setdefault(str(row.driver_id), {})
            for peer in rows:
                if row.driver_id == peer.driver_id:
                    continue
                item = comparisons.setdefault(str(peer.driver_id), {"races": 0, "finishWins": 0, "qualifyingWins": 0, "ratingDelta": 0.0})
                item["races"] += 1
                if float(row.position) < float(peer.position): item["finishWins"] += 1
                row_q, peer_q = getattr(row, "qualifying_position", None), getattr(peer, "qualifying_position", None)
                if pd.notna(row_q) and pd.notna(peer_q) and float(row_q) < float(peer_q): item["qualifyingWins"] += 1
                item["ratingDelta"] += float(row.retrospective_rating) - float(peer.retrospective_rating)
    for driver_id, comparisons in all_comparisons.items():
        rendered = []
        for peer_id, item in comparisons.items():
            if peer_id not in profiles: continue
            races = int(item["races"])
            rendered.append({"id": peer_id, "name": profiles[peer_id]["name"], "races": races,
                             "finishWins": int(item["finishWins"]), "qualifyingWins": int(item["qualifyingWins"]),
                             "averageRatingEdge": round(item["ratingDelta"] / races, 1)})
        profiles[driver_id]["teammates"] = sorted(rendered, key=lambda x: (-x["races"], x["name"]))
    for profile in profiles.values():
        profile.setdefault("teammates", [])


def write_driver_profiles_v8(history: pd.DataFrame, ranking: pd.DataFrame, output_dir: Path, f1db_root: Path) -> int:
    template = (Path(__file__).parent / "templates" / "driver_profile_v8.html").read_text(encoding="utf-8")
    history = history.copy()
    history["profile_event_rank"] = (
        history.groupby("event_index")["retrospective_rating"]
        .rank(method="min", ascending=False)
        .astype(int)
    )
    history["profile_event_field_size"] = history.groupby("event_index")["driver_id"].transform("nunique")
    latest_season = int(history["season"].max())
    history["profile_active_driver"] = history["season"].eq(latest_season)
    ranking_lookup = ranking.set_index("driver_id")
    profiles: dict[str, dict[str, Any]] = {}
    for driver_id, career in history.groupby("driver_id", sort=False):
        key = str(driver_id)
        ranked = ranking_lookup.loc[key] if key in ranking_lookup.index else None
        profiles[key] = build_driver_profile_v8(career, ranked, f1db_root)
    _add_teammate_comparisons(profiles, history)
    for driver_id, profile in profiles.items():
        target = output_dir / "drivers" / driver_id / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(profile, ensure_ascii=False, allow_nan=False, default=str, separators=(",", ":")).replace("</", "<\\/")
        target.write_text(template.replace("__DRIVER_NAME__", html.escape(profile["name"]))
                          .replace("__DRIVER_PROFILE__", payload), encoding="utf-8")
    index = [{"id": p["id"], "name": p["name"], "debut": p["debut"], "lastSeason": p["lastSeason"]} for p in profiles.values()]
    (output_dir / "data" / "driver-profiles.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(profiles)
