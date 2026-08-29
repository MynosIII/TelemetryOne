# TelemetryOne Fan Index

## What it measures

The Fan Index answers one narrow question: **which driver does an author explicitly choose as
the greatest Formula 1 driver of all time inside the selected public conversations?** It is a
public-comment convenience sample, not a representative poll of Formula 1 fans.

The performance model and the opinion ranking are intentionally separate pages. The former
estimates historical performance from race data; the latter describes visible public opinion.

## Tool decision

| Platform | Primary connector | Cost | Requirement | Decision |
| --- | --- | --- | --- | --- |
| YouTube | `youtube-comment-downloader` | Free | None for public comments | Used for the reproducible pilot |
| YouTube | Data API v3 | Free quota | Google Cloud API key | Best long-term replacement |
| Reddit | Public Atom/RSS feeds | Free | Rate limited | Used when the public feed responds |
| Forums | XenForo/phpBB HTML | Free | Public thread | Used; quoted text is removed |
| X | `twscrape` | Free / MIT | Authorized X session cookies | Implemented, disabled by default |
| Instagram | `Instaloader` | Free / MIT | Public post; login/session often required | Implemented, disabled by default |

The no-key YouTube package still ships an obsolete Chrome 79 user agent. TelemetryOne overrides
it with a current browser identifier; without that change the 2026 YouTube page does not expose
the configuration expected by the package. The official YouTube API is more stable: public
`commentThreads.list` requests cost one quota unit, but it requires a project and API key.

X and Instagram are not anonymous, zero-configuration sources in practice. `twscrape` explicitly
requires an authorized X account and stores its sessions in SQLite. Instaloader can read comments
from a public post, but Instagram may require a logged-in session and can change access limits.
The project does not automate account creation, CAPTCHA solving, proxy rotation, or access-control
bypass.

## Current snapshot

The collection manifests live in `configs/opinion_sources*.json`. The 2026-08-29 snapshot contains
16,364 unique public comments from 61 selected conversations on YouTube, Reddit, GTPlanet,
Z4 Forum, and FORUMula1. After classification, comment and author deduplication, and removal of
conflicting choices, 1,632 explicit votes remain. Thirty-three conversations contain at least five
valid votes and therefore influence the balanced index.

The working target was 2,000 valid choices. The snapshot stops below that target rather than
weakening the definition of a vote. Larger YouTube conversations were sampled more deeply and
search discovery was expanded across English, Spanish, Portuguese, French, German, and Italian.
Search false positives—such as rankings of races, charisma, or current seasons—are explicitly
excluded from the published build.

## From comment to vote

1. Download the public comment and source metadata.
2. Immediately replace the author/channel identifier with a stable SHA-256-derived key. Do not
   retain author names, avatars, or profile URLs.
3. Match a curated multilingual driver alias list.
4. Count only a direct endorsement, the first entry in an explicit ranking, or a name-only answer
   to the prompt. A relative “X is better than Y” claim is not enough to establish an all-time pick.
5. Reject no-driver comments, mere mentions, questions, and multi-driver ambiguity.
6. Keep one vote per hashed author and platform. Repeated identical choices collapse to one;
   authors making conflicting choices are removed rather than resolved with likes or engagement.
7. Within every source containing at least five valid votes, calculate each driver's share. Average
   those source shares inside each platform, then give YouTube, Reddit, and forums equal weight.

The raw vote count and 95% Wilson interval are also exported. The interval describes sampling
uncertainty within this convenience sample; it does not remove selection bias.

## Reproduce

From the `TelemetryOne` directory:

```powershell
python -m pip install -e ".[scrape]"
python -m historical_xw.opinion_cli collect `
  --config configs/opinion_sources.json `
  --output data/opinion/comments-shard-0.jsonl `
  --shard-index 0 --shard-count 3
$opinionInputs = (Get-ChildItem -Path data/opinion -Filter 'comments-*.jsonl').FullName
python -m historical_xw.opinion_cli build `
  --input $opinionInputs `
  --exclude-source-file configs/opinion_excluded_sources.json `
  --output public/data/opinion-ranking.json
python -m http.server 8765 --directory public
```

Open `http://127.0.0.1:8765/opinion/`.

## Enable X

Create an authorized `twscrape` account database according to that project's instructions, then
set the `x-f1-goat` source to `"enabled": true`. Never commit `accounts.db`, cookies, passwords,
or exported browser sessions.

## Enable Instagram

Choose a public post whose caption asks an all-time-best question, replace the placeholder URL and
shortcode, create an Instaloader session locally if Instagram requires it, and enable the source.
Never commit the session file. A source prompt centered on one named driver should not be used,
because it would preselect that driver's fan community.

## Main limitations

- Fans self-select into comment threads.
- Video framing, channel audience, language, era, and recommendation algorithms affect exposure.
- Deleted, hidden, private, and unindexed comments are absent.
- A rule-based classifier trades recall for auditability and higher precision.
- X and Instagram are excluded from this snapshot until authorized sessions are supplied; their
  collectors remain available without weakening access controls.
- Results should be refreshed on a declared schedule and versioned; silent live updates would make
  classroom results irreproducible.
