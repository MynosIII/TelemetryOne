"""Public-comment opinion poll for TelemetryOne.

The module deliberately separates collection from interpretation.  Collectors emit a small,
platform-neutral JSONL schema; the functions below classify explicit GOAT choices, remove
duplicate voters, and export a privacy-preserving aggregate for the static site.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DRIVERS: dict[str, dict[str, object]] = {
    "senna": {
        "name": "Ayrton Senna",
        "aliases": ("ayrton senna", "airton sena", "ayrton sena", "senna"),
    },
    "michael_schumacher": {
        "name": "Michael Schumacher",
        "aliases": (
            "michael schumacher",
            "m schumacher",
            "schumacher",
            "shumacher",
            "schumi",
            "schu",
        ),
    },
    "hamilton": {
        "name": "Lewis Hamilton",
        "aliases": ("lewis hamilton", "hamilton", "lewis"),
    },
    "fangio": {
        "name": "Juan Manuel Fangio",
        "aliases": ("juan manuel fangio", "juan fangio", "fangio"),
    },
    "clark": {"name": "Jim Clark", "aliases": ("jim clark", "clark")},
    "prost": {"name": "Alain Prost", "aliases": ("alain prost", "prost")},
    "max_verstappen": {
        "name": "Max Verstappen",
        "aliases": ("max verstappen", "verstappen", "mad max"),
    },
    "alonso": {"name": "Fernando Alonso", "aliases": ("fernando alonso", "alonso")},
    "lauda": {"name": "Niki Lauda", "aliases": ("niki lauda", "lauda")},
    "stewart": {"name": "Jackie Stewart", "aliases": ("jackie stewart",)},
    "vettel": {"name": "Sebastian Vettel", "aliases": ("sebastian vettel", "vettel", "seb")},
    "moss": {"name": "Stirling Moss", "aliases": ("stirling moss",)},
    "ascari": {"name": "Alberto Ascari", "aliases": ("alberto ascari", "ascari")},
    "piquet": {"name": "Nelson Piquet", "aliases": ("nelson piquet", "piquet")},
    "gilles_villeneuve": {
        "name": "Gilles Villeneuve",
        "aliases": ("gilles villeneuve", "gilles"),
    },
    "fittipaldi": {
        "name": "Emerson Fittipaldi",
        "aliases": ("emerson fittipaldi", "emerson"),
    },
    "brabham": {"name": "Jack Brabham", "aliases": ("jack brabham",)},
    "surtees": {"name": "John Surtees", "aliases": ("john surtees", "surtees")},
    "hakkinen": {"name": "Mika Hakkinen", "aliases": ("mika hakkinen", "hakkinen")},
    "raikkonen": {"name": "Kimi Raikkonen", "aliases": ("kimi raikkonen", "raikkonen", "kimi")},
    "mansell": {"name": "Nigel Mansell", "aliases": ("nigel mansell", "mansell")},
    "rindt": {"name": "Jochen Rindt", "aliases": ("jochen rindt", "rindt")},
    "hill": {"name": "Graham Hill", "aliases": ("graham hill",)},
    "andretti": {"name": "Mario Andretti", "aliases": ("mario andretti",)},
    "reutemann": {"name": "Carlos Reutemann", "aliases": ("carlos reutemann", "reutemann")},
    "button": {"name": "Jenson Button", "aliases": ("jenson button",)},
    "hunt": {"name": "James Hunt", "aliases": ("james hunt",)},
    "keke_rosberg": {"name": "Keke Rosberg", "aliases": ("keke rosberg",)},
    "montoya": {"name": "Juan Pablo Montoya", "aliases": ("juan pablo montoya", "montoya")},
    "ricciardo": {"name": "Daniel Ricciardo", "aliases": ("daniel ricciardo", "ricciardo")},
    "leclerc": {"name": "Charles Leclerc", "aliases": ("charles leclerc", "leclerc")},
    "norris": {"name": "Lando Norris", "aliases": ("lando norris",)},
    "russell": {"name": "George Russell", "aliases": ("george russell",)},
    "bottas": {"name": "Valtteri Bottas", "aliases": ("valtteri bottas", "bottas")},
    "perez": {"name": "Sergio Perez", "aliases": ("sergio perez", "checo perez")},
    "hulkenberg": {"name": "Nico Hulkenberg", "aliases": ("nico hulkenberg", "hulkenberg")},
    "sainz": {"name": "Carlos Sainz", "aliases": ("carlos sainz",)},
    "gurney": {"name": "Dan Gurney", "aliases": ("dan gurney",)},
    "bellof": {"name": "Stefan Bellof", "aliases": ("stefan bellof", "bellof")},
    "kubica": {"name": "Robert Kubica", "aliases": ("robert kubica", "kubica")},
    "villenueve": {
        "name": "Jacques Villeneuve",
        "aliases": ("jacques villeneuve",),
    },
    "winkelhock": {"name": "Markus Winkelhock", "aliases": ("markus winkelhock",)},
}

NEGATION_RE = re.compile(
    r"\b(not|isnt|isn't|never|no\s+es|nao\s+e|não\s+é|pas|nicht)\b", re.IGNORECASE
)
RANK_ONE_RE = re.compile(
    r"(?:^|[\s,;|])(?:#?1|1st|first|primero|premier|erste)[\s.):>\-]+", re.IGNORECASE
)
DIRECT_RIGHT_RE = re.compile(
    r"^\s*(?:[,;:.…—-]\s*)*(?:(?:is|was|remains|es|era|fue|e|é|foi|ist)\s+)?"
    r"(?:(?:without\s+(?:a\s+)?doubt|simply|easily|clearly|definitely|always)\s+)?"
    r"(?:(?:the|my|el|la|o|le)\s+)?(?:undisputed\s+)?"
    r"(?:goat|g\.?o\.?a\.?t\.?|greatest|mejor(?!\s+que)(?:\s+piloto)?|"
    r"melhor(?!\s+que)(?:\s+piloto)?|meilleur(?!\s+que)(?:\s+pilote)?|"
    r"miglior(?:e)?(?!\s+di)|piu\s+grande|"
    r"(?:der\s+)?beste|grosste|"
    r"best(?!\s+(?:than|car|cars|package|win|ratio|qualifier|on\s+the\s+grid))|"
    r"number\s*(?:one|1)|no\.?\s*1|nr\.?\s*1|#\s*1|top\s*1|"
    r"(?:my\s+)?(?:pick|choice|vote)|the\s+one|hands\s+down|all\s+day|"
    r"deserves?(?:\s+to\s+be)?(?:\s+at)?\s+(?:number\s*)?(?:one|1)|"
    r"deserves?\s+(?:the|de)\s+first\s+(?:place|position)|no\s+hay\s+mas)\b",
    re.IGNORECASE,
)
DIRECT_LEFT_RE = re.compile(
    r"(?:goat|greatest|best|(?:my\s+)?number\s*(?:one|1)|no\.?\s*1|#\s*1|"
    r"top\s*1|el\s+mejor|"
    r"o\s+melhor|le\s+meilleur|il\s+migliore|il\s+piu\s+grande|"
    r"der\s+beste|der\s+grosste|nummer\s+eins)"
    r"\s*(?:driver|piloto|pilote|fahrer)?\s*(?:is|was|es|era|e|é|ist|è|:)?\s*$",
    re.IGNORECASE,
)
PERSONAL_LEFT_RE = re.compile(
    r"(?:for\s+me|to\s+me|in\s+my\s+opinion|my\s+(?:pick|choice|vote)(?:\s+is)?|"
    r"i(?:'d|\s+would)?\s+(?:pick|choose|vote|go|put)(?:\s+for|\s+with)?|"
    r"i\s+prefer|para\s+mi(?:\s+concepto)?(?:\s+(?:es|fue))?|"
    r"me\s+quedo\s+con|yo\s+elijo|"
    r"mi\s+(?:voto|eleccion|elegido|top)(?:\s+es)?|voto\s+por|"
    r"pra\s+mim(?:\s+e)?|eu\s+(?:escolho|prefiro)|"
    r"pour\s+moi(?:\s+c'est)?|fur\s+mich(?:\s+ist)?|per\s+me(?:\s+e)?)[,;:—-]?\s*$",
    re.IGNORECASE,
)
PLURAL_ENDORSEMENT_RE = re.compile(
    r"\b(?:are|were|son|eran|sao|são)\s+(?:all\s+|los\s+|os\s+)?"
    r"(?:the\s+)?(?:best|greatest|mejores|melhores)\b",
    re.IGNORECASE,
)
SKEPTICAL_FRAME_RE = re.compile(
    r"\b(?:when\s+(?:people|they)\s+say|cuando\s+dicen|"
    r"(?:you|people|anyone)\s+(?:really\s+)?think|"
    r"(?:people|fans?|fanboys|they)\s+(?:are\s+)?(?:telling|saying|claiming)|"
    r"can(?:not|'t)\s+believe)\b",
    re.IGNORECASE,
)
RELATIVE_ONLY_RE = re.compile(
    r"\b(?:better\s+than|worse\s+than|over|above|below|higher|lower|"
    r"mejor\s+que|peor\s+que|encima\s+de|debajo\s+de|"
    r"melhor\s+que|pior\s+que|too\s+high|too\s+low|that\s+high|that\s+low|"
    r"where\s+is|with\s*out|missing|honou?rable)\b|[<>]{1,}",
    re.IGNORECASE,
)
NON_FIRST_RANK_RE = re.compile(
    r"(?:^|[\s,;|])(?:#?(?:[2-9]|[1-9][0-9]+)|(?:2nd|3rd|[4-9]th))\s*[.):>\-]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VoteDecision:
    driver_id: str | None
    confidence: float
    rule: str
    mentions: tuple[str, ...]


def normalize_text(text: str) -> str:
    """Lowercase, fold accents, and normalize punctuation/spacing for matching."""

    folded = unicodedata.normalize("NFKD", str(text))
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    folded = folded.lower().replace("’", "'").replace("ß", "ss")
    return re.sub(r"\s+", " ", folded).strip()


def _alias_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for driver_id, profile in DRIVERS.items():
        for alias in profile["aliases"]:
            for match in re.finditer(rf"(?<!\w){re.escape(str(alias))}(?!\w)", text):
                spans.append((match.start(), match.end(), driver_id))
    return sorted(set(spans))


def classify_vote(
    text: str, *, prompted: bool = False, ranking_prompt: bool = False
) -> VoteDecision:
    """Return one explicit all-time-best choice or a transparent rejection reason.

    This is intentionally conservative. A mere name mention does not become a vote unless the
    comment is a very short answer, contains endorsement language, or starts a ranking with that
    driver.
    """

    normalized = normalize_text(text)
    spans = _alias_spans(normalized)
    mentions = tuple(dict.fromkeys(span[2] for span in spans))
    if not mentions:
        return VoteDecision(None, 0.0, "no_driver", ())

    rank_match = RANK_ONE_RE.search(normalized)
    if rank_match:
        following = [span for span in spans if span[0] >= rank_match.end()]
        if following and following[0][0] - rank_match.end() <= 4:
            return VoteDecision(following[0][2], 0.98, "ranked_first", mentions)

    if ranking_prompt:
        ranked_lines: list[tuple[str, ...]] = []
        for raw_line in str(text).splitlines():
            line = normalize_text(raw_line)
            if not line or len(re.findall(r"\w+", line)) > 10:
                continue
            line_mentions = tuple(dict.fromkeys(span[2] for span in _alias_spans(line)))
            if line_mentions and not NEGATION_RE.search(line):
                ranked_lines.append(line_mentions)
        if len(ranked_lines) >= 3 and all(len(line) == 1 for line in ranked_lines[:3]):
            return VoteDecision(ranked_lines[0][0], 0.94, "unnumbered_ranked_first", mentions)

    direct_matches: set[str] = set()
    if (
        "?" not in normalized
        and not SKEPTICAL_FRAME_RE.search(normalized)
        and not (len(mentions) > 1 and PLURAL_ENDORSEMENT_RE.search(normalized))
    ):
        for start, end, driver_id in spans:
            left = normalized[max(0, start - 55) : start]
            right = normalized[end : min(len(normalized), end + 65)]
            right_match = DIRECT_RIGHT_RE.search(right)
            left_match = DIRECT_LEFT_RE.search(left) or PERSONAL_LEFT_RE.search(left)
            if right_match and not NEGATION_RE.search(right[: right_match.end()]):
                direct_matches.add(driver_id)
            if left_match and not NEGATION_RE.search(left[left_match.start() :]):
                direct_matches.add(driver_id)
    if len(direct_matches) == 1:
        return VoteDecision(next(iter(direct_matches)), 0.96, "direct_endorsement", mentions)
    if len(direct_matches) > 1:
        return VoteDecision(None, 0.0, "ambiguous_multiple", mentions)

    if (
        len(mentions) == 1
        and "?" not in normalized
        and not NEGATION_RE.search(normalized)
        and not NON_FIRST_RANK_RE.search(normalized)
    ):
        remainder = normalized
        driver_id = mentions[0]
        for alias in DRIVERS[driver_id]["aliases"]:
            remainder = re.sub(rf"(?<!\w){re.escape(str(alias))}(?!\w)", " ", remainder)
        remainder_words = set(re.findall(r"[a-z]+", remainder))
        short_answer_words = {
            "always",
            "doubt",
            "duda",
            "goat",
            "incomparable",
            "inigualable",
            "sem",
            "se",
            "si",
            "simply",
            "the",
            "unico",
            "unique",
            "without",
        }
        if remainder_words <= short_answer_words:
            return VoteDecision(mentions[0], 0.82, "short_answer", mentions)

        # In a thread whose title explicitly asks for the all-time choice, a terse response is
        # semantically an answer even when it omits words such as "GOAT". Relative placements
        # remain excluded because "should be higher" does not identify a number-one choice.
        prompted_words = {
            "auf",
            "always",
            "clearly",
            "definitely",
            "die",
            "doubt",
            "duda",
            "easily",
            "forever",
            "habran",
            "immer",
            "incomparable",
            "inigualable",
            "is",
            "no",
            "noo",
            "nope",
            "numero",
            "number",
            "one",
            "sem",
            "simply",
            "sir",
            "that",
            "thats",
            "the",
            "tho",
            "though",
            "unico",
            "unique",
            "unmatched",
            "without",
            "llama",
        }
        if prompted and remainder_words <= prompted_words and not RELATIVE_ONLY_RE.search(normalized):
            return VoteDecision(mentions[0], 0.78, "prompted_short_answer", mentions)

    if len(mentions) > 1:
        return VoteDecision(None, 0.0, "ambiguous_multiple", mentions)
    if len(re.findall(r"\w+", normalized)) <= 5:
        return VoteDecision(None, 0.0, "short_ambiguous", mentions)
    return VoteDecision(None, 0.0, "mention_without_choice", mentions)


def anonymize_author(platform: str, author_id: str) -> str:
    """Create a stable non-reversible voter key without retaining a public handle."""

    return sha256(f"telemetry-one:{platform}:{author_id}".encode()).hexdigest()[:20]


def redact_public_text(text: str) -> str:
    """Remove incidental handles, email addresses, and URLs from stored comment text."""

    value = re.sub(r"https?://\S+|www\.\S+", "[url]", str(text), flags=re.IGNORECASE)
    value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", "[email]", value, flags=re.IGNORECASE)
    return re.sub(r"(?<!\w)@[\w.-]+", "@user", value)


def youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname in {"youtu.be", "www.youtu.be"}:
        return parsed.path.strip("/")
    value = parse_qs(parsed.query).get("v", [""])[0]
    if not value:
        raise ValueError(f"Could not find YouTube video id in {url!r}")
    return value


def read_jsonl(paths: list[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
                rows.append(row)
    return rows


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def build_opinion_payload(
    rows: list[dict[str, object]], *, generated_at: str | None = None
) -> dict[str, object]:
    """Classify raw rows and create the aggregate consumed by the static page."""

    decisions: list[dict[str, object]] = []
    rejection_counts: Counter[str] = Counter()
    source_sampled: Counter[str] = Counter()
    source_meta: dict[str, dict[str, object]] = {}
    seen_comments: set[tuple[str, str]] = set()

    for row in rows:
        platform = str(row.get("platform", "unknown"))
        source_id = str(row.get("source_id", "unknown"))
        comment_id = str(row.get("comment_id", ""))
        comment_key = (platform, comment_id)
        if comment_id and comment_key in seen_comments:
            rejection_counts["duplicate_comment"] += 1
            continue
        if comment_id:
            seen_comments.add(comment_key)
        source_sampled[source_id] += 1
        source_meta[source_id] = {
            "id": source_id,
            "platform": platform,
            "title": row.get("source_title", source_id),
            "url": row.get("source_url", ""),
            "publishedDate": row.get("source_published_date", ""),
            "queryFamily": row.get("query_family", "all-time-best"),
        }
        query_family = str(row.get("query_family", "all-time-best"))
        decision = classify_vote(
            str(row.get("text", "")),
            prompted=query_family
            in {"all-time-question", "all-time-ranking", "all-time-debate", "all-time-top"},
            ranking_prompt=query_family in {"all-time-ranking", "all-time-top"},
        )
        if decision.driver_id is None:
            rejection_counts[decision.rule] += 1
            continue
        decisions.append(
            {
                **row,
                "driver_id": decision.driver_id,
                "confidence": decision.confidence,
                "rule": decision.rule,
            }
        )

    # One person, one vote per platform. Repeated identical choices collapse to one; conflicting
    # choices are removed rather than resolved with engagement, keeping every person equal.
    votes_by_voter: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for vote in decisions:
        voter_key = (str(vote.get("platform", "unknown")), str(vote.get("author_hash", "")))
        if not voter_key[1]:
            voter_key = (voter_key[0], f"comment:{vote.get('comment_id', '')}")
        votes_by_voter[voter_key].append(vote)

    votes: list[dict[str, object]] = []
    for voter_votes in votes_by_voter.values():
        choices = {str(vote["driver_id"]) for vote in voter_votes}
        if len(choices) > 1:
            rejection_counts["conflicting_voter"] += len(voter_votes)
            continue
        votes.append(max(voter_votes, key=lambda vote: float(vote["confidence"])))
        rejection_counts["duplicate_voter"] += len(voter_votes) - 1
    counts: Counter[str] = Counter(str(vote["driver_id"]) for vote in votes)
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for vote in votes:
        by_source[str(vote.get("source_id", "unknown"))][str(vote["driver_id"])] += 1

    total_votes = len(votes)
    eligible_sources = [source for source, values in by_source.items() if sum(values.values()) >= 5]
    source_platform = {source_id: str(meta["platform"]) for source_id, meta in source_meta.items()}
    eligible_platforms = sorted({source_platform[source] for source in eligible_sources})
    ranking: list[dict[str, object]] = []
    for driver_id, count in counts.items():
        platform_shares = []
        for platform in eligible_platforms:
            shares = [
                by_source[source][driver_id] / sum(by_source[source].values())
                for source in eligible_sources
                if source_platform[source] == platform
            ]
            if shares:
                platform_shares.append(sum(shares) / len(shares))
        balanced_share = (
            sum(platform_shares) / len(platform_shares)
            if platform_shares
            else count / total_votes
        )
        low, high = _wilson_interval(count, total_votes)
        ranking.append(
            {
                "driverId": driver_id,
                "name": DRIVERS[driver_id]["name"],
                "votes": count,
                "share": round(count / total_votes, 4) if total_votes else 0,
                "balancedShare": round(balanced_share, 4),
                "platforms": len(
                    {str(vote.get("platform")) for vote in votes if vote["driver_id"] == driver_id}
                ),
                "ciLow": round(low, 4),
                "ciHigh": round(high, 4),
                "sources": len([source for source in by_source if by_source[source][driver_id]]),
            }
        )
    ranking.sort(
        key=lambda item: (-float(item["balancedShare"]), -int(item["votes"]), str(item["name"]))
    )
    for index, item in enumerate(ranking, start=1):
        item["rank"] = index

    source_rows = []
    for source_id, meta in source_meta.items():
        valid = sum(by_source[source_id].values())
        leader_id, leader_votes = by_source[source_id].most_common(1)[0] if valid else (None, 0)
        source_rows.append(
            {
                **meta,
                "sampled": source_sampled[source_id],
                "validVotes": valid,
                "leader": DRIVERS[leader_id]["name"] if leader_id else None,
                "leaderShare": round(leader_votes / valid, 4) if valid else 0,
            }
        )
    source_rows.sort(key=lambda item: str(item["publishedDate"]))

    platform_counts = Counter(str(row.get("platform", "unknown")) for row in rows)
    platform_votes = Counter(str(vote.get("platform", "unknown")) for vote in votes)
    return {
        "schemaVersion": 1,
        "generatedAt": generated_at or datetime.now(UTC).isoformat(),
        "question": "Who is the greatest Formula 1 driver of all time?",
        "method": {
            "unit": "one explicit choice per anonymized author and platform",
            "ranking": (
                "mean source vote share within each platform, then equal-weight mean across "
                "eligible platforms; sources require at least five valid votes"
            ),
            "classifier": "auditable multilingual rules; no generative AI",
            "caveat": "A public-comment convenience sample is not representative of all Formula 1 fans.",
        },
        "quality": {
            "commentsSampled": len(rows),
            "uniqueComments": sum(source_sampled.values()),
            "validVotes": total_votes,
            "classificationRate": (
                round(total_votes / sum(source_sampled.values()), 4)
                if source_sampled
                else 0
            ),
            "sources": len(source_meta),
            "platforms": dict(sorted(platform_counts.items())),
            "platformVotes": dict(sorted(platform_votes.items())),
            "rejections": dict(sorted(rejection_counts.items())),
        },
        "ranking": ranking,
        "sources": source_rows,
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
