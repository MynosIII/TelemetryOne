from __future__ import annotations

import json
from pathlib import Path

from historical_xw.opinion_cli import _strip_html, _XenForoPostParser, main
from historical_xw.opinion_poll import (
    anonymize_author,
    build_opinion_payload,
    classify_vote,
    redact_public_text,
)


def test_classifies_explicit_multilingual_choices() -> None:
    assert classify_vote("Ayrton Senna is the GOAT. No contest.").driver_id == "senna"
    assert classify_vote("Para mí, Fangio es el mejor piloto").driver_id == "fangio"
    assert classify_vote("1. Jim Clark, 2. Prost, 3. Senna").driver_id == "clark"
    assert classify_vote("Hamilton is the GOAT").driver_id == "hamilton"
    assert classify_vote("Schumi 🐐").driver_id == "michael_schumacher"
    assert classify_vote("Senna deserves the first position").driver_id == "senna"
    assert classify_vote("Fangio is my choice for the GOAT").driver_id == "fangio"
    assert classify_vote("Me quedo con Prost").driver_id == "prost"
    assert classify_vote("Hamilton hands down").driver_id == "hamilton"
    assert classify_vote("Jim Clark tho", prompted=True).driver_id == "clark"
    assert (
        classify_vote("My top three:\nSenna\nFangio\nHamilton", ranking_prompt=True).driver_id
        == "senna"
    )


def test_rejects_mentions_without_a_unique_choice() -> None:
    assert classify_vote("Senna and Schumacher changed Formula 1").driver_id is None
    assert classify_vote("Hamilton is not the greatest").driver_id is None
    assert classify_vote("Hamilton always had the best car").driver_id is None
    assert classify_vote("Fangio and Ascari were the best").driver_id is None
    assert classify_vote("Alonso should be higher").driver_id is None
    assert classify_vote("Senna was the best?").driver_id is None
    assert classify_vote("Hamilton is better than Vettel").driver_id is None
    assert classify_vote("Jajaja cuando dicen que el mejor es Schumacher").driver_id is None
    assert classify_vote("Alonso should be higher", prompted=True).driver_id is None
    assert classify_vote("Senna > Hamilton", prompted=True).driver_id is None
    assert classify_vote("Mario Andretti also won the Triple Crown", prompted=True).driver_id is None
    assert classify_vote("Hamilton is way too high", prompted=True).driver_id is None
    assert classify_vote("11. George Russell", prompted=True).driver_id is None
    assert classify_vote("You think Verstappen is the best ever? Insane").driver_id is None
    assert classify_vote("Vettel es mejor que Alonso").driver_id is None
    assert classify_vote("Fans are saying Vettel is the best", prompted=True).driver_id is None
    assert (
        classify_vote("10. Alonso\n9. Vettel\n2. Fangio\n1. Senna", ranking_prompt=True).driver_id
        == "senna"
    )
    assert classify_vote("This list is terrible").rule == "no_driver"


def test_redacts_incidental_personal_links_from_stored_text() -> None:
    text = "@fan told me at fan@example.com — see https://example.com/post"
    assert redact_public_text(text) == "@user told me at [email] — see [url]"


def test_reddit_html_is_reduced_to_comment_text() -> None:
    assert _strip_html("<p>Senna &amp; Fangio</p><p>My pick: Senna</p>") == (
        "Senna & Fangio My pick: Senna"
    )


def test_forum_parser_excludes_quoted_text_and_keeps_author() -> None:
    parser = _XenForoPostParser()
    parser.feed(
        '<article class="message message--post" data-author="fan" data-content="post-7">'
        '<div class="bbWrapper"><blockquote>Hamilton is the GOAT</blockquote>'
        "My choice is Senna</div></article>"
    )
    assert parser.posts == [("post-7", "fan", "My choice is Senna")]


def test_payload_deduplicates_author_and_balances_sources() -> None:
    rows = []
    for index, (source, author, text) in enumerate(
        [
            ("old", "a", "Senna is the GOAT"),
            ("old", "a", "Senna is the best"),
            ("old", "b", "Senna"),
            ("old", "c", "Schumacher is the GOAT"),
            ("old", "d", "Senna"),
            ("old", "e", "Schumacher"),
            ("new", "f", "Hamilton"),
            ("new", "g", "Hamilton is the GOAT"),
            ("new", "h", "Hamilton"),
            ("new", "i", "Senna"),
            ("new", "j", "Hamilton"),
            ("new", "k", "Hamilton"),
        ]
    ):
        rows.append(
            {
                "platform": "youtube",
                "source_id": source,
                "source_title": source,
                "source_published_date": "2025-01-01",
                "comment_id": str(index),
                "author_hash": anonymize_author("youtube", author),
                "text": text,
                "likes": 0,
            }
        )
    payload = build_opinion_payload(rows, generated_at="2026-01-01T00:00:00Z")
    assert payload["quality"]["validVotes"] == 11
    assert payload["quality"]["rejections"]["duplicate_voter"] == 1
    assert payload["ranking"][0]["driverId"] == "hamilton"


def test_payload_rejects_conflicting_choices_from_one_voter() -> None:
    voter = anonymize_author("reddit", "same-person")
    rows = [
        {
            "platform": "reddit",
            "source_id": "thread",
            "source_title": "thread",
            "query_family": "all-time-question",
            "comment_id": "1",
            "author_hash": voter,
            "text": "Senna",
        },
        {
            "platform": "reddit",
            "source_id": "thread",
            "source_title": "thread",
            "query_family": "all-time-question",
            "comment_id": "2",
            "author_hash": voter,
            "text": "Hamilton",
        },
    ]
    payload = build_opinion_payload(rows)
    assert payload["quality"]["validVotes"] == 0
    assert payload["quality"]["rejections"]["conflicting_voter"] == 2


def test_cli_build_reads_multiple_inputs_and_exclusion_file(tmp_path: Path) -> None:
    included = tmp_path / "included.jsonl"
    excluded = tmp_path / "excluded.jsonl"
    output = tmp_path / "ranking.json"
    exclusions = tmp_path / "exclusions.json"
    common = {
        "platform": "youtube",
        "source_title": "Who is the greatest F1 driver of all time?",
        "query_family": "all-time-question",
    }
    included.write_text(
        json.dumps(
            {
                **common,
                "source_id": "keep",
                "comment_id": "1",
                "author_hash": "voter-a",
                "text": "Senna is the GOAT",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    excluded.write_text(
        json.dumps(
            {
                **common,
                "source_id": "drop",
                "comment_id": "2",
                "author_hash": "voter-b",
                "text": "Hamilton is the GOAT",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    exclusions.write_text(json.dumps({"source_ids": ["drop"]}), encoding="utf-8")

    assert (
        main(
            [
                "build",
                "--input",
                str(included),
                str(excluded),
                "--exclude-source-file",
                str(exclusions),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["quality"]["commentsSampled"] == 1
    assert payload["quality"]["validVotes"] == 1
    assert payload["ranking"][0]["driverId"] == "senna"


def test_published_fan_index_has_page_and_valid_payload() -> None:
    project = Path(__file__).resolve().parents[1]
    page = (project / "public" / "opinion" / "index.html").read_text(encoding="utf-8")
    payload = json.loads(
        (project / "public" / "data" / "opinion-ranking.json").read_text(encoding="utf-8")
    )
    assert "The internet’s <em>F1 GOAT.</em>" in page
    assert "../data/opinion-ranking.json" in page
    assert payload["quality"]["commentsSampled"] > payload["quality"]["validVotes"] > 0
    assert payload["ranking"][0]["name"] == "Ayrton Senna"
